"""체크포인터가 붙은 그래프. 회신 대기 상태를 PostgreSQL에 저장해 프로세스가 재시작돼도 이어서 처리한다."""
import atexit
from functools import cache

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.agent.graph import build_graph
from app.config import settings

# 체크포인트에서 복원을 허용할 상태 타입 (등록하지 않은 타입 역직렬화는 차단 예정)
STATE_TYPES = [("app.agent.state", name) for name in ("ExtractedItem", "MatchedItem", "Issue", "Question")]


@cache
def get_graph():
    pool = ConnectionPool(
        settings.database_url,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=True,
    )
    atexit.register(pool.close)
    checkpointer = PostgresSaver(pool, serde=JsonPlusSerializer(allowed_msgpack_modules=STATE_TYPES))
    checkpointer.setup()   # 체크포인트 테이블 생성 (이미 있으면 그대로)
    return build_graph(checkpointer=checkpointer)
