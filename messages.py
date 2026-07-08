"""Discord 메시지 생성 헬퍼 — 칭찬/비난 문구 모음."""
import random

# github_username → (목표 회사, 칭찬 문구 pool)
_PRAISE: dict[str, tuple[str, list[str]]] = {
    "Byesol": ("현대오토에버", [
        "와!!!!! 이대로라면 현대오토에버 가겠는데요??",
        "또 이걸 풀다니. 오늘도 성실하셨군요 🙌",
        "또 성실한 하루를 살아버렸어. 현대오토에버 각이에요.",
        "매일 이러면 현대오토에버가 먼저 연락할 것 같은데요??",
        "현대오토에버 면접관들이 알면 좋아하겠다 진짜로.",
        "오늘 또 성실하게 사셨군요. 이러다 현대오토에버 합격각 나오겠는데요?",
    ]),
    "gahyunkim": ("현대모비스", [
        "와!!!!! 이대로라면 현대모비스 확정인데요??",
        "또 이걸 풀다니. 오늘도 성실하셨군요 🙌",
        "또 성실한 하루를 살아버렸어. 현대모비스 각이에요.",
        "이 성실함이면 현대모비스가 먼저 DM 보내겠는데요??",
        "현대모비스 면접관들이 알면 좋아하겠다 진짜로.",
        "오늘 또 성실하게 사셨군요. 이러다 현대모비스 합격각 나오겠는데요?",
    ]),
}

_GENERIC_PRAISE = [
    "오늘도 성실하셨군요! 🔥",
    "또 성실한 하루를 살아버렸어. 대단해요 진짜로.",
    "꾸준함이 곧 실력이에요. 오늘도 수고하셨습니다!",
]


def praise_line(github_username: str, commit_count: int) -> str:
    """달성자에 대한 칭찬 한 줄 반환."""
    bonus = f" ({commit_count}개나?? 미쳤다 진짜로 🔥🔥)" if commit_count >= 5 else ""
    if github_username in _PRAISE:
        _, lines = _PRAISE[github_username]
        return random.choice(lines) + bonus
    return random.choice(_GENERIC_PRAISE) + bonus


def company_of(github_username: str) -> str:
    """목표 회사명 반환. 없으면 빈 문자열."""
    if github_username in _PRAISE:
        return _PRAISE[github_username][0]
    return ""


def done_line(did: str, gh_name: str, cnt: int) -> str:
    """달성자 한 줄 + 칭찬 멘트."""
    praise = praise_line(gh_name, cnt)
    return f"✅ <@{did}> `{gh_name}` — {cnt}개 🔥\n> _{praise}_"


def short_line(did: str, gh_name: str, cnt: int, min_commits: int) -> str:
    """미달자 한 줄."""
    remaining = min_commits - cnt
    return f"❌ <@{did}> `{gh_name}` — {cnt}개 (앞으로 **{remaining}개** 더요!!)"
