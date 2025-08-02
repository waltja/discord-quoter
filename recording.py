import discord
from discord.ext import commands
import asyncio
import datetime
import os

from discord.ext import audiorec  # This is from the discord-ext-audiorec library

TOKEN = 'YOUR_DISCORD_BOT_TOKEN'  # Replace with your bot token
GUILD_ID = 123456789012345678  # Replace with your server's ID

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
recording_manager = audiorec.RecordingManager()


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    bot.add_listener(recording_manager.on_packet, "on_voice_packet")


@bot.command()
async def record(ctx):
    if ctx.author.voice is None:
        await ctx.send("You need to be in a voice channel to use this command.")
        return

    voice_channel = ctx.author.voice.channel
    vc = await voice_channel.connect()

    await recording_manager.start(vc)
    await ctx.send("Recording started for 5 seconds...")

    await asyncio.sleep(5)

    audio = await recording_manager.stop(vc)
    await vc.disconnect()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"clip_{timestamp}.wav"

    await audio.save(filename)
    await ctx.send(f"Recording saved as {filename}")


bot.run(TOKEN)
