"""Vercel Cron — 매일 22:00 KST 저녁 리마인더."""
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
KST = ZoneInfo("Asia/Seoul")

app = Flask(__name__)


@app.route("/api/cron_evening", methods=["GET"])
def cron():
    auth = request.headers.get("Authorization", "")
    secret = os.environ.get("CRON_SECRET", "")
    if secret and auth != f"Bearer {secret}":
        return jsonify({"error": "Unauthorized"}), 401

    now = datetime.now(KST)
    today = (now - timedelta(days=1)).strftime("%Y-%m-%d") if now.hour < 2 else now.strftime("%Y-%m-%d")

    if db.is_cron_done("evening", today):
        return jsonify({"ok": True, "message": f"already sent for {today}"})

    users = db.get_all_users()
    if not users:
        return jsonify({"ok": True, "message": "no users"})

    results = dc.get_user_results(today, users, timeout=10)
    results.sort(key=lambda x: x[2], reverse=True)

    short_list = [(did, gh_name, cnt) for did, gh_name, cnt in results if cnt < gh.MIN_COMMITS]
    done_list  = [(did, gh_name, cnt) for did, gh_name, cnt in results if cnt >= gh.MIN_COMMITS]

    rows = []
    if short_list:
        mentions = " ".join(f"<@{did}>" for did, _, _ in short_list)
        if len(short_list) == len(results):
            rows.append(f"아니 {mentions} 다들 지금 뭐하고 계신 거예요?? 😤 자정까지 **2시간** 밖에 안 남았다고요!!\n")
        else:
            rows.append(f"{mentions} 저기요... 혹시 오늘 커밋 잊으신 거 아닌가요? 🙄 자정까지 **2시간** 남았어요 얼른요!!\n")
        for did, gh_name, cnt in short_list:
            remaining = gh.MIN_COMMITS - cnt
            rows.append(f"😱 <@{did}> `{gh_name}` — {cnt}개 완료 (아직 **{remaining}개** 더 해야 해요!!)")
    else:
        rows.append("세상에… 다들 미리 다 하셨어요?? 😭✨ 오늘 전원 조기 달성!! 이런 날도 있군요!!\n")

    if done_list:
        if short_list:
            rows.append("\n이미 끝내신 분들 👏")
        for did, gh_name, cnt in done_list:
            rows.append(f"✅ <@{did}> `{gh_name}` — {cnt}개 🔥")

    color = 0xFF4500 if short_list else 0x51CF66
    title = "🚨 자정까지 2시간!! 아직 안 끝난 분 있어요!!" if short_list else "🎊 오늘도 전원 달성!! 완벽해요!!"
    embed = {
        "title": title,
        "description": "\n".join(rows),
        "color": color,
        "footer": {"text": f"자정 집계까지 2시간 남았습니다 • {today}"},
    }

    resp = requests.post(
        DISCORD_WEBHOOK_URL,
        data=json.dumps({"embeds": [embed]}),
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()
    db.mark_cron_done("evening", today)
    return jsonify({"ok": True, "short": len(short_list), "done": len(done_list)})
