import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

KST = ZoneInfo("Asia/Seoul")
MIN_COMMITS = 2


def _headers(user_token: str | None = None) -> dict:
    h = {"Accept": "application/vnd.github.v3+json"}
    token = user_token or os.environ.get("GH_TOKEN", "")
    if token:
        h["Authorization"] = f"token {token}"
    return h


def get_commit_count(
    repos: list[str],
    github_username: str,
    date: str,
    user_token: str | None = None,
) -> int:
    kst_start = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=KST)
    utc_start = kst_start.astimezone(timezone.utc)
    utc_end = (kst_start + timedelta(days=1)).astimezone(timezone.utc)
    hdrs = _headers(user_token)

    if repos:
        count = 0
        for repo in repos:
            resp = requests.get(
                f"https://api.github.com/repos/{repo}/commits",
                params={
                    "author": github_username,
                    "since": utc_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "until": utc_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "per_page": 100,
                },
                headers=hdrs,
                timeout=10,
            )
            if resp.status_code == 200:
                count += len(resp.json())
        return count

    resp = requests.get(
        f"https://api.github.com/users/{github_username}/events",
        params={"per_page": 100},
        headers=hdrs,
        timeout=10,
    )
    if resp.status_code != 200:
        return 0

    count = 0
    for event in resp.json():
        if event.get("type") != "PushEvent":
            continue
        created_at = datetime.strptime(event["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if utc_start <= created_at < utc_end:
            count += len(event.get("payload", {}).get("commits", []))
    return count


def check_all_users(
    users: list[tuple[str, str, str]],
    get_repos_fn,
    date: str,
    user_tokens: dict[str, str | None] | None = None,
) -> list[tuple[str, str, int]]:
    """users 전체의 커밋 수를 병렬로 조회한다.
    user_tokens: {discord_id: github_token} — 없으면 공용 GH_TOKEN 사용
    """
    def fetch(user_tuple):
        discord_id, github_username, _ = user_tuple
        repos = get_repos_fn(discord_id)
        token = (user_tokens or {}).get(discord_id)
        count = get_commit_count(repos, github_username, date, user_token=token)
        return discord_id, github_username, count

    results = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(fetch, u): u for u in users}
        for future in as_completed(futures):
            results.append(future.result())
    return results
