import asyncio
import os
import random
import sys
import typing

import audiofile
import discord
import pytz
from discord import FFmpegPCMAudio, Interaction, app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from utils import (
    NoVCError,
    create_embed,
    get_string_time,
    get_weather,
    get_weather_type,
    handle_error,
)

load_dotenv()

ADMINS = [915670836357247006, 658650587679948820, 1015577382826020894]
FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}
MUSIC_FOLDER = "music"
GAMES = ["animal-crossing", "new-horizons", "new-leaf", "wild-world"]

db_client = MongoClient(os.environ["DB_URI"], server_api=ServerApi("1"))
db = db_client.data
server_collection = db.servers


class Client(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Synced slash commands for {self.user}")

    async def on_command_error(self, interaction: Interaction, error):
        await handle_error(interaction, error, ephemeral=True)


client = Client()


@client.event
async def on_ready():
    print("Ready")
    time = get_string_time()[0]
    await client.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening, name=f"AC {time} music"
        )
    )


@tasks.loop(minutes=5)
async def update_presence():
    time = get_string_time()[0]
    await client.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening, name=f"AC {time} music"
        )
    )


@client.event
async def on_guild_join(guild):
    server_doc = {
        "id": guild.id,
        "name": guild.name,
        "timezone": "Europe/London",
        "game": "all",
        "weather": "random",
        "kk": "default",
        "area": "London",
    }
    server_collection.insert_one(server_doc)


@client.event
async def on_guild_remove(guild):
    server_collection.find_one_and_delete({"id": guild.id})


@client.tree.command(name="restart", description="Restart the bot")
@commands.has_guild_permissions(administrator=True)
async def restart(interaction: Interaction):
    if interaction.user.id not in ADMINS:
        await interaction.response.send_message(embed=await create_embed())
        return
    await interaction.response.send_message(
        embed=await create_embed(
            title="Restarting",
            description=f"Restart ordered by {interaction.user.mention}",
        )
    )

    sys.exit()


@client.tree.command(
    name="ping",
    description="Check bot latency",
)
async def ping(interaction: Interaction):
    latency = round(client.latency * 1000)
    desc = (f":ping_pong: Pong! Bot's latency is `{latency}` ms!",)
    if round(latency * 1000) <= 50:
        embed = discord.Embed(
            title="PING",
            description=desc,
            color=0x44FF44,
        )
    elif round(latency * 1000) <= 100:
        embed = discord.Embed(
            title="PING",
            description=desc,
            color=0xFFD000,
        )
    elif round(latency * 1000) <= 200:
        embed = discord.Embed(
            title="PING",
            description=desc,
            color=0xFF6600,
        )
    else:
        embed = discord.Embed(
            title="PING",
            description=desc,
            color=0x990000,
        )
    await interaction.response.send_message(embed=embed)


