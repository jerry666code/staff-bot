import os
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
GUILD_ID = int(os.environ["GUILD_ID"])
STAFF_ROLE_ID = int(os.environ["STAFF_ROLE_ID"])
APPROVER_ROLE_ID = int(os.environ.get("APPROVER_ROLE_ID", STAFF_ROLE_ID))
REQUEST_CHANNEL_ID = int(os.environ["REQUEST_CHANNEL_ID"]) if os.environ.get("REQUEST_CHANNEL_ID") else None

GUILD_OBJECT = discord.Object(id=GUILD_ID)

PUNISHMENT_CHOICES = ["Бан", "Мут", "Варн", "Кик", "Другое"]

intents = discord.Intents.default()
intents.members = True


def has_role(member: discord.Member, role_id: int) -> bool:
    return any(role.id == role_id for role in member.roles)


def status_field(label: str, decided_by=None) -> str:
    if decided_by is None:
        return label
    ts = int(datetime.now(timezone.utc).timestamp())
    return f"{label}\n{decided_by.mention} • <t:{ts}:f>"


class DecisionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _decide(self, interaction: discord.Interaction, approved: bool):
        if not isinstance(interaction.user, discord.Member) or not has_role(interaction.user, APPROVER_ROLE_ID):
            await interaction.response.send_message("Недостаточно прав для решения по заявке.", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        label = "✅ Выполнено" if approved else "❌ Отклонено"
        embed.set_field_at(
            len(embed.fields) - 1,
            name="Статус",
            value=status_field(label, interaction.user),
            inline=False,
        )
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Выполнить", style=discord.ButtonStyle.success, custom_id="uw:approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._decide(interaction, approved=True)

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.danger, custom_id="uw:reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._decide(interaction, approved=False)


class StaffBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

    async def setup_hook(self):
        self.add_view(DecisionView())
        self.tree.copy_global_to(guild=GUILD_OBJECT)
        await self.tree.sync(guild=GUILD_OBJECT)


bot = StaffBot()


@bot.tree.command(name="uw", description="Подать заявку на снятие наказания", guild=GUILD_OBJECT)
@app_commands.describe(
    наказание="Тип наказания, которое нужно снять",
    админ="Админ, выдавший наказание",
    причина="Причина снятия",
    steamid64="SteamID64 игрока",
)
@app_commands.choices(наказание=[app_commands.Choice(name=p, value=p) for p in PUNISHMENT_CHOICES])
async def uw(
    interaction: discord.Interaction,
    наказание: app_commands.Choice[str],
    админ: discord.Member,
    причина: str,
    steamid64: str,
):
    if not isinstance(interaction.user, discord.Member) or not has_role(interaction.user, STAFF_ROLE_ID):
        await interaction.response.send_message("Эта команда доступна только администрации.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    embed = discord.Embed(title="✉️ Заявка на снятие наказания", color=discord.Color.blurple())
    embed.add_field(name="Наказание", value=наказание.value, inline=True)
    embed.add_field(name="Админ", value=админ.mention, inline=True)
    embed.add_field(name="SteamID64", value=f"`{steamid64}`", inline=True)
    embed.add_field(name="Причина снятия", value=причина, inline=False)
    embed.add_field(name="Статус", value=status_field("⏳ Ожидает решения"), inline=False)
    embed.set_footer(text=f"Заявка от {interaction.user.display_name}")
    embed.timestamp = datetime.now(timezone.utc)

    target_channel = interaction.channel
    if REQUEST_CHANNEL_ID is not None:
        channel = interaction.guild.get_channel(REQUEST_CHANNEL_ID)
        if channel is not None:
            target_channel = channel

    await target_channel.send(embed=embed, view=DecisionView())

    if target_channel.id != interaction.channel.id:
        await interaction.followup.send(f"Заявка отправлена в {target_channel.mention}.", ephemeral=True)
    else:
        await interaction.followup.send("Заявка создана.", ephemeral=True)


if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
