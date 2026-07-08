"""Vercel Cron — 매일 23:59 KST 일일 커밋 집계."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request

import database as db
import discord_commits as dc
import github_api as gh  # MIN_COMMITS 상수 재사용

load_dotenv()

DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"].strip()
FINE_AMOUNT = int(os.environ.get("FINE_AMOUNT", "1000"))
KST = ZoneInfo("Asia/Seoul")

app = Flask(__name__)


@app.route("/api/cron_daily", methods=["GET"])
def cron():
    auth = request.headers.get("Authorization", "")
    secret = os.environ.get("CRON_SECRET", "")
    if secret and auth != f"Bearer {secret}":
        return jsonify({"error": "Unauthorized"}), 401

    now = datetime.now(KST)
    default_date = (now - timedelta(days=1)).strftime("%Y-%m-%d") if now.hour < 2 else now.strftime("%Y-%m-%d")
    date = request.args.get("date") or default_date

    if not request.args.get("date") and db.is_cron_done("daily", date):
        return jsonify({"ok": True, "message": f"already processed {date}"})

    users = db.get_all_users()
    if not users:
        return jsonify({"ok": True, "message": "no users"})

    results = dc.get_user_results(date, users, timeout=10)

    fine_list, safe_list = [], []
    for discord_id, github_username, count in results:
        if count < gh.MIN_COMMITS:
            db.add_fine(
                discord_id, FINE_AMOUNT,
                f"{date} 커밋 {count}개 ({gh.MIN_COMMITS}개 미달)", date,
            )
            fine_list.append((discord_id, github_username, count))
        else:
            safe_list.append((discord_id, github_username, count))

    if fine_list and safe_list:
        title = f"😬 {date} 결산 — 희비가 엇갈렸습니다"
        color = 0xFF6B6B
        desc = "살아남은 자와 그렇지 못한 자… 오늘의 결과를 발표합니다."
    elif fine_list:
        title = f"💀 {date} 결산 — 오늘의 희생자 발표"
        color = 0xCC0000
        desc = "결국… 도망치지 못하셨군요. 벌금을 받아가세요. 😈"
    else:
        title = f"🏆 {date} 결산 — 전원 클리어!!"
        color = 0x51CF66
        desc = "믿을 수가 없어요… 오늘 **전원이 해냈습니다!!** 🥲🎉 이게 가능한 일이에요??"

    embed = {
        "title": title,
        "description": desc,
        "color": color,
        "fields": [],
        "footer": {"text": f"하루 최소 {gh.MIN_COMMITS}개 커밋 목표 • {date}"},
    }
    if safe_list:
        embed["fields"].append({
            "name": "🌟 오늘의 생존자",
            "value": "\n".join(f"✅ <@{did}> `{gh_name}` — {cnt}개 완료 🔥" for did, gh_name, cnt in safe_list),
            "inline": False,
        })
    if fine_list:
        embed["fields"].append({
            "name": f"💸 오늘의 희생자 (벌금 {FINE_AMOUNT:,}원)",
            "value": "\n".join(
                f"❌ <@{did}> `{gh_name}` — {cnt}개... → {FINE_AMOUNT:,}원 ㅠㅠ"
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
    if not request.args.get("date"):
        db.mark_cron_done("daily", date)
    return jsonify({"ok": True, "fined": len(fine_list), "safe": len(safe_list)})
