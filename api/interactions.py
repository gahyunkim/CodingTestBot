import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

import database as db
import github_api as gh

load_dotenv()

app = Flask(__name__)

DISCORD_PUBLIC_KEY = os.environ["DISCORD_PUBLIC_KEY"]
DISCORD_APPLICATION_ID = os.environ["DISCORD_APPLICATION_ID"]
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
FINE_AMOUNT = int(os.environ.get("FINE_AMOUNT", "1000"))
KST = ZoneInfo("Asia/Seoul")


# ── 서명 검증 ─────────────────────────────────────────────────────


def verify_signature() -> bool:
    sig = request.headers.get("X-Signature-Ed25519", "")
    ts = request.headers.get("X-Signature-Timestamp", "")
    try:
        VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY)).verify(
            ts.encode() + request.data, bytes.fromhex(sig)
        )
        return True
    except Exception:
        return False


# ── Embed 헬퍼 ────────────────────────────────────────────────────


def embed(title: str, description: str = "", color: int = 0x339AF0, fields: list | None = None) -> dict:
    e: dict = {"title": title, "color": color}
    if description:
        e["description"] = description
    if fields:
        e["fields"] = fields
    return e


def respond(embeds: list[dict], ephemeral: bool = False) -> dict:
    data: dict = {"embeds": embeds}
    if ephemeral:
        data["flags"] = 64
    return {"type": 4, "data": data}


def followup(token: str, embeds: list[dict]) -> None:
    requests.post(
        f"https://discord.com/api/v10/webhooks/{DISCORD_APPLICATION_ID}/{token}",
        json={"embeds": embeds},
        timeout=10,
    )


# ── 사용자 정보 추출 ──────────────────────────────────────────────


def user_info(interaction: dict) -> tuple[str, str]:
    u = interaction.get("member", {}).get("user") or interaction.get("user", {})
    return u["id"], u.get("global_name") or u.get("username", "")


def is_admin(interaction: dict) -> bool:
    perms = interaction.get("member", {}).get("permissions", "0")
    return bool(int(perms) & 8)


def opt(interaction: dict, name: str, default=None):
    for o in interaction.get("data", {}).get("options", []):
        if o["name"] == name:
            return o["value"]
    return default


# ── 라우트 ────────────────────────────────────────────────────────


@app.route("/api/interactions", methods=["POST"])
def interactions():
    if not verify_signature():
        abort(401)

    body = request.json

    if body["type"] == 1:
        return jsonify({"type": 1})

    if body["type"] == 2:
        return jsonify(handle_command(body))

    return jsonify({"type": 1})


# ── 커맨드 디스패처 ───────────────────────────────────────────────


def handle_command(interaction: dict) -> dict:
    name = interaction["data"]["name"]
    handlers = {
        "안내": cmd_안내,
        "등록": cmd_등록,
        "레포등록": cmd_레포등록,
        "레포삭제": cmd_레포삭제,
        "내레포": cmd_내레포,
        "내정보": cmd_내정보,
        "오늘현황": cmd_오늘현황,
        "벌금": cmd_벌금,
        "벌금납부": cmd_벌금납부,
        "강제집계": cmd_강제집계,
        "도움말": cmd_도움말,
    }
    handler = handlers.get(name)
    if handler:
        return handler(interaction)
    return respond([embed("❓ 알 수 없는 명령어", color=0xFF6B6B)])


# ── 개별 커맨드 ───────────────────────────────────────────────────


def cmd_안내(interaction: dict) -> dict:
    webhook_guide = (
        f"GitHub 레포 → Settings → Webhooks → Add webhook\n"
        f"• Payload URL: `{DISCORD_WEBHOOK_URL}/github`\n"
        f"• Content type: `application/json`\n"
        f"• Events: `Just the push event`"
        if DISCORD_WEBHOOK_URL
        else "관리자에게 Discord 웹훅 URL을 받아 GitHub 레포 Settings → Webhooks에 등록하세요."
    )
    fields = [
        {"name": "1️⃣ GitHub 계정 등록", "value": "`/등록 <GitHub아이디>`", "inline": False},
        {"name": "2️⃣ 감시할 레포 등록", "value": "`/레포등록 owner/repo`", "inline": False},
        {"name": "3️⃣ GitHub 레포에 Discord 웹훅 연결", "value": webhook_guide, "inline": False},
        {"name": "📖 전체 명령어", "value": "`/도움말`", "inline": False},
    ]
    e = embed(
        "👋 커밋 벌금봇 사용 안내",
        f"하루 **{gh.MIN_COMMITS}개 이상** 커밋하지 않으면 **{FINE_AMOUNT:,}원** 벌금이 부과됩니다!",
        color=0x845EF7,
        fields=fields,
    )
    return respond([e], ephemeral=True)


