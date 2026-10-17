from fastapi import APIRouter

from app.db.session import get_conn
from app.services.matching import search_candidates

router = APIRouter(prefix="/products", tags=["products"])


@router.get("")
def search_products(q: str, customer_id: int | None = None, limit: int = 5):
    with get_conn() as conn:
        return search_candidates(conn, customer_id, q, limit)
