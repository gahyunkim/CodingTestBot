import os
import xml.etree.ElementTree as ET
from datetime import datetime, time, timedelta

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

import database as db

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
FINE_AMOUNT = int(os.getenv("FINE_AMOUNT", "1000"))
MIN_COMMITS = 2
KST = ZoneInfo("Asia/Seoul")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
http_session: aiohttp.ClientSession = None


async def get_commit_count(discord_id: str, github_username: str, date: str) -> int:
    repos = await db.get_repos(discord_id)
    if not repos:
        return 0

    user_row = await db.get_user_by_discord(discord_id)
    # author_name 없으면 github_username으로 fallback
    author_name = (user_row[3] if user_row and user_row[3] else github_username)

    kst_start = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=KST)
    kst_end = kst_start + timedelta(days=1)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    count = 0

    for repo in repos:
        for branch in ["main", "master"]:
            url = f"https://github.com/{repo}/commits/{branch}.atom"
            async with http_session.get(url) as resp:
                if resp.status != 200:
                    continue
                try:
                    root = ET.fromstring(await resp.text())
                except ET.ParseError:
                    continue
                for entry in root.findall("atom:entry", ns):
                    author_el = entry.find("atom:author/atom:name", ns)
                    if author_el is None or author_el.text != author_name:
                        continue
                    updated_el = entry.find("atom:updated", ns)
                    if updated_el is None:
                        continue
                    commit_time = datetime.fromisoformat(
                        updated_el.text.replace("Z", "+00:00")
                    ).astimezone(KST)
                    if kst_start <= commit_time < kst_end:
                        count += 1
                break  # 200 응답 받은 브랜치로 확정
    return count


@bot.event
async def on_ready():
    global http_session
    http_session = aiohttp.ClientSession()
    await db.init_db()
    print(f"[봇] {bot.user} 준비 완료")
    if not daily_check.is_running():
        daily_check.start()
    await bot.tree.sync()
    print("[봇] 슬래시 커맨드 동기화 완료")


def build_onboarding_embed() -> discord.Embed:
    embed = discord.Embed(
        title="👋 커밋 벌금봇 사용 안내",
        description=f"하루 **{MIN_COMMITS}개 이상** 커밋하지 않으면 **{FINE_AMOUNT:,}원** 벌금이 부과됩니다!",
        color=0x845EF7,
    )
    embed.add_field(
        name="1️⃣ GitHub 계정 등록",
        value="`!등록 <GitHub아이디>`\n예: `!등록 kimgahyun`",
        inline=False,
    )
    embed.add_field(
        name="2️⃣ git 이름 등록 (커밋 작성자 매칭)",
        value="`!이름등록 <git user.name>`\n터미널에서 `git config user.name` 으로 확인\n예: `!이름등록 Kim Gahyun`",
        inline=False,
    )
    embed.add_field(
        name="3️⃣ 감시할 레포 등록 (여러 개 가능)",
        value="`!레포등록 owner/repo`\n예: `!레포등록 kimgahyun/CodingTest`",
        inline=False,
    )
    webhook_guide = (
        f"GitHub 레포 → Settings → Webhooks → Add webhook\n"
        f"• Payload URL: `{DISCORD_WEBHOOK_URL}/github`\n"
        f"• Content type: `application/json`\n"
        f"• Events: `Just the push event`"
        if DISCORD_WEBHOOK_URL
        else "관리자에게 Discord 웹훅 URL을 받아서\nGitHub 레포 Settings → Webhooks에 등록하세요."
    )
    embed.add_field(name="4️⃣ GitHub 레포에 Discord 웹훅 연결", value=webhook_guide, inline=False)
    embed.add_field(name="📖 전체 명령어 보기", value="`!도움말`", inline=False)
    return embed


@bot.event
async def on_member_join(member: discord.Member):
    embed = build_onboarding_embed()
    try:
        await member.send(embed=embed)
    except discord.Forbidden:
        channel = bot.get_channel(DISCORD_CHANNEL_ID)
        if channel:
            await channel.send(f"{member.mention} 환영합니다!", embed=embed)


