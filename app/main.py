from fastapi import FastAPI

from app.api import orders, products
from app.db.session import get_conn

app = FastAPI(title="Order Intake Agent")
app.include_router(orders.router)
app.include_router(products.router)


@app.get("/health")
def health():
    with get_conn() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}
