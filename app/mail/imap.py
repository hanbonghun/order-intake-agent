"""IMAP 폴러: 받은편지함의 읽지 않은 메일을 가져와 수신 처리(handle_email)에 넘긴다.

    uv run python -m app.mail.imap           # 계속 폴링
    uv run python -m app.mail.imap --once    # 한 번만
"""
import argparse
import imaplib
import logging
import time

from app.config import settings
from app.ingest.handler import handle_email

log = logging.getLogger("imap")


def poll_once() -> list[dict]:
    """읽지 않은 메일을 처리한다. 가져올 때는 읽음 표시를 하지 않고(BODY.PEEK), 처리 후에 표시한다.
    처리 중 오류가 나도 읽음 표시해 같은 메일을 무한히 재시도하지 않게 한다 (문서 상태로 추적)."""
    results = []
    with imaplib.IMAP4_SSL(settings.mail_imap_host) as imap:
        imap.login(settings.mail_address, settings.mail_app_password)
        imap.select("INBOX")
        _, data = imap.uid("search", None, "UNSEEN")
        for uid in data[0].split():
            _, msg_data = imap.uid("fetch", uid, "(BODY.PEEK[])")
            raw = next(part[1] for part in msg_data if isinstance(part, tuple))
            try:
                result = handle_email(raw)
                log.info("처리: uid=%s → %s", uid.decode(), {k: result.get(k) for k in ("document_id", "status", "order_id")})
            except Exception as e:   # 한 메일 실패가 폴러를 멈추지 않게
                log.exception("처리 실패: uid=%s", uid.decode())
                result = {"error": f"{type(e).__name__}: {e}"}
            imap.uid("store", uid, "+FLAGS", "(\\Seen)")
            results.append({"uid": uid.decode()} | result)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    if not (settings.mail_address and settings.mail_app_password):
        raise SystemExit("MAIL_ADDRESS, MAIL_APP_PASSWORD를 .env에 설정하세요")
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
