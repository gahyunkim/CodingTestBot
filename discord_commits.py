"""Discord 채널 GitHub 웹훅 메시지에서 날짜별 커밋 수 집계."""
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

MIN_COMMITS = 2
KST = ZoneInfo("Asia/Seoul")
_DISCORD_EPOCH_MS = 1420070400000  # 2015-01-01T00:00:00Z


def _snowflake(dt: datetime) -> str:
    ms = int(dt.timestamp() * 1000) - _DISCORD_EPOCH_MS
    return str(max(ms, 0) << 22)


def get_commit_counts(date: str) -> dict[str, int]:
    """
    date(YYYY-MM-DD, KST 기준) 에 채널에 올라온 GitHub 웹훅 메시지를 파싱해
    {github_username: commit_count} 반환.
    DISCORD_BOT_TOKEN 또는 DISCORD_COMMITS_CHANNEL_ID 미설정 시 빈 dict.
    """
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    channel_id = os.environ.get("DISCORD_COMMITS_CHANNEL_ID", "")
    if not token or not channel_id:
        return {}

    d = datetime.strptime(date, "%Y-%m-%d")
    day_start = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=KST)
    day_end   = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=KST)

    headers = {"Authorization": f"Bot {token}"}
    counts: dict[str, int] = {}
    last_id = _snowflake(day_start)

    while True:
        try:
            resp = requests.get(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers=headers,
                params={"limit": 100, "after": last_id},
                timeout=2,
            )
        except Exception as e:
            print(f"[discord_commits] request failed: {e}")
            return counts
        if not resp.ok:
            print(f"[discord_commits] Discord API error {resp.status_code}: {resp.text}")
            return counts
        messages: list[dict] = resp.json()
        if not messages:
            break

        for msg in messages:
            # GitHub 웹훅 메시지만 처리
            if not msg.get("webhook_id"):
                continue
            if msg.get("author", {}).get("username") != "GitHub":
                continue

            msg_time = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00"))
            if msg_time > day_end:
                return counts

            # Discord GitHub 통합은 embed의 description에 커밋 목록을 넣음
            # 형식: [`SHA`](url) commit message - author
            for embed in msg.get("embeds", []):
                description = embed.get("description", "")
                for line in description.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    idx = line.rfind(" - ")
                    if idx != -1:
                        author = line[idx + 3:].strip()
                        if author:
                            counts[author] = counts.get(author, 0) + 1

        if len(messages) < 100:
            break
        last_id = messages[-1]["id"]

    return counts


def get_user_results(date: str, users: list) -> list[tuple[str, str, int]]:
    """[(discord_id, github_username, commit_count)] 반환."""
    counts = get_commit_counts(date)
    return [
        (discord_id, github_username, counts.get(github_username, 0))
        for discord_id, github_username, *_ in users
    ]
