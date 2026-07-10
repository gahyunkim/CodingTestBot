"""Discord 메시지 생성 헬퍼 — 칭찬/비난 문구 모음."""
import random

# 사람 정보: github_username → (실명, 목표 회사)  ← 씨 없이 저장, 템플릿에서 직접 붙임
_PEOPLE: dict[str, tuple[str, str]] = {
    "Byesol":    ("백승주",  "현대오토에버"),
    "gahyunkim": ("김가현", "현대모비스"),
}

# ── 2~4개 (잔잔한 감탄) ───────────────────────────────────────────
_BASE = [
    # 기업 100억 손해 스타일
    "님들 그 소식 들었어? {기업} 잠재적 영업이익이 지금 100억 마이너스래. 어케 100억이나? 잘나가는 거 아니었어? 아니 그게 정확히 말하자면 {이름}씨를 아직 고용 못 해서 발생한 기회손실이래. 아, 그건 어쩔 수 없지.",
    # 다큐멘터리 내레이션
    "오늘도 {이름}씨는 알고리즘 문제 앞에 앉았다. {n}번째 문제가 풀렸다. 화면 너머 어딘가에서 {기업} 면접관이 자신도 모르게 공고를 다시 열었다. '이런 사람 한 명 있으면 팀이 달라지는데.' 그는 오늘도 같은 생각을 했다.",
    # 코드 리뷰 대화
    "PR 리뷰어A: '{이름}씨 오늘 또 커밋 남겼네.' / 리뷰어B: '어제도 하지 않았어?' / 리뷰어A: '그제도.' / 리뷰어B: '{기업} 가려는 분이야?' / 리뷰어A: '응.' / 리뷰어B: '아 그럼 걱정 없겠다.'",
    # 주식 스타일
    "{이름}씨 주가 오늘 {n}문제 달성으로 신고가 경신. 단기 급등보다 무서운 게 이 장기 우상향임. {기업} 리서치센터 리포트: '목표주가 상향 조정. 매수 의견 유지. 장기 보유 추천.'",
    # 코테 집중력 비유
    "코테 문제 {n}개 붙잡는 집중력이 이 정도면 면접장 화이트보드 앞에서도 똑같이 나오는 거임. 시험장에서 흔들리는 사람은 평소에 안 해본 사람이고, {이름}씨는 평소에 하는 사람임. {기업} 채용담당자? 화이트보드 먼저 닦아두고 대기함.",
    # 라디오 사연
    "사연 하나 읽겠습니다. '저 {기업} 채용담당자인데요, 요즘 이상하게 한 지원자가 자꾸 생각나서요. 깃허브 보니까 오늘도 커밋 올라왔더라고요. 이런 감정이 처음이라 어떻게 해야 할지.' — {이름}씨한테 연락처 달라고 하세요. 지금 바로요.",
    # 따뜻한 메시지
    "바쁜 하루 끝에도 하셨네요. 오늘도 수고하셨습니다, {이름}씨! 💪",
]

# ── 5~9개 (호들갑 텐션 상승) ──────────────────────────────────────
_HYPE = [
    # 뉴스 속보
    "[속보] {이름}씨, 오늘 {n}문제 돌파. 현장 상황 전해드립니다. 현재 키보드에서 연기가 나고 있으며 손가락이 멈출 기미를 보이지 않고 있습니다. {기업} 채용팀에서는 긴급 회의를 소집한 것으로 알려졌습니다. 자세한 내용은 추후 업데이트 예정. 끝.",
    # 기업 실적 확장
    "아니 이거 들었어?? {기업} 2분기 실적 발표 났는데 영업이익이 예상보다 낮대. 왜?? {이름}씨를 아직도 안 뽑아서 그런 거잖아. 매일 {n}문제씩 코테 푸는 동안 {기업}는 그냥 손 놓고 있던 거임. 이제라도 전화하지.",
    # 감독-코치 대화
    "감독: '{이름}씨 오늘 몇 문제야?' / 코치: '{n}개요.' / 감독: '...' / 코치: '왜요?' / 감독: '어제도 그랬잖아.' / 코치: '그제도요.' / 감독: '이 선수 어디 뺏기기 전에 계약 얘기 먼저 해야겠는데.'",
    # 알고리즘 사고회로
    "{이름}씨 코테 푸는 방식이 있어. {n}문제 잡으면 접근법 여러 개 떠올리고 시간복잡도 먼저 따진 다음에 코드 짬. 이거 그냥 문제 하나 푸는 게 아니라 알고리즘 사고 회로 자체를 트레이닝하는 거임. 매일 이러면 면접에서 설명도 막힘 없이 나옴. {기업} 기술면접? 통과각임.",
    # 코테 근육
    "잠깐, {이름}씨 {n}문제라고?? 이거 그냥 {n}문제가 아니라 코테 근육 {n}세트 완주한 거임. 매일 나타나서 세트 채우는 사람이 실전 들어가면 어떻게 되는지 알지? {기업} 코테는 이미 워밍업 수준인 거임. 아 진짜 부럽다.",
    # 카카오톡 단톡
    "{기업}채용팀 단톡 / 담당자A: 야 이거봐 [깃허브] / 담당자B: 뭔데 / 담당자A: {이름}씨 오늘 {n}문제 / 담당자B: ??? / 담당자C: 실화임? / 담당자A: 어제도 이랬어 / 담당자B: 서류 검토 필요 없겠다 그냥 / 담당자C: 연락처 있어?",
    # 따뜻한 메시지
    "꾸준히 하시는 거 다 보이고 있어요. {이름}씨 {기업} 응원합니다! 🙌",
]

