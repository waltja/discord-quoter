import discord, asyncio
from discord.ext import commands, voice_recv
import wave, transcribe, time
import database


def pcm_to_wav(pcm_data, wavfile='sample.wav', bitrate=16000):
    """Saves PCM data to wav file"""
    with wave.open(wavfile, 'wb') as wavefile:
        wavefile.setparams((1, 2, bitrate, 0, 'NONE', 'NONE'))
        wavefile.writeframes(pcm_data)


# ---------------------- Main Class ---------------------- #
class Recorder(commands.Cog):
    """Bot class that records, processes, and transcribes users audio"""
    def __init__(self, bot):
        self.bot = bot
        self.listener: voice_recv.VoiceRecvClient
        self.bitrate = 48000
        self.user_queues: dict[str, asyncio.Queue] = {}  # {username: asyncio.Queue}
        self.active_tasks: dict[str, asyncio.Task] = {} # {username: asyncio.Task}
        self.transcribe = None
        self.db = database.STTDatabase()

    def callback(self, user, data: voice_recv.VoiceData):
        """Callback function to be used with voice_recv listener sink"""
        if user.name not in self.user_queues and user.name != 'Quoter':
            self.user_queues[user.name] = asyncio.Queue()
            self.active_tasks[user.name] = asyncio.create_task(self.worker(user.name))
        # push pcm to queue (non-blocking)
        self.user_queues[user.name].put_nowait(data.pcm)

    async def worker(self, uname):
        """Process audio for one user."""
        buffer = [b'']
        temp = b''
        timeout = 0
        try:
            while True:
                await asyncio.sleep(10)
                try:
                    for i in range(self.user_queues[uname].qsize()):
                        temp += self.user_queues[uname].get_nowait()
                except asyncio.QueueEmpty:
                    timeout+=1
                    if timeout > 10:
                        self.active_tasks[uname].cancel()
                except Exception as e:
                    print(f'Exception occurred: {e}')

                if len(buffer) > 4:
                    del buffer[0]

                buffer.append(temp)
                temp = b''

                wav_path = f"{uname}.wav"
                pcm_to_wav(b''.join(buffer), wavfile=wav_path, bitrate=self.bitrate)
                print(f'Saved {uname}\'s audio to {wav_path}')
                if self.transcribe is not None:
                    transcription = await self.transcribe.stt(wav_path, (time.time() - 10*len(buffer)))
                    print(transcription['text'])
                    self.db.store_transcript(uname, transcription['timestamp'], transcription['text'])

        except asyncio.CancelledError:
            pass # TODO: create cleaner for leftover audio
        finally:
            raise asyncio.CancelledError

    async def remove_worker(self, uname):
        """Remove a worker and its associated queue."""
        # Cancel worker
        task: asyncio.Task = self.active_tasks.pop(uname)
        queue: asyncio.Queue = self.user_queues.pop(uname)
        if task:
            task.cancel()
        if queue:
            queue.shutdown()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Listener to remove a users worker and its associated queue."""
        if (before.channel and not after.channel) and member.name != 'Quoter':  # user left a voice channel
            await self.remove_worker(member.name)

    @commands.command()
    async def record(self, ctx: commands.Context):
        """Command to start recording the users voice call"""
        if ctx.author.voice is None:
            await ctx.send("Join a voice channel first.")
            return

        self.bitrate = ctx.author.voice.channel.bitrate
        # noinspection PyAttributeOutsideInit
        self.listener = await ctx.author.voice.channel.connect(cls=voice_recv.VoiceRecvClient, self_mute=True)

        for uname in {member.name for member in ctx.author.voice.channel.members}:
            if uname != 'Quoter':
                print(f'Starting task for: {uname}')
                self.user_queues[uname] = asyncio.Queue()
                self.active_tasks[uname] = asyncio.create_task(self.worker(uname))

        self.listener.listen(voice_recv.BasicSink(self.callback))
        self.transcribe = transcribe.Transcriber()

    @commands.command()
    async def stop(self, ctx: commands.Context):
        """Command to stop recording the users voice call"""
        self.listener.stop()
        await ctx.voice_client.disconnect(force=True)
        for uname, xx in list(self.user_queues.items()):
            await self.remove_worker(uname)
            # TEMP BOT KILL
        self.db.close()
        await ctx.bot.close()

    @commands.command()
    async def kill(self, ctx):
        """Command to stop the bot, should only be used when no active instances of record() are running."""
        await ctx.send("Dying")
        print(str(ctx.author) + " killed me")
        await ctx.bot.close()


# - discord.quoter Setup -
# noinspection SpellCheckingInspection
TOKEN = ''  # Replace with your bot token
SERVER_ID = 1102726131779633154  # Replace with your server's ID
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

# noinspection PyProtectedMember
discord.opus._load_default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    """Executes when the bot is online and ready."""
    print(f'Logged in as {bot.user}')
    await bot.add_cog(Recorder(bot))

bot.run(TOKEN)