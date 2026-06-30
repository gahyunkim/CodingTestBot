"""GitHub Actions cron (23:59 KST)에서 실행되는 일일 커밋 집계 스크립트."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

import database as db
import discord_commits as dc
import github_api as gh  # MIN_COMMITS 상수 재사용

load_dotenv()

DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"].strip()
FINE_AMOUNT = int(os.environ.get("FINE_AMOUNT", "1000"))
KST = ZoneInfo("Asia/Seoul")


def run(date: str) -> None:
    users = db.get_all_users()
    if not users:
        print("등록된 사용자 없음, 종료")
        return

    results = dc.get_user_results(date, users)

    fine_list, safe_list = [], []
    for discord_id, github_username, count in results:
        if count < gh.MIN_COMMITS:
            db.add_fine(
                discord_id, FINE_AMOUNT,
                f"{date} 커밋 {count}개 ({gh.MIN_COMMITS}개 미달)", date,
            )
            fine_list.append((discord_id, github_username, count))
            print(f"[벌금] {github_username} — {count}개")
        else:
            safe_list.append((discord_id, github_username, count))
            print(f"[달성] {github_username} — {count}개")

    embed = {
        "title": f"📊 {date} 일일 커밋 결산",
        "color": 0xFF6B6B if fine_list else 0x51CF66,
        "fields": [],
        "footer": {"text": f"하루 최소 {gh.MIN_COMMITS}개 커밋 목표"},
    }
    if safe_list:
        embed["fields"].append({
            "name": "목표 달성 🎉",
            "value": "\n".join(f"✅ <@{did}> `{gh_name}` — {cnt}개" for did, gh_name, cnt in safe_list),
            "inline": False,
        })
    if fine_list:
        embed["fields"].append({
            "name": f"벌금 {FINE_AMOUNT:,}원 💸",
            "value": "\n".join(
                f"❌ <@{did}> `{gh_name}` — {cnt}개 → 벌금 {FINE_AMOUNT:,}원"
                for did, gh_name, cnt in fine_list
            ),
            "inline": False,
        })

    resp = requests.post(
        DISCORD_WEBHOOK_URL,
        data=json.dumps({"embeds": [embed]}),
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    print(f"Discord 전송 완료 ({resp.status_code})")


if __name__ == "__main__":
    today = datetime.now(KST).strftime("%Y-%m-%d")
    target_date = sys.argv[1] if len(sys.argv) > 1 else today
    print(f"[daily_check] {target_date} 집계 시작")
    run(target_date)
