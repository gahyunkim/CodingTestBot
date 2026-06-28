"""Discord 슬래시 커맨드를 등록하는 일회성 스크립트.
배포 후 한 번 실행하면 됩니다: python scripts/register_commands.py
"""
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

APPLICATION_ID = os.environ["DISCORD_APPLICATION_ID"]
BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]

COMMANDS = [
    {
        "name": "안내",
        "description": "봇 사용 방법 안내",
        "type": 1,
    },
    {
        "name": "등록",
        "description": "내 GitHub 계정을 등록합니다",
        "type": 1,
        "options": [
            {"name": "github_username", "description": "GitHub 아이디 (예: kimgahyun)", "type": 3, "required": True},
        ],
    },
    {
        "name": "레포등록",
        "description": "커밋을 집계할 GitHub 레포를 등록합니다",
        "type": 1,
        "options": [
            {"name": "repo", "description": "레포 경로 (예: kimgahyun/CodingTest)", "type": 3, "required": True},
        ],
    },
    {
        "name": "레포삭제",
        "description": "등록된 레포를 삭제합니다",
        "type": 1,
        "options": [
            {"name": "repo", "description": "삭제할 레포 경로", "type": 3, "required": True},
        ],
    },
    {"name": "내레포", "description": "내가 등록한 레포 목록을 봅니다", "type": 1},
    {"name": "내정보", "description": "나의 오늘 커밋 수와 벌금을 확인합니다", "type": 1},
    {"name": "오늘현황", "description": "전체 멤버의 오늘 커밋 현황을 봅니다", "type": 1},
    {"name": "벌금", "description": "전체 미납 벌금 현황을 봅니다", "type": 1},
    {"name": "내벌금", "description": "내 벌금 날짜별 내역을 확인합니다", "type": 1},
    {"name": "주간통계", "description": "이번 주 미달 현황과 벌금 합계를 봅니다", "type": 1},
    {
        "name": "토큰등록",
        "description": "GitHub PAT를 등록해 private 레포 커밋을 집계합니다",
        "type": 1,
        "options": [
            {"name": "token", "description": "GitHub Personal Access Token (Contents: Read)", "type": 3, "required": True},
        ],
    },
    {"name": "토큰삭제", "description": "등록된 GitHub 토큰을 삭제합니다", "type": 1},
    {
        "name": "벌금납부",
        "description": "벌금 납부 처리 (관리자 전용)",
        "type": 1,
        "default_member_permissions": "8",
        "options": [
            {"name": "member", "description": "납부 처리할 멤버", "type": 6, "required": True},
        ],
    },
    {
        "name": "강제집계",
        "description": "수동으로 일일 결산을 실행합니다 (관리자 전용)",
        "type": 1,
        "default_member_permissions": "8",
        "options": [
            {"name": "date", "description": "날짜 (기본값: 오늘, 형식: YYYY-MM-DD)", "type": 3, "required": False},
        ],
    },
    {"name": "도움말", "description": "전체 명령어 목록을 봅니다", "type": 1},
]

url = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/commands"
headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}

resp = requests.put(url, json=COMMANDS, headers=headers, timeout=15)
if resp.status_code == 200:
    registered = resp.json()
    print(f"✅ {len(registered)}개 커맨드 등록 완료")
    for cmd in registered:
        print(f"  • /{cmd['name']}")
else:
    print(f"❌ 등록 실패: {resp.status_code}")
    print(resp.text)
    sys.exit(1)
