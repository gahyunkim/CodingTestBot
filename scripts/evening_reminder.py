"""매일 21:00 KST에 실행 — 커밋 미달 유저에게 Discord 채널 경고."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

import database as db
import github_api as gh

load_dotenv()

DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
KST = ZoneInfo("Asia/Seoul")


def run() -> None:
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")

    users = db.get_all_users()
    if not users:
        print("등록된 사용자 없음, 종료")
        return

    user_tokens = db.get_user_tokens()
    results = gh.check_all_users(users, db.get_repos, today, user_tokens=user_tokens)
    short_list = [(did, gh_name, cnt) for did, gh_name, cnt in results if cnt < gh.MIN_COMMITS]

    if not short_list:
        print("모든 멤버 목표 달성, 알림 불필요")
        return

    mentions = " ".join(f"<@{did}>" for did, _, _ in short_list)
    rows = "\n".join(
        f"• <@{did}> `{gh_name}` — {cnt}/{gh.MIN_COMMITS}개"
        for did, gh_name, cnt in short_list
    )

    embed = {
        "title": "⏰ 저녁 커밋 리마인더",
        "description": f"{mentions}\n\n아직 오늘 목표를 달성하지 못했어요!\n\n{rows}",
        "color": 0xFF9500,
        "footer": {"text": f"자정까지 약 3시간 남았습니다 ({today})"},
    }

    resp = requests.post(
        DISCORD_WEBHOOK_URL,
        data=json.dumps({"embeds": [embed]}),
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    print(f"리마인더 전송 완료 — {len(short_list)}명 대상")


if __name__ == "__main__":
    run()