@tasks.loop(time=time(hour=23, minute=59, tzinfo=KST))
async def daily_check():
    today = datetime.now(KST).strftime("%Y-%m-%d")
    await run_daily_check(today)


async def run_daily_check(today: str):
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if not channel:
        return
    users = await db.get_all_users()
    if not users:
        return

    fine_list = []
    safe_list = []

    for discord_id, github_username, *_ in users:
        count = await get_commit_count(discord_id, github_username, today)
        if count < MIN_COMMITS:
            await db.add_fine(
                discord_id, FINE_AMOUNT,
                f"{today} 커밋 {count}개 ({MIN_COMMITS}개 미달)", today,
            )
            fine_list.append((discord_id, github_username, count))
        else:
            safe_list.append((discord_id, github_username, count))

    embed = discord.Embed(
        title=f"📊 {today} 일일 커밋 결산",
        color=0xFF6B6B if fine_list else 0x51CF66,
        timestamp=datetime.now(KST),
    )
    if safe_list:
        text = "\n".join(f"✅ <@{did}> `{gh}` — {cnt}개" for did, gh, cnt in safe_list)
        embed.add_field(name="목표 달성 🎉", value=text, inline=False)
    if fine_list:
        text = "\n".join(
            f"❌ <@{did}> `{gh}` — {cnt}개 → 벌금 {FINE_AMOUNT:,}원"
            for did, gh, cnt in fine_list
        )
        embed.add_field(name=f"벌금 {FINE_AMOUNT:,}원 💸", value=text, inline=False)
    embed.set_footer(text=f"하루 최소 {MIN_COMMITS}개 커밋 목표")
    await channel.send(embed=embed)


# ── 명령어 ────────────────────────────────────────────────────────


@bot.command(name="등록")
async def cmd_register(ctx, github_username: str = None):
    if not github_username:
        await ctx.reply("사용법: `!등록 <GitHub 아이디>`")
        return
    await db.register_user(str(ctx.author.id), github_username, ctx.author.display_name)
    embed = discord.Embed(
        title="✅ 등록 완료",
        description=f"{ctx.author.mention} → GitHub `{github_username}` 연결됐습니다.",
        color=0x51CF66,
    )
    await ctx.reply(embed=embed)


@bot.command(name="내정보")
async def cmd_my_info(ctx):
    row = await db.get_user_by_discord(str(ctx.author.id))
    if not row:
        await ctx.reply("`!등록 <GitHub 아이디>`로 먼저 등록해주세요.")
        return
    _, github_username, *_ = row
    today = datetime.now(KST).strftime("%Y-%m-%d")
    count = await get_commit_count(str(ctx.author.id), github_username, today)
    total_fine = await db.get_total_fine(str(ctx.author.id))
    status = "✅ 달성" if count >= MIN_COMMITS else f"❌ {MIN_COMMITS - count}개 부족"
    embed = discord.Embed(title=f"👤 {ctx.author.display_name}", color=0x339AF0)
    embed.add_field(name="GitHub", value=f"`{github_username}`", inline=True)
    embed.add_field(name=f"오늘 커밋 ({today})", value=f"{count}개  {status}", inline=True)
    embed.add_field(name="미납 벌금", value=f"{total_fine:,}원", inline=True)
    await ctx.reply(embed=embed)


@bot.command(name="오늘현황")
async def cmd_today(ctx):
    users = await db.get_all_users()
    if not users:
        await ctx.reply("등록된 사용자가 없습니다.")
        return
    today = datetime.now(KST).strftime("%Y-%m-%d")
    rows = []
    for discord_id, github_username, *_ in users:
        count = await get_commit_count(discord_id, github_username, today)
        icon = "✅" if count >= MIN_COMMITS else "❌"
        rows.append(f"{icon} <@{discord_id}> `{github_username}` — {count}개")
    embed = discord.Embed(
        title=f"📅 {today} 커밋 현황",
        description="\n".join(rows),
        color=0x339AF0,
    )
    embed.set_footer(text=f"목표: 하루 {MIN_COMMITS}개 이상")
    await ctx.reply(embed=embed)


