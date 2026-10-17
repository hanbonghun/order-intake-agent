"""IMAP 폴러: 받은편지함의 읽지 않은 메일을 가져와 수신 처리(handle_email)에 넘긴다.

    uv run python -m app.mail.imap           # 계속 폴링
    uv run python -m app.mail.imap --once    # 한 번만
"""
import argparse
import imaplib
import logging
import time
from datetime import datetime, timezone
from email.utils import parseaddr

from app.config import settings
from app.ingest.handler import handle_email

log = logging.getLogger("imap")


def _accepted_senders() -> set[str]:
    return {a.strip().lower() for a in settings.mail_accept_from.split(",") if a.strip()}


def _eligible(imap, uid: bytes, since: datetime | None) -> bool:
    """본문을 읽기 전에 헤더·도착 시각만 보고 처리 대상인지 판단한다.
    대상이 아닌 메일은 본문을 가져오지도, 읽음 표시하지도 않는다 (개인 메일함에 연결된 경우의 안전장치)."""
    _, data = imap.uid("fetch", uid, "(INTERNALDATE BODY.PEEK[HEADER.FIELDS (FROM)])")
    meta = b" ".join(p[0] if isinstance(p, tuple) else p for p in data if p)
    if since is not None:
        arrived = imaplib.Internaldate2tuple(meta)
        if arrived is None or datetime.fromtimestamp(time.mktime(arrived), timezone.utc) < since:
            return False
    accept = _accepted_senders()
    if accept:
        header = next((p[1] for p in data if isinstance(p, tuple)), b"").decode(errors="replace")
        if parseaddr(header.split(":", 1)[-1].strip())[1].lower() not in accept:
            return False
    return True


def poll_once(since: datetime | None = None) -> list[dict]:
    """처리 대상인 안 읽은 메일을 처리한다. 가져올 때는 읽음 표시를 하지 않고(BODY.PEEK), 처리 후에 표시한다.
    처리 중 오류가 나도 읽음 표시해 같은 메일을 무한히 재시도하지 않게 한다 (문서 상태로 추적)."""
    results = []
    with imaplib.IMAP4_SSL(settings.mail_imap_host) as imap:
        imap.login(settings.mail_address, settings.mail_app_password)
        imap.select("INBOX")
        months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()   # IMAP 날짜는 영문 월 (로케일 무관)
        criteria = f"(UNSEEN SINCE {since.day:02d}-{months[since.month - 1]}-{since.year})" if since else "UNSEEN"
        _, data = imap.uid("search", None, criteria)   # 서버에서 날짜(일 단위)로 먼저 거르고, 시각은 _eligible에서
        for uid in data[0].split():
            if not _eligible(imap, uid, since):
                continue
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
    since = None if settings.mail_process_backlog else datetime.now(timezone.utc)
    log.info("폴링 시작: %s, 발신자 제한 %s", "기존 안 읽은 메일 포함" if since is None else f"{since:%H:%M:%S} 이후 도착분만",
             f"{len(_accepted_senders())}개 주소" if _accepted_senders() else "없음")
    while True:
        try:
            for r in poll_once(since):
                print(r, flush=True)
        except (imaplib.IMAP4.error, OSError):
            log.exception("IMAP 연결 실패, 다음 주기에 재시도")
        if args.once:
            break
        time.sleep(settings.mail_poll_seconds)


if __name__ == "__main__":
    main()