# ── 10개 이상 (완전 폭주 텐션) ────────────────────────────────────
_ULTRA = [
    # 뉴스 속보 폭주
    "[긴급속보] {이름}씨가 오늘 {n}문제를 풀었습니다. 다시 한번 말씀드립니다. {n}개입니다. 현재 코딩테스트 업계는 충격에 빠졌으며 {기업} 채용팀 전원이 비상소집된 것으로 전해지고 있습니다. 면접관 A씨는 '이런 지원자는 처음'이라며 말을 잇지 못했습니다. 오퍼 레터 초안 작성이 시작된 것으로 알려졌습니다. 계속해서 속보 전해드리겠습니다.",
    # 이사회 긴급회의
    "지금 {기업} 이사회에서 긴급 안건 상정됐대. '{이름}씨 영입 건'. 이사: '{n}문제를 하루에요?' / 대표: '예.' / 이사: '어제도요?' / 대표: '예.' / 이사: '연봉 얼마 드리면 돼요?' / 대표: 'HR팀 계산 중입니다.' / 이사: '빨리요. 경쟁사가 먼저 채가면 안 되잖아요.'",
    # 다큐멘터리 내레이션
    "오늘 {이름}씨는 {n}번째 문제를 닫았다. 화면에 'Accepted'가 떴다. 몇 초간의 침묵. 그리고 다음 문제를 열었다. 이 장면은 이후 {기업} 내부 교육 자료에 '이상적인 취준생의 하루'라는 제목으로 수록됐다. 당사자는 아직 그 사실을 모른다.",
    # 단톡방 폭주
    "{기업}채용팀방 / A: 야 {이름}씨 오늘 {n}문제임 / B: ??? 진짜? / A: 어 / C: 잠깐 {n}개?? / B: 어제 몇 개였어 / A: 어제도 많았어 / C: 이거 그냥 뽑자 / B: 동의 / A: 나도 동의 / C: 서류전형 의미 있음? {이름}씨한테? / A: 없을듯 / B: 없을듯 / C: 없을듯",
    # 교수 발표
    "잠깐 다들 조용히 해봐. {이름}씨 오늘 {n}문제 올라왔어. {n}개. 한 번이면 인상적인 거고 매일이면 레벨이 다른 거임. 이 스터디에서 하루 최다 문제가 언제인지 알아? 오늘임. {이름}씨가. {기업} 코테팀이 이 사람 찾아야 하는데 우리가 먼저 알고 있는 거잖아. 영광인 줄 알아야 해.",
    # Accepted 연속 알림 스타일
    "딩동 Accepted. 딩동 Accepted. 딩동 Accepted. ... (x{n}) / {이름}씨 오늘 알림음이 {n}번 울렸습니다. 이 소리 {기업} 면접관이 들었으면 귀 쫑긋 세웠을 텐데. 매번 틀리면 다시 잡고, 맞으면 다음 거 또 잡고. 이 루틴이 쌓이면 코테는 그냥 통과임. 오늘 진짜 수고했어.",
    # 따뜻한 메시지
    "{n}개라니… 오늘 정말 대단하세요. {이름}씨 파이팅입니다!! 🔥",
]

_BASE_GENERIC = [
    "님들 그 소식 들었어? 어느 회사 잠재적 영업이익이 지금 100억 마이너스래. 어케 100억이나? 이 분을 아직 못 뽑아서 발생한 기회손실이래. 어쩔 수 없지.",
    "오늘 {n}문제. 문제 푸는 꾸준함이 코테 근육이 되는 거임. 이 근육은 시험장 들어가서 비로소 나오는 거고.",
]
_HYPE_GENERIC = [
    "[속보] {n}문제 달성. 키보드에서 연기남. 채용팀 긴급 소집된 것으로 알려짐. 오늘 진짜 대단했어!!",
    "오늘 {n}문제는 그냥 {n}문제가 아니라 코테 사고회로 {n}세트 트레이닝한 거임. 매일 이러면 면접장에서 설명이 술술 나옴. 진짜 대단해!!",
]
_ULTRA_GENERIC = [
    "[긴급속보] {n}문제 달성. 업계 충격. 채용팀 비상소집. 오퍼 레터 초안 작성 시작. 계속 속보 전해드리겠습니다. 오늘 레전드였어. 👑🔥",
]

