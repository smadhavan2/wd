from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

conn = sqlite3.connect("writing_stability.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT,
    time_ms INTEGER,
    ax REAL, ay REAL, az REAL,
    gx REAL, gy REAL, gz REAL,
    tremor REAL,
    jerk REAL,
    smoothness REAL,
    created_at REAL
)
""")
conn.commit()

last_samples = {}  

class Sample(BaseModel):
    device_id: str
    time_ms: int
    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float

@app.get("/")
def root():
    return {"message": "Smart Writing Stability Backend running"}

@app.get("/api/test")
def test():
    return {"message": "Backend is working!"}


@app.post("/api/data")
def receive_data(sample: Sample):
    tremor = 0.0
    jerk = 0.0
    smoothness = 1.0

    prev = last_samples.get(sample.device_id)

    if prev is not None:
        tremor = (
            abs(sample.gx - prev["gx"]) +
            abs(sample.gy - prev["gy"]) +
            abs(sample.gz - prev["gz"])
        )

        jerk = (
            abs(sample.ax - prev["ax"]) +
            abs(sample.ay - prev["ay"]) +
            abs(sample.az - prev["az"])
        )

        smoothness_raw = tremor + jerk
        smoothness = 1.0 / (1.0 + smoothness_raw)
    else:
        tremor = 0.0
        jerk = 0.0
        smoothness = 1.0

    last_samples[sample.device_id] = {
        "ax": sample.ax,
        "ay": sample.ay,
        "az": sample.az,
        "gx": sample.gx,
        "gy": sample.gy,
        "gz": sample.gz,
    }

    print("\n--- RECEIVED SAMPLE ---")
    print("Device:", sample.device_id)
    print("Raw:", sample)
    print("Tremor:", tremor)
    print("Jerk:", jerk)
    print("Smoothness:", smoothness)

    cur.execute("""
        INSERT INTO samples (
            device_id, time_ms,
            ax, ay, az,
            gx, gy, gz,
            tremor, jerk, smoothness,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sample.device_id, sample.time_ms,
        sample.ax, sample.ay, sample.az,
        sample.gx, sample.gy, sample.gz,
        tremor, jerk, smoothness,
        time.time()
    ))
    conn.commit()

    return {
        "status": "ok",
        "tremor": tremor,
        "jerk": jerk,
        "smoothness": smoothness
    }


@app.get("/api/latest")
def latest(device_id: str = "pen_01"):
    cur.execute("""
        SELECT time_ms, tremor, jerk, smoothness
        FROM samples
        WHERE device_id = ?
        ORDER BY id DESC
        LIMIT 1
    """, (device_id,))
    row = cur.fetchone()
    if not row:
        return {}

    return {
        "time_ms": row[0],
        "tremor": row[1],
        "jerk": row[2],
        "smoothness": row[3]
    }


@app.get("/api/history")
def history(device_id: str = "pen_01", limit: int = 200):
    cur.execute("""
        SELECT time_ms, tremor, jerk, smoothness
        FROM samples
        WHERE device_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (device_id, limit))
    rows = cur.fetchall()
    rows = rows[::-1] 

    data = [
        {
            "time_ms": r[0],
            "tremor": r[1],
            "jerk": r[2],
            "smoothness": r[3]
        }
        for r in rows
    ]
    return {"data": data}
