# CodingTestBot — CLAUDE.md

## 프로젝트 개요

코딩테스트 스터디원들의 GitHub 커밋을 매일 자동 집계하고, 하루 목표 커밋 수를 달성하지 못한 사용자에게 벌금을 부과하는 Discord 봇.

**아키텍처**: 상시 프로세스 없음. 슬래시 커맨드는 Vercel Serverless, 일일 집계는 GitHub Actions Cron으로 분리.

---

## 아키텍처

```
Discord 유저
  │ /슬래시 커맨드
  ▼
Vercel (api/interactions.py)   ←── Ed25519 서명 검증
  │ DB 읽기/쓰기                  GitHub API 조회
  ▼
Supabase (PostgreSQL)

GitHub Actions (cron 23:59 KST)
  │ 전체 유저 커밋 집계 + 벌금 기록
  ▼
Supabase + Discord Webhook → 채널에 결산 결과 전송
```

---

## 파일 구조

```
api/
  interactions.py      Vercel 슬래시 커맨드 핸들러 (Flask)
scripts/
  daily_check.py       GitHub Actions 일일 집계 스크립트
  register_commands.py Discord 슬래시 커맨드 등록 (일회성)
supabase/
  migrations/
    001_initial.sql    DB 스키마
.github/
  workflows/
    daily_check.yml    Cron 워크플로우 (23:59 KST)
database.py            Supabase 클라이언트 래퍼 (동기)
github_api.py          GitHub API 헬퍼, 병렬 커밋 집계
vercel.json            Vercel 함수 설정 (maxDuration: 30s)
requirements.txt       flask, supabase, requests, PyNaCl, python-dotenv
.env.example           환경변수 템플릿
```

---

## 환경변수

| 변수 | 용도 | 필수 |
|---|---|---|
| `DISCORD_APPLICATION_ID` | 앱 ID (Discord Developer Portal) | ✅ |
| `DISCORD_PUBLIC_KEY` | Ed25519 서명 검증용 공개키 | ✅ |
| `DISCORD_BOT_TOKEN` | 커맨드 등록 스크립트에만 사용 | 등록 시만 |
| `DISCORD_WEBHOOK_URL` | 일일 결산 결과를 보낼 채널 웹훅 | ✅ |
| `SUPABASE_URL` | Supabase 프로젝트 URL | ✅ |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Service Role Key (RLS 우회) | ✅ |
| `GH_TOKEN` | GitHub PAT (없으면 60req/h 제한) | 권장 |
| `FINE_AMOUNT` | 하루 벌금 금액 (기본: 1000) | 선택 |

`MIN_COMMITS = 2`는 `github_api.py` 상단에 하드코딩되어 있다.

---

## DB 스키마

```sql
users      (discord_id PK, github_username, discord_name)
user_repos (discord_id, repo, PRIMARY KEY(discord_id, repo))
fines      (id SERIAL, discord_id, amount, reason, date, paid BOOLEAN)
```

`supabase/migrations/001_initial.sql`을 Supabase SQL 에디터에서 실행해 테이블을 생성한다.

---

## 슬래시 커맨드 목록

| 커맨드 | 권한 | 설명 |
|---|---|---|
| `/안내` | 일반 | 온보딩 가이드 (ephemeral) |
| `/등록 <GitHub ID>` | 일반 | GitHub 계정 등록 |
| `/레포등록 owner/repo` | 일반 | 집계할 레포 추가 |
| `/레포삭제 owner/repo` | 일반 | 등록된 레포 제거 |
| `/내레포` | 일반 | 내 등록 레포 목록 |
| `/내정보` | 일반 | 오늘 커밋 수 + 미납 벌금 |
| `/오늘현황` | 일반 | 전체 멤버 오늘 커밋 현황 |
| `/벌금` | 일반 | 전체 미납 벌금 현황 |
| `/벌금납부 @유저` | 관리자 | 벌금 납부 처리 |
| `/강제집계 [날짜]` | 관리자 | 수동 일일 결산 + 채널 전송 |
| `/도움말` | 일반 | 명령어 목록 (ephemeral) |

---

## 배포 절차

### 1. Supabase 설정
1. [supabase.com](https://supabase.com)에서 프로젝트 생성
2. SQL 에디터에서 `supabase/migrations/001_initial.sql` 실행
3. Settings → API에서 `URL`과 `service_role` 키 복사

### 2. Discord 앱 설정
1. [Discord Developer Portal](https://discord.com/developers/applications)에서 앱 생성
2. Bot 탭 → 토큰 발급
3. General Information → `Application ID`, `Public Key` 복사
4. 일일 결산을 받을 채널에서 웹훅 생성 (채널 편집 → 연동 → 웹훅)

### 3. Vercel 배포
```bash
npm i -g vercel
vercel --prod
```
Vercel 대시보드 → Settings → Environment Variables에 `.env.example`의 모든 값 입력.

배포 후 나오는 URL을 Discord Developer Portal → General Information → **Interactions Endpoint URL**에 입력:
```
https://your-project.vercel.app/api/interactions
```

### 4. 슬래시 커맨드 등록 (일회성)
```bash
pip install -r requirements.txt
cp .env.example .env  # 값 채우기
python scripts/register_commands.py
```

### 5. GitHub Actions Secrets 설정
레포 → Settings → Secrets and variables → Actions에 다음 시크릿 추가:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `GH_TOKEN`
- `DISCORD_WEBHOOK_URL`
- `FINE_AMOUNT` (선택)

---

## 로컬 개발

```bash
pip install -r requirements.txt
cp .env.example .env   # 값 입력 후

# Vercel 함수 로컬 실행
vercel dev

# 일일 집계 스크립트 수동 실행
python scripts/daily_check.py             # 오늘
python scripts/daily_check.py 2026-06-21  # 특정 날짜
```

---

## 핵심 설계 결정

- **상시 프로세스 없음**: 슬래시 커맨드는 HTTP 요청 시에만 실행 (Serverless), 일일 집계는 GitHub Actions Cron으로 완전 무료
- **병렬 GitHub API 조회**: `github_api.check_all_users`가 `ThreadPoolExecutor(max_workers=5)`로 전체 유저를 병렬 조회해 3초 내 응답 가능
- **동기 코드**: Vercel Python은 async가 불필요하므로 `requests` + 동기 supabase-py 사용
- **Service Role Key**: Supabase RLS를 우회하기 위해 anon key가 아닌 service_role key 사용
