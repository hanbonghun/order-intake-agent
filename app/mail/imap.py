"""IMAP 폴러: 받은편지함의 새 메일을 가져와 수신 처리(handle_email)에 넘긴다.

처리 여부는 메일의 읽음 표시가 아니라 DB에 저장한 UID 커서로 판단한다.
같은 메일함을 사람이 함께 보면 Gmail 화면에서 메일이 먼저 읽음 처리될 수 있기 때문이다.

    uv run python -m app.mail.imap           # 계속 폴링
    uv run python -m app.mail.imap --once    # 한 번만
"""
import argparse
import imaplib
import logging
import re
import time
from email.utils import parseaddr

from app.config import settings
from app.db.session import get_conn
from app.ingest.handler import handle_email

log = logging.getLogger("imap")
MAILBOX = "INBOX"


def _accepted_senders() -> set[str]:
    return {a.strip().lower() for a in settings.mail_accept_from.split(",") if a.strip()}


def _load_cursor(uidvalidity: int, current_max: int) -> int:
    """마지막으로 처리한 UID. 처음이거나 메일함이 재설정(UIDVALIDITY 변경)되면 새로 정한다:
    MAIL_PROCESS_BACKLOG=false면 지금 있는 메일은 건너뛰고(현재 최대 UID), true면 처음부터(0)."""
    with get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS mail_cursor "
                     "(mailbox TEXT PRIMARY KEY, uidvalidity BIGINT NOT NULL, last_uid BIGINT NOT NULL)")
        row = conn.execute("SELECT uidvalidity, last_uid FROM mail_cursor WHERE mailbox = %s", (MAILBOX,)).fetchone()
        if row and row["uidvalidity"] == uidvalidity:
            return row["last_uid"]
        start = 0 if settings.mail_process_backlog else current_max
        _save_cursor(conn, uidvalidity, start)
        log.info("커서 초기화: UID %s 이후부터 처리", start)
        return start


def _save_cursor(conn, uidvalidity: int, last_uid: int) -> None:
    conn.execute(
        """
        INSERT INTO mail_cursor (mailbox, uidvalidity, last_uid) VALUES (%s, %s, %s)
        ON CONFLICT (mailbox) DO UPDATE SET uidvalidity = EXCLUDED.uidvalidity, last_uid = EXCLUDED.last_uid
        """,
        (MAILBOX, uidvalidity, last_uid),
    )


def _sender_allowed(imap, uid: bytes) -> bool:
    """발신자 제한이 있으면 본문을 읽기 전에 From 헤더만 보고 거른다."""
    accept = _accepted_senders()
    if not accept:
        return True
    _, data = imap.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (FROM)])")
    header = next((p[1] for p in data if isinstance(p, tuple)), b"").decode(errors="replace")
    return parseaddr(header.split(":", 1)[-1].strip())[1].lower() in accept


def poll_once() -> list[dict]:
    """커서 이후 도착한 메일을 UID 순서대로 처리한다. 처리 중 오류가 나도 커서를 넘겨
    같은 메일을 무한히 재시도하지 않는다 (문서 상태로 추적). 중복 처리는 Message-ID로 한 번 더 막는다."""
    results = []
    with imaplib.IMAP4_SSL(settings.mail_imap_host) as imap:
        imap.login(settings.mail_address, settings.mail_app_password)
        imap.select(MAILBOX)
        uidvalidity = int(re.search(rb"\d+", imap.response("UIDVALIDITY")[1][0]).group())
        _, data = imap.uid("search", None, "ALL")
        all_uids = [int(u) for u in data[0].split()]
        last = _load_cursor(uidvalidity, max(all_uids, default=0))

        for uid in (u for u in all_uids if u > last):
            buid = str(uid).encode()
            if _sender_allowed(imap, buid):
                _, msg_data = imap.uid("fetch", buid, "(BODY.PEEK[])")
                raw = next(part[1] for part in msg_data if isinstance(part, tuple))
                try:
                    result = handle_email(raw)
                    log.info("처리: uid=%s → %s", uid, {k: result.get(k) for k in ("document_id", "status", "order_id")})
                except Exception as e:   # 한 메일 실패가 폴러를 멈추지 않게
                    log.exception("처리 실패: uid=%s", uid)
                    result = {"error": f"{type(e).__name__}: {e}"}
                imap.uid("store", buid, "+FLAGS", "(\\Seen)")   # 사람이 볼 때 처리됐음을 알 수 있게 (판단 기준은 아님)
                results.append({"uid": uid} | result)
            with get_conn() as conn:
                _save_cursor(conn, uidvalidity, uid)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    if not (settings.mail_address and settings.mail_app_password):
        raise SystemExit("MAIL_ADDRESS, MAIL_APP_PASSWORD를 .env에 설정하세요")
    log.info("폴링 시작 (기존 메일 %s, 발신자 제한 %s)", "포함" if settings.mail_process_backlog else "제외",
             f"{len(_accepted_senders())}개 주소" if _accepted_senders() else "없음")
    while True:
        try:
            for r in poll_once():
                print(r, flush=True)
        except (imaplib.IMAP4.error, OSError):
            log.exception("IMAP 연결 실패, 다음 주기에 재시도")
        if args.once:
            break
        time.sleep(settings.mail_poll_seconds)


if __name__ == "__main__":
    main()