@bot.command(name="벌금")
async def cmd_fine(ctx):
    summary = await db.get_all_fines_summary()
    if not summary:
        await ctx.reply("등록된 사용자가 없습니다.")
        return
    rows = []
    for discord_id, _, github_username, total in summary:
        icon = "💸" if total > 0 else "😇"
        rows.append(f"{icon} <@{discord_id}> `{github_username}` — {total:,}원")
    embed = discord.Embed(
        title="💰 벌금 현황 (미납)",
        description="\n".join(rows),
        color=0xFFD43B,
    )
    await ctx.reply(embed=embed)


@bot.command(name="벌금납부")
@commands.has_permissions(administrator=True)
async def cmd_pay_fine(ctx, member: discord.Member = None):
    if not member:
        await ctx.reply("사용법: `!벌금납부 @유저`")
        return
    total = await db.get_total_fine(str(member.id))
    if total == 0:
        await ctx.reply(f"{member.mention}의 미납 벌금이 없습니다.")
        return
    await db.pay_fines(str(member.id))
    embed = discord.Embed(
        title="✅ 납부 완료",
        description=f"{member.mention}의 미납 벌금 {total:,}원이 납부 처리됐습니다.",
        color=0x51CF66,
    )
    await ctx.reply(embed=embed)


@bot.command(name="강제집계")
@commands.has_permissions(administrator=True)
async def cmd_force_check(ctx, date: str = None):
    target = date or datetime.now(KST).strftime("%Y-%m-%d")
    await ctx.reply(f"`{target}` 집계를 시작합니다...")
    await run_daily_check(target)


@bot.command(name="안내")
async def cmd_onboarding(ctx):
    await ctx.reply(embed=build_onboarding_embed())


@bot.command(name="레포등록")
async def cmd_add_repo(ctx, repo: str = None):
    if not repo or "/" not in repo:
        await ctx.reply("사용법: `!레포등록 owner/repo-name`\n예시: `!레포등록 kimgahyun/CodingTest`")
        return
    await db.add_repo(str(ctx.author.id), repo)
    embed = discord.Embed(
        title="✅ 레포 등록 완료",
        description=f"`{repo}` 가 등록됐습니다. 이제 이 레포의 커밋만 집계됩니다.",
        color=0x51CF66,
    )
    await ctx.reply(embed=embed)


@bot.command(name="레포삭제")
async def cmd_remove_repo(ctx, repo: str = None):
    if not repo:
        await ctx.reply("사용법: `!레포삭제 owner/repo-name`")
        return
    await db.remove_repo(str(ctx.author.id), repo)
    await ctx.reply(f"`{repo}` 를 삭제했습니다.")


@bot.command(name="내레포")
async def cmd_my_repos(ctx):
    repos = await db.get_repos(str(ctx.author.id))
    if not repos:
        await ctx.reply("등록된 레포가 없습니다. 레포 없이 전체 커밋 활동을 집계합니다.\n`!레포등록 owner/repo` 로 추가하세요.")
        return
    embed = discord.Embed(
        title=f"📁 {ctx.author.display_name}의 등록 레포",
        description="\n".join(f"• `{r}`" for r in repos),
        color=0x339AF0,
    )
    await ctx.reply(embed=embed)


@bot.command(name="이름등록")
async def cmd_author_name(ctx, *, author_name: str = None):
    if not author_name:
        await ctx.reply("사용법: `!이름등록 <git 이름>`\n`git config user.name` 값을 입력해주세요.")
        return
    await db.update_author_name(str(ctx.author.id), author_name)
    await ctx.reply(f"✅ git 이름 `{author_name}` 으로 등록됐습니다. 커밋 집계에 이 이름이 사용됩니다.")


