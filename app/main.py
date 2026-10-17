from fastapi import FastAPI

from app.db.session import get_conn

app = FastAPI(title="Order Intake Agent")


@app.get("/health")
def health():
    with get_conn() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}
