import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

_client: Client | None = None


def _db() -> Client:
    global _client
    if _client is None:
        _client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )
    return _client


def register_user(discord_id: str, github_username: str, discord_name: str) -> None:
    _db().table("users").upsert(
        {"discord_id": discord_id, "github_username": github_username, "discord_name": discord_name}
    ).execute()


def get_user_by_discord(discord_id: str) -> dict | None:
    res = _db().table("users").select("*").eq("discord_id", discord_id).maybe_single().execute()
    return res.data


def get_all_users() -> list[tuple[str, str, str]]:
    res = _db().table("users").select("discord_id, github_username, discord_name").execute()
    return [(r["discord_id"], r["github_username"], r["discord_name"]) for r in (res.data or [])]


def add_fine(discord_id: str, amount: int, reason: str, date: str) -> None:
    _db().table("fines").insert(
        {"discord_id": discord_id, "amount": amount, "reason": reason, "date": date, "paid": False}
    ).execute()


def get_total_fine(discord_id: str) -> int:
    res = _db().table("fines").select("amount").eq("discord_id", discord_id).eq("paid", False).execute()
    return sum(r["amount"] for r in (res.data or []))


def get_all_fines_summary() -> list[tuple[str, str, str, int]]:
    users = _db().table("users").select("discord_id, discord_name, github_username").execute().data or []
    fines = _db().table("fines").select("discord_id, amount").eq("paid", False).execute().data or []

    totals: dict[str, int] = {}
    for f in fines:
        totals[f["discord_id"]] = totals.get(f["discord_id"], 0) + f["amount"]

    result = [
        (u["discord_id"], u["discord_name"], u["github_username"], totals.get(u["discord_id"], 0))
        for u in users
    ]
    result.sort(key=lambda x: x[3], reverse=True)
    return result


def add_repo(discord_id: str, repo: str) -> None:
    _db().table("user_repos").upsert({"discord_id": discord_id, "repo": repo}).execute()


def remove_repo(discord_id: str, repo: str) -> None:
    _db().table("user_repos").delete().eq("discord_id", discord_id).eq("repo", repo).execute()


def get_repos(discord_id: str) -> list[str]:
    res = _db().table("user_repos").select("repo").eq("discord_id", discord_id).execute()
    return [r["repo"] for r in (res.data or [])]


def pay_fines(discord_id: str) -> None:
    _db().table("fines").update({"paid": True}).eq("discord_id", discord_id).eq("paid", False).execute()


def get_fine_history(discord_id: str, limit: int = 20) -> list[dict]:
    res = (
        _db().table("fines")
        .select("amount, reason, date, paid")
        .eq("discord_id", discord_id)
        .order("date", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def get_weekly_fines(week_start: str) -> list[dict]:
    res = (
        _db().table("fines")
        .select("discord_id, amount, date, paid")
        .gte("date", week_start)
        .execute()
    )
    return res.data or []