def cmd_등록(interaction: dict) -> dict:
    user_id, display_name = user_info(interaction)
    github_username = opt(interaction, "github_username")
    db.register_user(user_id, github_username, display_name)
    return respond([embed(
        "✅ 등록 완료",
        f"<@{user_id}> → GitHub `{github_username}` 연결됐습니다.",
        color=0x51CF66,
    )])


def cmd_레포등록(interaction: dict) -> dict:
    user_id, _ = user_info(interaction)
    repo = opt(interaction, "repo", "")
    if "/" not in repo:
        return respond([embed("❌ 형식 오류", "`owner/repo-name` 형식으로 입력해주세요.", color=0xFF6B6B)], ephemeral=True)
    db.add_repo(user_id, repo)
    return respond([embed("✅ 레포 등록 완료", f"`{repo}` 가 등록됐습니다.", color=0x51CF66)])


def cmd_레포삭제(interaction: dict) -> dict:
    user_id, _ = user_info(interaction)
    repo = opt(interaction, "repo", "")
    db.remove_repo(user_id, repo)
    return respond([embed("🗑️ 레포 삭제 완료", f"`{repo}` 를 삭제했습니다.", color=0xFFD43B)])


def cmd_내레포(interaction: dict) -> dict:
    user_id, display_name = user_info(interaction)
    repos = db.get_repos(user_id)
    if not repos:
        return respond([embed(
            "📁 등록된 레포 없음",
            "`/레포등록 owner/repo` 로 추가하면 해당 레포 커밋만 집계됩니다.\n등록 없이는 전체 GitHub 활동을 집계합니다.",
        )], ephemeral=True)
    return respond([embed(
        f"📁 {display_name}의 등록 레포",
        "\n".join(f"• `{r}`" for r in repos),
    )])


def cmd_내정보(interaction: dict) -> dict:
    user_id, display_name = user_info(interaction)
    row = db.get_user_by_discord(user_id)
    if not row:
        return respond([embed("❌ 미등록", "`/등록 <GitHub 아이디>`로 먼저 등록해주세요.", color=0xFF6B6B)], ephemeral=True)

    github_username = row["github_username"]
    today = datetime.now(KST).strftime("%Y-%m-%d")
    repos = db.get_repos(user_id)
    count = gh.get_commit_count(repos, github_username, today)
    total_fine = db.get_total_fine(user_id)
    status = "✅ 달성" if count >= gh.MIN_COMMITS else f"❌ {gh.MIN_COMMITS - count}개 부족"

    return respond([embed(
        f"👤 {display_name}",
        color=0x339AF0,
        fields=[
            {"name": "GitHub", "value": f"`{github_username}`", "inline": True},
            {"name": f"오늘 커밋 ({today})", "value": f"{count}개  {status}", "inline": True},
            {"name": "미납 벌금", "value": f"{total_fine:,}원", "inline": True},
        ],
    )])


def cmd_오늘현황(interaction: dict) -> dict:
    users = db.get_all_users()
    if not users:
        return respond([embed("📅 등록된 사용자 없음", color=0xFF6B6B)], ephemeral=True)

    today = datetime.now(KST).strftime("%Y-%m-%d")
    results = gh.check_all_users(users, db.get_repos, today)
    results.sort(key=lambda x: x[2], reverse=True)

    rows = [
        f"{'✅' if cnt >= gh.MIN_COMMITS else '❌'} <@{did}> `{gh_name}` — {cnt}개"
        for did, gh_name, cnt in results
    ]
    return respond([embed(
        f"📅 {today} 커밋 현황",
        "\n".join(rows),
        color=0x339AF0,
    )])


def cmd_벌금(interaction: dict) -> dict:
    summary = db.get_all_fines_summary()
    if not summary:
        return respond([embed("💰 등록된 사용자 없음", color=0xFF6B6B)], ephemeral=True)
    rows = [
        f"{'💸' if total > 0 else '😇'} <@{did}> `{gh_name}` — {total:,}원"
        for did, _, gh_name, total in summary
    ]
    return respond([embed("💰 벌금 현황 (미납)", "\n".join(rows), color=0xFFD43B)])


