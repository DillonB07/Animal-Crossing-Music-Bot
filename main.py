import discord
from discord.ext import commands, tasks
from discord import FFmpegPCMAudio, PCMVolumeTransformer, opus
from utils import create_embed, handle_error, NoVCError, get_string_time

from datetime import datetime
import asyncio
import audiofile
import os
import pytz
import random
import sys

# opus.load_opus()

ADMINS = [915670836357247006, 658650587679948820, 1015577382826020894]
FFMPEG_OPTIONS = {
    'before_options':
        '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}
MUSIC_FOLDER = 'music'
GAMES = ['animal-crossing', 'new-horizons', 'new-leaf', 'wild-world']

timezone = pytz.timezone('Europe/London')


class Bot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="ac!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Synced slash commands for {self.user}")

    async def on_command_error(self, ctx, error):
        await handle_error(ctx, error, ephemeral=True)


bot = Bot()


@bot.event
async def on_ready():
    print("Ready")
    time = get_string_time()[0]
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"AC {time} music"))


@tasks.loop(minutes=5)
async def update_presence():
    time = get_string_time()[0]
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"AC {time} music"))


@bot.hybrid_command(name="restart",
                    with_app_command=True,
                    description="Restart the bot")
async def restart(ctx):
    await ctx.defer(ephemeral=False)
    if not ctx.author.id in ADMINS:
        await ctx.reply(embed=await create_embed())
        return
    await ctx.reply(embed=await create_embed(
        title="Restarting",
        description=f"Restart ordered by {ctx.author.mention}"))

    sys.exit()


@bot.hybrid_command(
    name="ping",
    description="Check bot latency",
    with_app_command=True,
)
async def ping(ctx):
    await ctx.defer(ephemeral=True)
    if round(bot.latency * 1000) <= 50:
        embed = discord.Embed(
            title="PING",
            description=
            f":ping_pong: Pong! Bot's latency  is **{(bot.latency * 1000)}** ms!",
            color=0x44FF44,
        )
    elif round(bot.latency * 1000) <= 100:
        embed = discord.Embed(
            title="PING",
            description=
            f":ping_pong: Pong! Bot's latency  is **{round(bot.latency * 1000)}** ms!",
            color=0xFFD000,
        )
    elif round(bot.latency * 1000) <= 200:
        embed = discord.Embed(
            title="PING",
            description=
            f":ping_pong: Pong! Bot's latency  is **{round(bot.latency * 1000)}** ms!",
            color=0xFF6600,
        )
    else:
        embed = discord.Embed(
            title="PING",
            description=
            f":ping_pong: Pong! Bot's latency  is **{round(bot.latency * 1000)}** ms!",
            color=0x990000,
        )
    await ctx.reply(embed=embed)


@bot.hybrid_command(name="join",
                    description="Join a vc",
                    with_app_command=True)
async def join(ctx, channel: discord.VoiceChannel = None):
    await ctx.defer(ephemeral=False)

    if not channel:
        channel = ctx.author.voice.channel
        if not channel:
            return await ctx.reply(title='Could not join VC',
        description='Make sure to specify a voice channel or be in a vc')

    await channel.connect(reconnect=True)
    return await ctx.reply(
embed=await create_embed(title='Success',
description='Joined voice channel',
color=discord.Color.green()))


@bot.hybrid_command(name='play', description="Start playing music", with_app_command=True)
async def play(ctx):
    await ctx.defer(ephemeral=False)

    voice_channel = ctx.author.voice.channel
    voice_client = ctx.guild.voice_client
    if not voice_client:
        if not voice_channel:
            raise NoVCError()
        voice_client = await voice_channel.connect()

    async def play_music():
        while True:
            game = random.choice(GAMES)
            time, current_hour = get_string_time()

            tune = f"{MUSIC_FOLDER}/{game}/sunny/{time}.ogg"

            voice_client.play(FFmpegPCMAudio(tune))
            duration = audiofile.duration(tune)

            await ctx.send(embed=await create_embed(
                title=f'Started playing {" ".join(word.capitalize() for word in game.split("-"))} music',
                description=f"It is {time} and sunny",
                color=discord.Color.green()
            ))

            await asyncio.sleep(duration)  # Sleep until the end of the track

            # Check if the bot should continue playing
            new_hour = datetime.now(timezone).hour
            if current_hour != new_hour or voice_channel != voice_client.channel:
                break

        # Disconnect from the voice channel
        await voice_client.disconnect()
        await ctx.send(embed=await create_embed(title="Stopping",
                                                description="You left vc or the hour changed. Stopping playing music"))

    bot.loop.create_task(play_music())


@bot.hybrid_command(name='stop', description='Stop playing music', with_app_command=True)
async def stop(ctx):
    await ctx.defer(ephemeral=False)

    voice_client = ctx.guild.voice_client

    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await voice_client.disconnect()

        await ctx.send(embed=await create_embed(
            title='Music Stopped',
            description='The music playback has been stopped.',
            color=discord.Color.red()
        ))
    else:
        await ctx.send(embed=await create_embed(
            title='Music Not Playing',
            description='There is no music currently playing.',
            color=discord.Color.orange()
        ))


try:
    bot.run(os.environ["BOT_TOKEN"])
except BaseException as e:
    print(f"ERROR WITH LOGGING IN: {e}")
