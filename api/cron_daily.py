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
    # cron이 지연돼 자정을 넘겨 실행됐을 경우 전날 날짜 사용
    default_date = (now - timedelta(days=1)).strftime("%Y-%m-%d") if now.hour < 6 else now.strftime("%Y-%m-%d")
    date = request.args.get("date") or default_date
    users = db.get_all_users()
    if not users:
        return jsonify({"ok": True, "message": "no users"})

    results = dc.get_user_results(date, users)

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
    return jsonify({"ok": True, "fined": len(fine_list), "safe": len(safe_list)})
