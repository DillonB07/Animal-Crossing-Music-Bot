import discord
from discord.ext import commands
from datetime import datetime
import pytz

timezone = pytz.timezone('Europe/London')


class NoVCError(commands.CommandError):
    pass


async def create_embed(

        title="Command failed",
        description="You don't have permission to use this command",
        color=discord.Color.red(),
        **kwargs,
):
    """Returns an embed"""
    embed = discord.Embed(title=title, description=description, color=color, **kwargs)
    return embed


async def handle_error(ctx, error, ephemeral=True):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.reply(
            embed=await create_embed(
                description="You're on cooldown for {:.1f}s".format(error.retry_after),
                ephemeral=ephemeral,
            )
        )
    elif isinstance(error, commands.DisabledCommand):
        await ctx.reply(
            embed=await create_embed(description="This command is disabled."),
            ephemeral=ephemeral,
        )
    elif isinstance(error, NoVCError):
        await ctx.reply(embed=await create_embed(
            description="I must be in a voice channel to play music and I wasn't able to join your vc."))
    else:
        await ctx.reply(
            embed=await create_embed(description=error), ephemeral=ephemeral
        )


def get_string_time():
    current_time = datetime.now(timezone) if timezone else datetime.now()
    hour = current_time.hour % 12
    am_pm = "am" if current_time.hour < 12 else "pm"
    return [f"{hour}{am_pm}", hour]
