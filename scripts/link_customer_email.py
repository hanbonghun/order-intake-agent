"""데모용: 거래처의 등록 메일을 실제 주소로 바꾼다 (시드 거래처 메일은 가짜 도메인이라 실제로 보낼 수 없음).

    uv run python -m scripts.link_customer_email --customer 1 --email me@example.com

평가 실행(evals.run)은 DB를 시드 상태로 초기화하므로 그 뒤에는 다시 실행해야 한다.
"""
import argparse

from app.db.session import get_conn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--customer", type=int, required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    with get_conn() as conn:
        row = conn.execute("UPDATE customers SET email = %s WHERE id = %s RETURNING id, name, email",
                           (args.email.strip().lower(), args.customer)).fetchone()
    print(row or f"거래처 {args.customer} 없음")


if __name__ == "__main__":
    main()
