"""평가 대상 실행기. 케이스 하나를 받아 결과 dict를 반환한다.

- dummy: 아무것도 하지 않는 기준선 (지표 파이프라인 확인용)
- oracle: 정답을 그대로 반환 (채점 로직 검증용, 모든 지표가 만점이어야 함)
- graph: 실제 에이전트 (그래프 구현 후 추가)
"""
from collections.abc import Callable

from evals.dataset import Case

Runner = Callable[[Case], dict]


def dummy(case: Case) -> dict:
    return {"is_order": False, "decision": "skip", "items": []}


def oracle(case: Case) -> dict:
    return dict(case.expected)


RUNNERS: dict[str, Runner] = {"dummy": dummy, "oracle": oracle}
