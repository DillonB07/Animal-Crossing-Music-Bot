import asyncio
import os
import random
import sys

import audiofile
import discord
import pytz
from discord import FFmpegPCMAudio, Interaction, app_commands
from discord.ext import tasks
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

from utils import NoVCError, create_embed, get_string_time, handle_error

load_dotenv()
# opus.load_opus()

ADMINS = [915670836357247006, 658650587679948820, 1015577382826020894]
FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}
MUSIC_FOLDER = "music"
GAMES = ["animal-crossing", "new-horizons", "new-leaf", "wild-world"]

timezone = pytz.timezone("Europe/London")

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
    }
    server_collection.insert_one(server_doc)


@client.event
async def on_guild_remove(guild):
    server_collection.find_one_and_delete({"id": guild.id})


@client.tree.command(name="restart", description="Restart the bot")
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
    name="join",
    description="Join a vc",
)
async def join(interaction: Interaction):
    if type(interaction.user) != discord.Member:
        return await interaction.response.send_message(
            embed=await create_embed(
                title="Error",
                description="Something strange happened, please try again",
            )
        )
    voice = interaction.user.voice
    if not voice:
        raise NoVCError()
    channel = voice.channel
    if not channel:
        raise NoVCError()
    await channel.connect(reconnect=True)
    return await interaction.response.send_message(
        embed=await create_embed(
            title="Success",
            description="Joined voice channel",
            color=discord.Color.green(),
        )
    )


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

    async def play_music():
        while True:
            game = random.choice(GAMES)
            time = get_string_time()[0]

            tune = f"{MUSIC_FOLDER}/{game}/sunny/{time}.ogg"

            if type(voice_client) != discord.VoiceClient:
                print(type(voice_client))
                return await interaction.response.send_message(
                    embed=await create_embed(
                        title="Error",
                        description="Could not get voice client",
                    )
                )
            voice_client.play(FFmpegPCMAudio(tune))
            duration = audiofile.duration(tune)
            name = " ".join(word.capitalize() for word in game.split("-"))

            await interaction.response.send_message(
                embed=await create_embed(
                    title=f"Started playing {name} music",
                    description=f"It is {time} and sunny",
                    color=discord.Color.green(),
                )
            )

            await asyncio.sleep(duration)  # Sleep until the end of the track

            if voice_channel != voice_client.channel:
                break

        # Disconnect from the voice channel
        await voice_client.disconnect()
        await interaction.response.send_message(
            embed=await create_embed(
                title="Stopping",
                description="You left vc or the hour changed. Stopping playing music",
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
                color=discord.Color.red(),
            )
        )
    else:
        return await interaction.response.send_message(
            embed=await create_embed(
                title="Music Not Playing",
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
                color=discord.Color.green(),
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


# @client.tree(name="set", description="Set a setting")
# async def set(interaction: Interaction):
#     pass


# @set.command(name="timezone", description="Set the timezone")
# @app_commands.describe(
#     timezone="Timezone for live music",
# )
# async def set_timezone(interaction: Interaction, timezone: str):
#     pass


try:
    print("Pinging DB")
    db_client.admin.command("ping")
    print("DB pinged successfully & vars set successfully - logging into the bot")
    client.run(os.environ["BOT_TOKEN"])
except BaseException as e:
    print(f"ERROR WITH LOGGING IN: {e}")