@bot.command(name="도움말")
async def cmd_help(ctx):
    embed = discord.Embed(title="📖 명령어 도움말", color=0x845EF7)
    cmds = [
        ("!등록 <GitHub ID>", "내 GitHub 계정 등록"),
        ("!이름등록 <git 이름>", "git user.name 등록 (커밋 작성자 매칭용)"),
        ("!레포등록 owner/repo", "집계할 레포 추가 (여러 개 가능)"),
        ("!레포삭제 owner/repo", "등록된 레포 제거"),
        ("!내레포", "내가 등록한 레포 목록"),
        ("!내정보", "나의 오늘 커밋 수 & 벌금 확인"),
        ("!오늘현황", "전체 멤버 오늘 커밋 현황"),
        ("!벌금", "전체 미납 벌금 현황"),
        ("!벌금납부 @유저", "벌금 납부 처리 (관리자)"),
        ("!강제집계 [날짜]", "수동 일일 결산 (관리자), 날짜: YYYY-MM-DD"),
    ]
    for name, desc in cmds:
        embed.add_field(name=f"`{name}`", value=desc, inline=False)
    await ctx.reply(embed=embed)


@cmd_pay_fine.error
async def pay_fine_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("❌ 관리자 권한이 필요합니다.")


@cmd_force_check.error
async def force_check_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("❌ 관리자 권한이 필요합니다.")


# ── 슬래시 커맨드 ────────────────────────────────────────────────


@bot.tree.command(name="안내", description="봇 사용 방법 안내")
async def slash_onboarding(interaction: discord.Interaction):
    await interaction.response.send_message(embed=build_onboarding_embed(), ephemeral=True)


@bot.tree.command(name="등록", description="내 GitHub 계정을 등록합니다")
@app_commands.describe(github_username="GitHub 아이디 (예: kimgahyun)")
async def slash_register(interaction: discord.Interaction, github_username: str):
    await db.register_user(str(interaction.user.id), github_username, interaction.user.display_name)
    embed = discord.Embed(
        title="✅ 등록 완료",
        description=f"{interaction.user.mention} → GitHub `{github_username}` 연결됐습니다.",
        color=0x51CF66,
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="이름등록", description="git user.name을 등록합니다 (커밋 작성자 매칭에 사용)")
@app_commands.describe(author_name="git config user.name 값")
async def slash_author_name(interaction: discord.Interaction, author_name: str):
    await db.update_author_name(str(interaction.user.id), author_name)
    await interaction.response.send_message(
        f"✅ git 이름 `{author_name}` 으로 등록됐습니다. 커밋 집계에 이 이름이 사용됩니다."
    )


@bot.tree.command(name="레포등록", description="커밋을 집계할 GitHub 레포를 등록합니다")
@app_commands.describe(repo="레포 경로 (예: kimgahyun/CodingTest)")
async def slash_add_repo(interaction: discord.Interaction, repo: str):
    if "/" not in repo:
        await interaction.response.send_message("형식: `owner/repo-name`\n예: `kimgahyun/CodingTest`", ephemeral=True)
        return
    await db.add_repo(str(interaction.user.id), repo)
    embed = discord.Embed(
        title="✅ 레포 등록 완료",
        description=f"`{repo}` 가 등록됐습니다. 이제 이 레포의 커밋만 집계됩니다.",
        color=0x51CF66,
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="레포삭제", description="등록된 레포를 삭제합니다")
@app_commands.describe(repo="삭제할 레포 경로 (예: kimgahyun/CodingTest)")
async def slash_remove_repo(interaction: discord.Interaction, repo: str):
    await db.remove_repo(str(interaction.user.id), repo)
    await interaction.response.send_message(f"`{repo}` 를 삭제했습니다.")