def cmd_벌금납부(interaction: dict) -> dict:
    if not is_admin(interaction):
        return respond([embed("❌ 관리자 권한 필요", color=0xFF6B6B)], ephemeral=True)

    member_id = opt(interaction, "member")
    total = db.get_total_fine(member_id)
    if total == 0:
        return respond([embed("ℹ️ 미납 벌금 없음", f"<@{member_id}>의 미납 벌금이 없습니다.", color=0x339AF0)], ephemeral=True)

    db.pay_fines(member_id)
    return respond([embed(
        "✅ 납부 완료",
        f"<@{member_id}>의 미납 벌금 {total:,}원이 납부 처리됐습니다.",
        color=0x51CF66,
    )])


def cmd_강제집계(interaction: dict) -> dict:
    if not is_admin(interaction):
        return respond([embed("❌ 관리자 권한 필요", color=0xFF6B6B)], ephemeral=True)

    date = opt(interaction, "date") or datetime.now(KST).strftime("%Y-%m-%d")
    users = db.get_all_users()
    if not users:
        return respond([embed("ℹ️ 등록된 사용자 없음", color=0xFF6B6B)], ephemeral=True)

    results = gh.check_all_users(users, db.get_repos, date)

    fine_list, safe_list = [], []
    for discord_id, github_username, count in results:
        if count < gh.MIN_COMMITS:
            db.add_fine(discord_id, FINE_AMOUNT, f"{date} 커밋 {count}개 ({gh.MIN_COMMITS}개 미달)", date)
            fine_list.append((discord_id, github_username, count))
        else:
            safe_list.append((discord_id, github_username, count))

    result_embed = _build_daily_embed(date, fine_list, safe_list)

    if DISCORD_WEBHOOK_URL:
        followup_data = json.dumps({"embeds": [result_embed]})
        requests.post(DISCORD_WEBHOOK_URL, data=followup_data, headers={"Content-Type": "application/json"}, timeout=10)

    return respond([embed("✅ 강제 집계 완료", f"`{date}` 결산이 완료됐습니다. 채널을 확인하세요.", color=0x51CF66)])


def cmd_도움말(interaction: dict) -> dict:
    cmds = [
        ("/등록 <GitHub ID>", "내 GitHub 계정 등록"),
        ("/레포등록 owner/repo", "집계할 레포 추가"),
        ("/레포삭제 owner/repo", "등록된 레포 제거"),
        ("/내레포", "내가 등록한 레포 목록"),
        ("/내정보", "오늘 커밋 수 & 벌금 확인"),
        ("/오늘현황", "전체 멤버 오늘 커밋 현황"),
        ("/벌금", "전체 미납 벌금 현황"),
        ("/벌금납부 @유저", "벌금 납부 처리 (관리자)"),
        ("/강제집계 [날짜]", "수동 일일 결산 (관리자)"),
    ]
    fields = [{"name": f"`{cmd}`", "value": desc, "inline": False} for cmd, desc in cmds]
    return respond([embed("📖 명령어 도움말", color=0x845EF7, fields=fields)], ephemeral=True)


# ── 공통 Embed 빌더 ───────────────────────────────────────────────


def _build_daily_embed(date: str, fine_list: list, safe_list: list) -> dict:
    color = 0xFF6B6B if fine_list else 0x51CF66
    fields = []
    if safe_list:
        fields.append({
            "name": "목표 달성 🎉",
            "value": "\n".join(f"✅ <@{did}> `{gh_name}` — {cnt}개" for did, gh_name, cnt in safe_list),
            "inline": False,
        })
    if fine_list:
        fields.append({
            "name": f"벌금 {FINE_AMOUNT:,}원 💸",
            "value": "\n".join(
                f"❌ <@{did}> `{gh_name}` — {cnt}개 → 벌금 {FINE_AMOUNT:,}원"
                for did, gh_name, cnt in fine_list
            ),
            "inline": False,
        })
    return {
        "title": f"📊 {date} 일일 커밋 결산",
        "color": color,
        "fields": fields,
        "footer": {"text": f"하루 최소 {gh.MIN_COMMITS}개 커밋 목표"},
    }