_PREFIX_BASE  = "와! "
_PREFIX_HYPE  = "와!!!!!!!!!! 미쳤다! 돌았다! 와!!!!\n"
_PREFIX_ULTRA = "여기요!!!!! 게더 사람들!!!!!!!!!!!!!!!!!!!! {이름}씨가 미쳤어요!!!!!!!! 코테의 신이 되려나봐요!!!!!!!!\n"


def _fmt(template: str, n: int, github_username: str) -> str:
    이름, 기업 = _PEOPLE.get(github_username, ("", ""))
    return (template
            .replace("{n}", str(n))
            .replace("{이름}", 이름)
            .replace("{기업}", 기업))


def praise_line(github_username: str, commit_count: int, used: set | None = None) -> str:
    n = commit_count
    if n >= 10:
        prefix = _PREFIX_ULTRA
        pool = _ULTRA if github_username in _PEOPLE else _ULTRA_GENERIC
    elif n >= 5:
        prefix = _PREFIX_HYPE
        pool = _HYPE if github_username in _PEOPLE else _HYPE_GENERIC
    else:
        prefix = _PREFIX_BASE
        pool = _BASE if github_username in _PEOPLE else _BASE_GENERIC
    available = [m for m in pool if m not in (used or set())]
    chosen = random.choice(available if available else pool)
    if used is not None:
        used.add(chosen)
    return _fmt(prefix + chosen, n, github_username)


def company_of(github_username: str) -> str:
    return _PEOPLE.get(github_username, ("", ""))[1]


def done_line(did: str, gh_name: str, cnt: int, used: set | None = None) -> str:
    header = f"✅ <@{did}> `{gh_name}` — {cnt}개 🔥"
    praise = praise_line(gh_name, cnt, used=used)
    return f"{header}\n> {praise}"


def short_line(did: str, gh_name: str, cnt: int, min_commits: int) -> str:
    remaining = min_commits - cnt
    return f"❌ <@{did}> `{gh_name}` — {cnt}개 (앞으로 **{remaining}개** 더요!!)"


_TEASE_SMALL = [
    "딱 {gap}개 차이에요 ㅎ. <@{loser}> 아깝다~",
    "<@{loser}> {gap}개 차이인데 알고 있어요? 😏",
    "오늘 {gap}개 차. <@{loser}> 내일은 역전 가보자고요~",
]
_TEASE_MED = [
    "<@{loser}> 오늘 좀 쉬셨나봐요~ {gap}개나 차이나는데 ㅋ",
    "오늘 <@{winner}>한테 {gap}개 밀렸어요. <@{loser}> 괜찮아요?? 😄",
    "<@{loser}> {gap}개 차이면 그냥 졌다고 봐도 되는 거 아닌가요 ㅎㅎ",
]
_TEASE_BIG = [
    "<@{loser}> 오늘 {gap}개 차이로 탈탈 털렸네요 ㅋㅋㅋ 내일은요??",
    "오늘 격차가 {gap}개예요. <@{loser}> 뭐 하셨어요 진짜로 😂",
    "<@{winner}> {gap}개 앞서는 거 실화임? <@{loser}> 이거 보고 있어요?",
]
_TEASE_DRAW = [
    "오늘은 동점이네요 👀 내일은 결판 내보세요.",
    "똑같이 {cnt}개. 오늘은 무승부. 내일은 살짝 더 내주면 안 돼요? 😁",
    "동점이라 약올리기 애매한데… 내일은 차이 좀 내줘요 ㅎ",
]


def rank_line(results: list[tuple[str, str, int]]) -> str:
    """전체 (discord_id, gh_name, count) 리스트 → 순위 비교 + 약올리기 문자열."""
    if len(results) < 2:
        return ""
    ranked = sorted(results, key=lambda x: x[2], reverse=True)

    parts = []
    for i, (did, gh_name, cnt) in enumerate(ranked, 1):
        이름 = _PEOPLE.get(gh_name, (gh_name, ""))[0]
        parts.append(f"**{i}위** {이름}씨 `{cnt}개`")
    ranking = " > ".join(parts)

    winner_did, _, winner_cnt = ranked[0]
    loser_did, _, loser_cnt = ranked[-1]
    gap = winner_cnt - loser_cnt

    if gap == 0:
        tease = random.choice(_TEASE_DRAW).replace("{cnt}", str(winner_cnt))
    elif gap <= 2:
        tease = random.choice(_TEASE_SMALL)
    elif gap <= 5:
        tease = random.choice(_TEASE_MED)
    else:
        tease = random.choice(_TEASE_BIG)

    tease = tease.replace("{gap}", str(gap)).replace("{winner}", winner_did).replace("{loser}", loser_did)
    return f"{ranking}\n{tease}"