@client.tree.command(
    name="play",
    description="Start playing music",
)
async def play(interaction: Interaction):
    guild = interaction.guild
    if not guild:
        return await interaction.response.send_message(
            embed=await create_embed(
                title="Error",
                description="Could not get guild info",
            )
        )

    if type(interaction.user) != discord.Member:
        return await interaction.response.send_message(
            embed=await create_embed(
                title="Error",
                description="Something strange happened, please try again",
            )
        )

    # Get voice_client and voice_channel. join the user's vc
    voice = interaction.user.voice
    if not voice:
        raise NoVCError()
    voice_channel = voice.channel
    if not voice_channel:
        raise NoVCError()
    await voice_channel.connect(reconnect=True)
    voice_client = guild.voice_client

    await interaction.response.send_message(
        embed=await create_embed(
            title="Playing Music",
            description=f"Check {voice_channel.mention} for notifications",
            color=discord.Color.green(),
        )
    )

    async def play_music():
        while True:
            if type(voice_client) != discord.VoiceClient:
                print(type(voice_client))
                return await interaction.response.send_message(
                    embed=await create_embed(
                        title="Error",
                        description="Could not get voice client",
                    )
                )

            if voice_channel != voice_client.channel:
                break

            if not voice_channel:
                raise NoVCError()

            server = server_collection.find_one({"id": guild.id})
            if not server:
                return await voice_channel.send(
                    embed=await create_embed(
                        title="Error",
                        description="Could not get server info",
                    )
                )

            kk = server["kk"]
            tz = server["timezone"]
            time, hour, day = get_string_time(tz)
            if kk == "always" or (kk == "default" and hour >= 18 and day == 5):
                # Get a random kk song from anything in the kk folder
                regular = False
                file = random.choice(os.listdir(f"{MUSIC_FOLDER}/kk"))
                tune = f"{MUSIC_FOLDER}/kk/{file}"
                name = "K.K."
            else:
                if server["game"] == "all":
                    game = random.choice(GAMES)
                else:
                    game = server["game"]

                if server["weather"] == "live":
                    weather = await get_weather(server.get("area", "london"))
                    code = weather.get("current", {}).get("condition", {}).get("code")
                    condition = get_weather_type(code)
                elif server["weather"] == "random":
                    condition = random.choice(["raining", "sunny", "snowing"])
                else:
                    condition = server.get("weather", "sunny")

                if condition == "raining" and game == "animal-crossing":
                    condition = "snowing"

                regular = True
                tune = f"{MUSIC_FOLDER}/{game}/{condition}/{time}.ogg"
                name = " ".join(word.capitalize() for word in game.split("-"))
                file = ""

            voice_client.play(FFmpegPCMAudio(tune))
            duration = audiofile.duration(tune)

            embed = await create_embed(
                title=f"Playing {name} Music",
                description=f"It is {time} and sunny"
                if regular
                else f"Playing {file.strip('.mp3')}",
                color=discord.Color.green(),
            )
            embed.set_footer(text=f"{round(duration)}s | {tz}")
            await voice_channel.send(embed=embed)

            await asyncio.sleep(duration)  # Sleep until the end of the track

        # Disconnect from the voice channel
        await voice_client.disconnect()
        await interaction.response.send_message(
            embed=await create_embed(
                title="Stopping",
                description="You left the vc. Stopping playing music",
                color=discord.Color.orange(),
            )
        )

    client.loop.create_task(play_music())


@client.tree.command(
    name="stop",
    description="Stop playing music",
)
async def stop(interaction: Interaction):
    guild = interaction.guild
    if not guild:
        return await interaction.response.send_message(
            embed=await create_embed(
                title="Error",
                description="Could not get guild info",
            )
        )

    voice_client = guild.voice_client

    if type(voice_client) != discord.VoiceClient:
        return await interaction.response.send_message(
            embed=await create_embed(
                title="Error",
                description="Could not get voice client",
            )
        )

    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await voice_client.disconnect()

        return await interaction.response.send_message(
            embed=await create_embed(
                title="Music Stopped",
                description="The music playback has been stopped.",
                color=discord.Color.green(),
            )
        )
    else:
        return await interaction.response.send_message(
            embed=await create_embed(
                title="Not Playing",
                description="There is no music currently playing.",
                color=discord.Color.orange(),
            )
        )


@client.tree.command(
    name="time",
    description="Get current time",
)
async def time(interaction: Interaction):
    guild = interaction.guild
    if not guild:
        return await interaction.response.send_message(
            embed=await create_embed(
                title="Error",
                description="Could not get guild info",
            )
        )

    server = server_collection.find_one({"id": guild.id})
    if server:
        return await interaction.response.send_message(
            embed=await create_embed(
                title="Info",
                description=f'Your timezone is set to `{server.get("timezone", None)}`',
                color=discord.Color.yellow(),
            )
        )
    else:
        return await interaction.response.send_message(
            embed=await create_embed(
                title="Error",
                description="Could not connect to the database. Please try again later",
                color=discord.Color.red(),
            )
        )


async def timezone_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> typing.List[app_commands.Choice]:
    timezones = pytz.all_timezones
    return [
        app_commands.Choice(name=timezone, value=timezone)
        for timezone in timezones
        if current.lower() in timezone.lower()
    ]


