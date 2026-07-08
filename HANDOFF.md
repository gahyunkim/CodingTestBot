# CodingTestBot — 개발 인수인계 문서

> 이 문서만 읽으면 프로젝트 전체 맥락을 파악하고 개발을 이어나갈 수 있도록 작성했습니다.

---

## 프로젝트 개요

코딩테스트 스터디원들의 **GitHub 커밋을 매일 자동 집계**하고, 하루 목표 커밋 수(현재 2개)를 달성하지 못한 사용자에게 **벌금(5,000원)** 을 부과하는 Discord 봇.

- **상시 프로세스 없음**: 슬래시 커맨드는 Vercel Serverless, 일일 집계는 Vercel Cron
- **커밋 집계 방식**: GitHub API 직접 호출 X → **Discord 채널에 올라온 GitHub 웹훅 메시지 파싱**으로 집계 (GitHub PAT 토큰 불필요)
- **멤버**: 백승주(`Byesol`) 목표 회사 현대오토에버, 김가현(`gahyunkim`) 목표 회사 현대모비스

---

## 아키텍처

```
Discord 유저
  │ /슬래시 커맨드
  ▼
Vercel (api/interactions.py)   ←── Ed25519 서명 검증
  │ DB 읽기/쓰기
  ▼
Supabase (PostgreSQL)

Vercel Cron (UTC 13:00 = KST 22:00)
  └─ api/cron_evening.py  →  22시 리마인더 Discord 전송

Vercel Cron (UTC 14:59 = KST 23:59)
  └─ api/cron_daily.py    →  커밋 집계 + 벌금 부과 + Discord 전송

커밋 집계 방법:
  GitHub Push → Discord GitHub 통합 → #코테 채널에 웹훅 메시지 자동 게시
  → discord_commits.py가 Bot 토큰으로 채널 메시지 읽어서 파싱
```

---

## 파일 구조

```
api/
  interactions.py      Vercel 슬래시 커맨드 핸들러 (Flask)
  cron_evening.py      Vercel Cron — 매일 22:00 KST 저녁 리마인더
  cron_daily.py        Vercel Cron — 매일 23:59 KST 일일 집계 + 벌금
scripts/
  daily_check.py       (구버전 GitHub Actions용 — 현재 미사용)
  evening_reminder.py  (구버전 GitHub Actions용 — 현재 미사용)
  register_commands.py Discord 슬래시 커맨드 등록 (일회성)
supabase/
  migrations/
    001_initial.sql    DB 스키마 (users, user_repos, fines)
    002_cron_log.sql   cron 중복 발송 방지 테이블
.github/
  workflows/
    daily_check.yml        schedule 제거됨 (workflow_dispatch만 남음)
    evening_reminder.yml   schedule 제거됨 (workflow_dispatch만 남음)
database.py            Supabase 클라이언트 래퍼 (동기)
discord_commits.py     Discord 채널에서 커밋 수 집계 (핵심 신규 모듈)
github_api.py          MIN_COMMITS 상수만 재사용 (API 호출은 미사용)
messages.py            Discord 메시지 문구 모음 (칭찬/감탄 텍스트)
vercel.json            Vercel 함수 설정 + Cron 스케줄
requirements.txt       flask, supabase, requests, PyNaCl, python-dotenv
```

---

## 환경변수 (Vercel Production에 모두 설정됨)

| 변수 | 용도 | 비고 |
|---|---|---|
| `DISCORD_APPLICATION_ID` | 앱 ID | Discord Developer Portal |
| `DISCORD_PUBLIC_KEY` | Ed25519 서명 검증용 | Discord Developer Portal |
| `DISCORD_BOT_TOKEN` | Discord 채널 메시지 읽기용 Bot 토큰 | **MESSAGE CONTENT INTENT 활성화 필수** |
| `DISCORD_WEBHOOK_URL` | 결산/리마인더 메시지를 보낼 채널 웹훅 | |
| `DISCORD_COMMITS_CHANNEL_ID` | 커밋 메시지가 올라오는 채널 ID | 현재: `1518179223469162536` |
| `SUPABASE_URL` | Supabase 프로젝트 URL | |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Service Role Key (RLS 우회) | |
| `CRON_SECRET` | Vercel Cron 인증 시크릿 | Vercel 자동 주입 (`Authorization: Bearer <secret>`) |
| `FINE_AMOUNT` | 하루 벌금 금액 | 현재: `5000` |

> `GH_TOKEN` 은 더 이상 불필요 (GitHub API 직접 호출 안 함)

---

## DB 스키마

```sql
-- 기본 테이블 (001_initial.sql)
users      (discord_id PK, github_username, discord_name)
user_repos (discord_id, repo, PRIMARY KEY(discord_id, repo))  -- 현재 미활용
fines      (id SERIAL, discord_id, amount, reason, date, paid BOOLEAN)

-- cron 중복 발송 방지 (002_cron_log.sql)
cron_log   (cron_type TEXT, target_date DATE, sent_at TIMESTAMPTZ, PRIMARY KEY(cron_type, target_date))
```