@bot.tree.command(name="내레포", description="내가 등록한 레포 목록을 봅니다")
async def slash_my_repos(interaction: discord.Interaction):
    repos = await db.get_repos(str(interaction.user.id))
    if not repos:
        await interaction.response.send_message(
            "등록된 레포가 없습니다. `/레포등록 owner/repo` 로 추가하세요.", ephemeral=True
        )
        return
    embed = discord.Embed(
        title=f"📁 {interaction.user.display_name}의 등록 레포",
        description="\n".join(f"• `{r}`" for r in repos),
        color=0x339AF0,
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="내정보", description="나의 오늘 커밋 수와 벌금을 확인합니다")
async def slash_my_info(interaction: discord.Interaction):
    row = await db.get_user_by_discord(str(interaction.user.id))
    if not row:
        await interaction.response.send_message("`/등록 <GitHub 아이디>`로 먼저 등록해주세요.", ephemeral=True)
        return
    _, github_username, *_ = row
    today = datetime.now(KST).strftime("%Y-%m-%d")
    await interaction.response.defer()
    count = await get_commit_count(str(interaction.user.id), github_username, today)
    total_fine = await db.get_total_fine(str(interaction.user.id))
    status = "✅ 달성" if count >= MIN_COMMITS else f"❌ {MIN_COMMITS - count}개 부족"
    embed = discord.Embed(title=f"👤 {interaction.user.display_name}", color=0x339AF0)
    embed.add_field(name="GitHub", value=f"`{github_username}`", inline=True)
    embed.add_field(name=f"오늘 커밋 ({today})", value=f"{count}개  {status}", inline=True)
    embed.add_field(name="미납 벌금", value=f"{total_fine:,}원", inline=True)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="오늘현황", description="전체 멤버의 오늘 커밋 현황을 봅니다")
async def slash_today(interaction: discord.Interaction):
    users = await db.get_all_users()
    if not users:
        await interaction.response.send_message("등록된 사용자가 없습니다.", ephemeral=True)
        return
    today = datetime.now(KST).strftime("%Y-%m-%d")
    await interaction.response.defer()
    rows = []
    for discord_id, github_username, *_ in users:
        count = await get_commit_count(discord_id, github_username, today)
        icon = "✅" if count >= MIN_COMMITS else "❌"
        rows.append(f"{icon} <@{discord_id}> `{github_username}` — {count}개")
    embed = discord.Embed(
        title=f"📅 {today} 커밋 현황",
        description="\n".join(rows),
        color=0x339AF0,
    )
    embed.set_footer(text=f"목표: 하루 {MIN_COMMITS}개 이상")
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="벌금", description="전체 미납 벌금 현황을 봅니다")
async def slash_fine(interaction: discord.Interaction):
    summary = await db.get_all_fines_summary()
    if not summary:
        await interaction.response.send_message("등록된 사용자가 없습니다.", ephemeral=True)
        return
    rows = []
    for discord_id, _, github_username, total in summary:
        icon = "💸" if total > 0 else "😇"
        rows.append(f"{icon} <@{discord_id}> `{github_username}` — {total:,}원")
    embed = discord.Embed(
        title="💰 벌금 현황 (미납)",
        description="\n".join(rows),
        color=0xFFD43B,
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="벌금납부", description="벌금 납부 처리 (관리자 전용)")
@app_commands.describe(member="납부 처리할 멤버")
@app_commands.checks.has_permissions(administrator=True)
async def slash_pay_fine(interaction: discord.Interaction, member: discord.Member):
    total = await db.get_total_fine(str(member.id))
    if total == 0:
        await interaction.response.send_message(f"{member.mention}의 미납 벌금이 없습니다.", ephemeral=True)
        return
    await db.pay_fines(str(member.id))
    embed = discord.Embed(
        title="✅ 납부 완료",
        description=f"{member.mention}의 미납 벌금 {total:,}원이 납부 처리됐습니다.",
        color=0x51CF66,
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="강제집계", description="수동으로 일일 결산을 실행합니다 (관리자 전용)")
@app_commands.describe(date="날짜 (기본값: 오늘, 형식: YYYY-MM-DD)")
@app_commands.checks.has_permissions(administrator=True)
async def slash_force_check(interaction: discord.Interaction, date: str = None):
    target = date or datetime.now(KST).strftime("%Y-%m-%d")
    await interaction.response.send_message(f"`{target}` 집계를 시작합니다...")
    await run_daily_check(target)


@slash_pay_fine.error
async def slash_pay_fine_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ 관리자 권한이 필요합니다.", ephemeral=True)


@slash_force_check.error
async def slash_force_check_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ 관리자 권한이 필요합니다.", ephemeral=True)


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
