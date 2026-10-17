import json
from dataclasses import dataclass
from pathlib import Path

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"


@dataclass
class Case:
    case_id: str
    category: str
    dir: Path
    input: dict           # input.json
    expected: dict        # expected.json의 "expected"
    reply: dict | None    # 재질의 시나리오의 스크립트된 회신 (reply.json: received_at, body)


def load_cases(samples_dir: Path = SAMPLES_DIR, categories: list[str] | None = None) -> list[Case]:
    cases = []
    for case_dir in sorted(p for p in samples_dir.iterdir() if (p / "expected.json").exists()):
        meta = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
        if categories and meta["category"] not in categories:
            continue
        reply_path = case_dir / "reply.json"
        cases.append(Case(
            case_id=meta["case_id"],
            category=meta["category"],
            dir=case_dir,
            input=json.loads((case_dir / "input.json").read_text(encoding="utf-8")),
            expected=meta["expected"],
            reply=json.loads(reply_path.read_text(encoding="utf-8")) if reply_path.exists() else None,
        ))
    return cases