`cron_log` 사용 방식:
- cron 실행 시 `is_cron_done(type, date)` 체크 → 이미 있으면 스킵
- 발송 성공 후 `mark_cron_done(type, date)` 기록
- `type`: `"daily"` 또는 `"evening"`
- 수동 강제집계(`?date=` 파라미터)는 중복 체크 제외

---

## 슬래시 커맨드 목록

| 커맨드 | 권한 | 설명 |
|---|---|---|
| `/안내` | 일반 | 온보딩 가이드 (ephemeral) |
| `/등록 <GitHub ID>` | 일반 | GitHub 계정 등록 |
| `/레포등록 owner/repo` | 일반 | 집계할 레포 추가 (현재 미활용) |
| `/레포삭제 owner/repo` | 일반 | 등록된 레포 제거 |
| `/내레포` | 일반 | 내 등록 레포 목록 |
| `/내정보` | 일반 | 오늘 커밋 수 + 미납 벌금 |
| `/오늘현황` | 일반 | 전체 멤버 오늘 커밋 현황 |
| `/벌금` | 일반 | 전체 미납 벌금 현황 |
| `/내벌금` | 일반 | 내 벌금 날짜별 내역 (ephemeral) |
| `/주간통계` | 일반 | 이번 주 미달 현황 & 벌금 합계 |
| `/벌금납부 @유저` | 관리자 | 벌금 납부 처리 |
| `/강제집계 [날짜]` | 관리자 | 수동 일일 결산 + 채널 전송 |
| `/도움말` | 일반 | 명령어 목록 (ephemeral) |

---

## 커밋 집계 핵심 로직 (discord_commits.py)

GitHub Push가 발생하면 Discord GitHub 통합이 자동으로 채널에 메시지를 게시한다.
해당 메시지의 `embeds[0].description` 형식:

```
[`abc1234`](url) 커밋 메시지 - GitHubUsername
[`def5678`](url) 다른 커밋 메시지 - GitHubUsername
```

파싱 방법: 각 줄에서 마지막 ` - ` 이후 문자열 = GitHub 사용자명

```python
# 날짜 범위를 Snowflake ID로 변환해서 Discord API after 파라미터로 페이지네이션
last_id = _snowflake(day_start)  # 해당 날짜 00:00 KST
# 메시지 시각이 day_end(23:59 KST) 초과 시 즉시 return
```

**주의사항**:
- Bot에 **MESSAGE CONTENT INTENT** 권한 필요 (Discord Developer Portal → Bot → Privileged Gateway Intents)
- `timeout` 파라미터: 슬래시 커맨드에서 호출 시 `2`초(3초 제한), cron에서 호출 시 `10`초

---

## Cron 타이밍 이슈 & 해결책

**문제**: Vercel Cron이 스케줄 시각보다 30분~2시간 늦게 실행될 수 있음.
- `cron_daily` (KST 23:59 예정) → 실제로 KST 00:30~01:30에 실행되기도 함
- 이 경우 `datetime.now(KST)`가 다음 날 날짜를 반환해서 커밋을 0개로 잘못 집계

**해결**: `hour < 2` 이면 전날 날짜를 사용

```python
now = datetime.now(KST)
date = (now - timedelta(days=1)).strftime("%Y-%m-%d") if now.hour < 2 else now.strftime("%Y-%m-%d")
```

**중복 실행 문제**: Vercel 배포 시 놓친 cron을 backfill로 즉시 실행 → `cron_log` 테이블로 중복 차단

---

## 메시지 시스템 (messages.py)

달성자에 대한 칭찬 문구를 커밋 수에 따라 3단계로 차등 적용.

```python
_PEOPLE = {
    "Byesol":    ("백승주씨", "현대오토에버"),
    "gahyunkim": ("김가현씨", "현대모비스"),
}
```

| 구간 | 감탄사 prefix | 톤 | 풀 크기 |
|---|---|---|---|
| 2~4개 (BASE) | `와! ` | 잔잔한 감탄, 일상 비유 | 6개 |
| 5~9개 (HYPE) | `와!!!!!!!!!! 미쳤다! 돌았다! 와!!!!\n` | 호들갑, 비유 과장 | 6개 |
| 10개 이상 (ULTRA) | `여기요!!!!! 게더 사람들!!... {이름}가 미쳤어요!!!...\n` | 완전 폭주, 게더 소환 | 6개 |

메시지 템플릿 내 플레이스홀더:
- `{n}` → 커밋 수
- `{이름}` → `백승주씨` 또는 `김가현씨`
- `{기업}` → `현대오토에버` 또는 `현대모비스`

