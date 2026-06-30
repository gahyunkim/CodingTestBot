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
import discord_commits as dc
import github_api as gh  # MIN_COMMITS 상수 재사용

load_dotenv()

DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"].strip()
KST = ZoneInfo("Asia/Seoul")


def run() -> None:
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")

    users = db.get_all_users()
    if not users:
        print("등록된 사용자 없음, 종료")
        return

    results = dc.get_user_results(today, users)
    results.sort(key=lambda x: x[2], reverse=True)

    short_list = [(did, gh_name, cnt) for did, gh_name, cnt in results if cnt < gh.MIN_COMMITS]
    done_list  = [(did, gh_name, cnt) for did, gh_name, cnt in results if cnt >= gh.MIN_COMMITS]

    rows = []
    if short_list:
        mentions = " ".join(f"<@{did}>" for did, _, _ in short_list)
        rows.append(f"**{mentions}** 아직 목표 미달이에요! 자정까지 2시간 남았습니다.\n")
        for did, gh_name, cnt in short_list:
            rows.append(f"❌ <@{did}> `{gh_name}` — {cnt}/{gh.MIN_COMMITS}개")
    else:
        rows.append("🎉 오늘은 모든 멤버가 목표를 달성했어요!")

    if done_list:
        rows.append("")
        for did, gh_name, cnt in done_list:
            rows.append(f"✅ <@{did}> `{gh_name}` — {cnt}개")

    color = 0xFF9500 if short_list else 0x51CF66
    embed = {
        "title": "⏰ 22:00 커밋 현황",
        "description": "\n".join(rows),
        "color": color,
        "footer": {"text": f"자정 집계까지 2시간 남았습니다 ({today})"},
    }

    resp = requests.post(
        DISCORD_WEBHOOK_URL,
        data=json.dumps({"embeds": [embed]}),
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    print(f"리마인더 전송 완료 — 미달 {len(short_list)}명 / 달성 {len(done_list)}명")


if __name__ == "__main__":
    run()
