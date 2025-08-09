import asyncio
import collections
import discord
from discord.ext import commands, voice_recv

import wave
import torch
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq, pipeline

# — Whisper Setup —
MODEL_ID = "openai/whisper-large-v3"
print(torch.cuda.is_available())
device = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.float16 if device == "cuda" else torch.float32
processor = AutoProcessor.from_pretrained(MODEL_ID)
print('Before Pipeline')
pipe = pipeline(
    "automatic-speech-recognition",
    model=AutoModelForSpeechSeq2Seq.from_pretrained(MODEL_ID, torch_dtype=dtype, low_cpu_mem_usage=False,
                                                    use_safetensors=True).to(device),
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    return_timestamps=True,
    batch_size=4,
    device=device,
    torch_dtype=dtype,
    generate_kwargs={"language": "english", "task": "transcribe"}
)

WAV_PATH = 'sample'

def pcm_to_wav(pcm_data, wavfile=WAV_PATH, bitrate=48000):
    with wave.open(wavfile + '.wav', 'wb') as wavefile:
        wavefile.setparams((1, 2, bitrate, 0, 'NONE', 'NONE'))
        wavefile.writeframes(pcm_data)

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


class Wav(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.loop = asyncio.get_event_loop()
        self.running = False
        self.users: dict = {}
        self.pcm_int: dict = {}
        self.bitrate = 48000
        self.print = []

    def handle_user(self, user, ctx: commands.Context):
        data_int: list[bytes] = []
        self.pcm_int[user] = b''
        while self.users[user][0]:
            if len(data_int) >= 4:
                del data_int[0]
            data_int.append(self.pcm_int[user])
            self.pcm_int[user] = b''
            pcm_to_wav(b''.join(data_int), bitrate=self.bitrate, wavfile=WAV_PATH + '_' + user)
            data_int = []
            transcript = pipe(WAV_PATH + '_' + user + '.wav')
            print(user+' said: '+str(transcript['text']))
        print(user + ' left...')
        return


    @commands.command()
    async def record(self, ctx: commands.Context):

        def callback(user, data: voice_recv.VoiceData):
            user = str(user.name)
            if user not in self.users:
                # self.users[user] = [True, threading.Thread(target=self.handle_user, args=(user, ctx))]
                self.users[user][1].start()
                self.pcm_int.update({user: b''})
            self.pcm_int[user] += data.pcm

        if ctx.author.voice is None:
            await ctx.send("Please join a voice channel first.")
            return
        else:
            channel = ctx.author.voice.channel
            self.bitrate = channel.bitrate

        members_names = {member.name for member in channel.members}
        for user in self.users:
            # self.users[user] = [True, threading.Thread(target=self.handle_user, args=(user, ctx))]
            self.users[user][1].start()

        vc = await channel.connect(cls=voice_recv.VoiceRecvClient, self_mute=True)
        vc.listen(voice_recv.BasicSink(callback))

        self.running = True
        while self.running:
            members_names = {member.name for member in channel.members}
            for user in self.users:
                if user not in members_names:
                    self.users[user][0] = False
                    self.users[user][1].join()
                    self.users.pop(user)

            if len(self.print) > 0:
                for item in self.print:
                    await ctx.send(item)

        await ctx.voice_client.disconnect(force=False)
        return

    @commands.command()
    async def stop(self, ctx):
        self.running = False
        await ctx.voice_client.disconnect()

    @commands.command()
    async def kill(self, ctx):
        await ctx.send("Dying")
        print(str(ctx.author) + " killed me")
        await ctx.bot.close()


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.add_cog(Wav(bot))


@bot.event
async def setup_hook():
    await bot.add_cog(Wav(bot))


bot.run(TOKEN)
