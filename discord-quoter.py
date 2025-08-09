import asyncio
import collections
import discord
from discord.ext import commands, voice_recv
import wave

def pcm_to_wav(pcm_data, wavfile='sample.wav', bitrate=48000):
    with wave.open(wavfile, 'wb') as wavefile:
        wavefile.setparams((1, 2, bitrate, 0, 'NONE', 'NONE'))
        wavefile.writeframes(pcm_data)

# ---------------------- Main Class ---------------------- #
class Recorder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.listener: voice_recv.VoiceRecvClient
        self.bitrate = 48000
        self.user_queues: dict[str, asyncio.Queue] = {}  # {username: asyncio.Queue}
        self.active_tasks: dict[str, asyncio.Task] = {} # {username: asyncio.Task}

    def callback(self, user, data: voice_recv.VoiceData):
        if user.name not in self.user_queues and user.name != 'Quoter':
            self.user_queues[user.name] = asyncio.Queue()
            self.active_tasks[user.name] = asyncio.create_task(self.worker(user.name))
        # push pcm to queue (non-blocking)
        self.user_queues[user.name].put_nowait(data.pcm)

    async def worker(self, uname):
        """Process audio for one user."""
        buffer = [b'']
        timeout = 0
        try:
            while True:
                await asyncio.sleep(10)
                try:
                    for i in range(self.user_queues[uname].qsize()):
                        buffer.append(self.user_queues[uname].get_nowait())
                except asyncio.QueueEmpty:
                    timeout+=1
                    if timeout > 10:
                        self.active_tasks[uname].cancel()
                except Exception as e:
                    print(f'Exception occurred: {e}')

                if len(buffer) > 4:
                    del buffer[0]

                wav_path = f"{uname}.wav"
                pcm_to_wav(b''.join(buffer), wavfile=wav_path)
                print(f'Saved {uname}\'s audio to {wav_path}')
                # pipe to transcribe.stt(wav_path)
        except asyncio.CancelledError:
            # asyncio.Task.uncancel(self.active_tasks[uname]) # Perhaps don't need this?
            try:
                while True:
                    temp = self.user_queues[uname].get_nowait()
                    buffer.append(temp)
            except asyncio.QueueEmpty:
                self.user_queues[uname].shutdown(immediate=True)
                self.user_queues.pop(uname)

            wav_path = f"{uname}.wav"
            pcm_to_wav(b''.join(buffer), wavfile=wav_path, bitrate=self.bitrate)
            # pipe to transcribe.stt(wav_path)

            raise asyncio.CancelledError

    async def remove_worker(self, uname):
        # Cancel worker
        task: asyncio.Task = self.active_tasks.pop(uname)
        if task:
            task.cancel()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if (before.channel and not after.channel) and member.name != 'Quoter':  # user left a voice channel
            await self.remove_worker(member.name)

    @commands.command()
    async def record(self, ctx: commands.Context):
        if ctx.author.voice is None:
            await ctx.send("Join a voice channel first.")
            return

        self.bitrate = ctx.author.voice.channel.bitrate
        print(self.bitrate)
        # noinspection PyAttributeOutsideInit
        self.listener = await ctx.author.voice.channel.connect(cls=voice_recv.VoiceRecvClient, self_mute=True)

        for uname in {member.name for member in ctx.author.voice.channel.members}:
            if uname != 'Quoter':
                print(f'Starting task for: {uname}')
                self.user_queues[uname] = asyncio.Queue()
                self.active_tasks[uname] = asyncio.create_task(self.worker(uname))

        self.listener.listen(voice_recv.BasicSink(self.callback))
        # TODO: create ctx.send() for STT items

    @commands.command()
    async def stop(self, ctx: commands.Context):
        self.listener.stop()
        await ctx.voice_client.disconnect(force=True)
        for uname in self.user_queues:
            await self.remove_worker(uname)

    @commands.command()
    async def kill(self, ctx):
        await ctx.send("Dying")
        print(str(ctx.author) + " killed me")
        await ctx.bot.close()


# - discord.quoter Setup -
# noinspection SpellCheckingInspection
TOKEN = 'MTM3MDYwMjk5Mjc3NjI1MzUzMQ.G6W0RR.avQa1j_tnylZfNa6kCcM8R2Q4t0AXau445ribg'  # Replace with your bot token
SERVER_ID = 1102726131779633154  # Replace with your server's ID
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

# noinspection PyProtectedMember
discord.opus._load_default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.add_cog(Recorder(bot))

bot.run(TOKEN)