**멤버 추가 방법**: `_PEOPLE` dict에 `"github_username": ("실명씨", "목표회사")` 추가 후 `_BASE`, `_HYPE`, `_ULTRA`에 해당 유저용 메시지 추가.

---

## Discord 메시지 톤 & 스타일

### 22:00 리마인더 (cron_evening.py)
- 미달 있을 때 타이틀: `🚨 자정까지 2시간!! 아직 안 끝난 분 있어요!!`
- 전원 달성 타이틀: `🎊 오늘도 전원 달성!! 완벽해요!!`
- 달성자는 `done_line()` → 커밋 수에 따른 칭찬 멘트 포함

### 23:59 결산 (cron_daily.py)
- 벌금 있을 때: `💀 {date} 결산 — 오늘의 희생자 발표` + `결국… 도망치지 못하셨군요. 😈`
- 혼재: `😬 희비가 엇갈렸습니다`
- 전원 달성: `🏆 전원 클리어!!` + `믿을 수가 없어요… 🥲🎉`

### /오늘현황 (interactions.py)
- 전원 달성 중: `🏅 현재까지 전원 달성 중!`
- 아무도 못 함: `😰 아직 아무도 못 했어요...`
- 혼재: `📊 N명 달성 / N명 분발 필요`

---

## 배포 절차

```bash
# 로컬에서 배포
vercel --prod

# 환경변수 로컬에 동기화 (테스트용)
vercel env pull --environment production .env.local

# 슬래시 커맨드 재등록 (새 커맨드 추가 시)
python scripts/register_commands.py
```

**Discord Interactions Endpoint URL** (Developer Portal에 등록됨):
```
https://coding-test-bot.vercel.app/api/interactions
```

---

## 알려진 문제 & 주의사항

### Vercel Cron 지연
- Vercel Cron은 스케줄 시각보다 수십 분 늦게 실행될 수 있음
- `hour < 2` 가드로 날짜 오판정 방지 중
- `cron_log` 테이블로 중복 발송 방지 중

### Discord Bot Token
- `DISCORD_BOT_TOKEN`이 만료/재발급되면 Vercel 환경변수 업데이트 필요
  ```bash
  vercel env rm DISCORD_BOT_TOKEN production
  vercel env add DISCORD_BOT_TOKEN production
  ```
- 재발급 후 반드시 MESSAGE CONTENT INTENT 재확인 (Discord Developer Portal → Bot)

### 수동 벌금 수정
- 잘못 부과된 벌금은 Supabase 대시보드 또는 로컬 스크립트로 직접 수정
  ```python
  # 로컬에서 .env.local 로드 후
  db._db().table('fines').delete().eq('id', 10).execute()
  ```

### cron_log 수동 처리
- cron이 벌금은 넣었는데 Discord 전송 실패로 `cron_log`에 기록 못 한 경우:
  ```python
  db.mark_cron_done('daily', '2026-07-02')
  ```

### 슬래시 커맨드 3초 제한
- Discord는 슬래시 커맨드에 3초 내 응답 필수
- Discord API 호출 timeout은 `2`초로 제한 (cron은 `10`초 사용)
- 무거운 커맨드는 deferred response 고려 필요

---

## 로컬 개발

```bash
pip install -r requirements.txt
vercel env pull --environment production .env.local

# Vercel 함수 로컬 실행
vercel dev

# 특정 날짜 커밋 집계 테스트
python -c "
import sys; sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv('.env.local')
import discord_commits as dc
print(dc.get_commit_counts('2026-07-03', timeout=10))
"

# 메시지 출력 테스트
python -c "
import sys; sys.path.insert(0, '.'); sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv; load_dotenv('.env.local')
import messages as m
print(m.done_line('123', 'Byesol', 3))
print(m.done_line('456', 'gahyunkim', 7))
print(m.done_line('123', 'Byesol', 24))
"
```

---

## GitHub 저장소

- **URL**: https://github.com/gahyunkim/CodingTestBot
- **기본 브랜치**: `main` (Vercel이 main 기준으로 자동 배포)
- `.github/workflows/` 의 두 워크플로우는 `schedule` 트리거 제거됨 (`workflow_dispatch`만 남음 — Vercel Cron으로 이전했기 때문)

---

## 향후 개발 아이디어 (논의됐으나 미구현)

- **메시지 슬래시 커맨드 편집**: `/메시지추가`, `/메시지목록`, `/메시지삭제` — Supabase에 messages 테이블 + Discord Modal 필요. 복잡도 대비 효용 낮아서 보류.
- **실시간 커밋 달성 알림**: GitHub Push → Vercel 웹훅 엔드포인트 → 5개/10개 돌파 시 즉시 메시지. Vercel Hobby 플랜 cron 최소 단위가 1시간이라 폴링으로는 한계. 보류.
