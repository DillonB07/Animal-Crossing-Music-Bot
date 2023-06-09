import json
import os
from datetime import datetime

import aiohttp
import discord
import pytz
from discord.ext import commands


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


async def handle_error(
    interaction: discord.Interaction,
    error,
    ephemeral=True,
):
    if isinstance(error, commands.CommandOnCooldown):
        await interaction.response.send_message(
            embed=await create_embed(
                description="You're on cooldown for {:.1f}s".format(error.retry_after),
                ephemeral=ephemeral,
            )
        )
    elif isinstance(error, commands.DisabledCommand):
        await interaction.response.send_message(
            embed=await create_embed(description="This command is disabled."),
            ephemeral=ephemeral,
        )
    elif isinstance(error, NoVCError):
        await interaction.response.send_message(
            embed=await create_embed(
                description="I was not able to join your voice channel",
            )
        )
    else:
        await interaction.response.send_message(
            embed=await create_embed(description="Something went wrong"),
            ephemeral=ephemeral,
        )


def get_string_time(timezone: str = "Europe/London"):
    tz = pytz.timezone(timezone)
    hour = datetime.now(tz).hour
    day = datetime.now(tz).weekday()
    hour_12 = hour % 12
    if hour_12 == 0:
        hour_12 = 12
    am_pm = "am" if hour < 12 else "pm"
    return [f"{hour_12}{am_pm}", hour, day]


async def get_weather(area: str = "London"):
    key = os.getenv("WEATHER_TOKEN")
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"http://api.weatherapi.com/v1/current.json?key={key}&aqi=no&q={area}"
        ) as response:
            return await response.json()


def get_weather_type(code: int):
    with open("data/weather.json", "r") as f:
        data = json.load(f)
    for item in data:
        if item.get("code") == code:
            if "rain" in item.get("day").lower() or "rain" in item.get("night").lower():
                return "raining"
            elif (
                "snow" in item.get("day").lower() or "snow" in item.get("night").lower()
            ):
                return "snowing"
            else:
                return "sunny"
    return "sunny"
