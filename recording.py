import discord
from discord.ext import commands, voice_recv
import asyncio
import datetime
import os

TOKEN = 'MTM3MDYwMjk5Mjc3NjI1MzUzMQ.G6W0RR.avQa1j_tnylZfNa6kCcM8R2Q4t0AXau445ribg'  # Replace with your bot token
GUILD_ID = 123456789012345678  # Replace with your server's ID


intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

discord.opus._load_default()
bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)

class Wav(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def record(self, ctx):

        def callback(user, data: voice_recv.VoiceData):
            print(f"Got packet from {user}")
            print(data)

        if ctx.author.voice is None:
            await ctx.send("You need to be in a voice channel to use this command.")
            return

        vc = await ctx.author.voice.channel.connect(cls=voice_recv.VoiceRecvClient)
        vc.listen(voice_recv.BasicSink(callback))

    @commands.command()
    async def stop(self, ctx):
        await  ctx.voice_client.disconnect()

    @commands.command()
    async def die(self, ctx):
        ctx.voice_client.stop()
        await ctx.bot.close()

class Manager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command
    async def start(self, ctx):
        pass

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.event
async def setup_hook():
    await bot.add_cog(Wav(bot))


bot.run(TOKEN)
