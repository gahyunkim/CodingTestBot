"""Vercel Cron — 매일 22:00 KST 저녁 리마인더."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request

import database as db
import github_api as gh

load_dotenv()

DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"].strip()
KST = ZoneInfo("Asia/Seoul")

app = Flask(__name__)


@app.route("/api/cron_evening", methods=["GET"])
def cron():
    auth = request.headers.get("Authorization", "")
    secret = os.environ.get("CRON_SECRET", "")
    if secret and auth != f"Bearer {secret}":
        return jsonify({"error": "Unauthorized"}), 401

    today = datetime.now(KST).strftime("%Y-%m-%d")
    users = db.get_all_users()
    if not users:
        return jsonify({"ok": True, "message": "no users"})

    user_tokens = db.get_user_tokens()
    results = gh.check_all_users(users, db.get_repos, today, user_tokens=user_tokens)
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
    return jsonify({"ok": True, "short": len(short_list), "done": len(done_list)})