@client.tree.command(name="timezone", description="Set your timezone")
@app_commands.autocomplete(timezone=timezone_autocomplete)
@app_commands.describe(timezone="Your server's timezone")
async def timezone(interaction: Interaction, timezone: str):
    # Check if timezone is in pytz.all_timezones. check case insensitive
    for tz in pytz.all_timezones:
        if tz.lower() == timezone.lower():
            break
    else:
        return await interaction.response.send_message(
            embed=await create_embed(
                title="Error",
                description="Invalid timezone",
                color=discord.Color.red(),
            )
        )
    guild = interaction.guild
    if not guild:
        return await interaction.response.send_message(
            embed=await create_embed(
                title="Error",
                description="Could not get guild info",
            )
        )
    old_tz = server_collection.find_one_and_update(
        {"id": guild.id}, {"$set": {"timezone": timezone}}
    )["timezone"]

    return await interaction.response.send_message(
        embed=await create_embed(
            title="Timezone Updated",
            description=f"Timezone for `{guild.name}` has been changed from `{old_tz}` to `{timezone}`",  # NOQA
            color=discord.Color.green(),
        )
    )


@client.tree.command(name="kk", description="Set when you want KK songs to play")
@app_commands.describe(setting="When you want KK songs to play")
@app_commands.choices(
    setting=[
        app_commands.Choice(name="Always", value="always"),
        app_commands.Choice(name="Never", value="never"),
        app_commands.Choice(name="Default (after 6pm on Saturday)", value="default"),
    ]
)
async def kk(interaction: discord.Interaction, setting: app_commands.Choice[str]):
    guild = interaction.guild
    if not guild:
        return await interaction.response.send_message(
            embed=await create_embed(
                title="Error",
                description="Could not get guild info",
            )
        )
    kk = setting.value
    old_kk = server_collection.find_one_and_update(
        {"id": guild.id}, {"$set": {"kk": kk}}
    )["kk"]

    return await interaction.response.send_message(
        embed=await create_embed(
            title="KK Settings Updated",
            description=f"KK setting for `{guild.name}` has been changed from `{old_kk}` to `{kk}`",  # NOQA
            color=discord.Color.green(),
        )
    )


@client.tree.command(name="weather", description="Choose weather type for music")
@app_commands.describe(
    setting="Choose if you want live weather, random or specific type"
)  # NOQA
@app_commands.choices(
    setting=[
        app_commands.Choice(name="Live", value="live"),
        app_commands.Choice(name="Random", value="random"),
        app_commands.Choice(name="sunny", value="sunny"),
        app_commands.Choice(name="Raining", value="raining"),
        app_commands.Choice(name="Snowy", value="snowing"),
    ]
)
async def weather(interaction: discord.Interaction, setting: app_commands.Choice[str]):
    guild = interaction.guild
    if not guild:
        return await interaction.response.send_message(
            embed=await create_embed(
                title="Error",
                description="Could not get guild info",
            )
        )
    weather = setting.value
    old_weather = server_collection.find_one_and_update(
        {"id": guild.id}, {"$set": {"weather": weather}}
    )["weather"]

    return await interaction.response.send_message(
        embed=await create_embed(
            title="Weather Settings Updated",
            description=f"Weather setting for `{guild.name}` has been changed from `{old_weather}` to `{weather}`",  # NOQA
            color=discord.Color.green(),
        )
    )


@client.tree.command(name="area", description="Choose area for live weather")
@app_commands.describe(setting="Post/zip code or city name")  # NOQA
async def area(interaction: discord.Interaction, setting: app_commands.Choice[str]):
    guild = interaction.guild
    if not guild:
        return await interaction.response.send_message(
            embed=await create_embed(
                title="Error",
                description="Could not get guild info",
            )
        )
    area = setting.value
    old_area = server_collection.find_one_and_update(
        {"id": guild.id}, {"$set": {"area": area}}
    )["area"]

    return await interaction.response.send_message(
        embed=await create_embed(
            title="Area Settings Updated",
            description=f"Area setting for `{guild.name}` has been changed from `{old_area}` to `{area}`",  # NOQA
            color=discord.Color.green(),
        )
    )


try:
    print("Pinging DB")
    db_client.admin.command("ping")
    print("DB pinged successfully & vars set successfully - logging into the bot")
    client.run(os.environ["BOT_TOKEN"])
except BaseException as e:
    print(f"ERROR WITH LOGGING IN: {e}")
