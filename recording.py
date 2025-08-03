import asyncio
import wave
import discord
import torch
from discord.ext import commands, voice_recv
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq, pipeline

# — Whisper Setup —
MODEL_ID = "openai/whisper-large-v3"
print(torch.cuda.is_available())
device    = "cuda" if torch.cuda.is_available() else "cpu"
dtype     = torch.float16 if device == "cuda" else torch.float32
processor = AutoProcessor.from_pretrained(MODEL_ID)
print('Before Pipeline')
pipe = pipeline(
    "automatic-speech-recognition",
    model=AutoModelForSpeechSeq2Seq.from_pretrained(MODEL_ID, torch_dtype=dtype, low_cpu_mem_usage=False, use_safetensors=True).to(device),
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    return_timestamps=True,
    batch_size=4,
    device=device,
    torch_dtype=dtype,
    generate_kwargs={"language": "english", "task": "transcribe"}
)

WAV_PATH = 'sample'
def pcm_to_wav(pcm_data, wavfile = WAV_PATH, bitrate = 48000):
    with wave.open(wavfile+'.wav', 'wb') as wavefile:
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
        self.running = False
        self.pcm_int = b''
        self.data_int: list[bytes] = []
        self.transcript = {}

    @commands.command()
    async def record(self, ctx):
        users = []
        def callback(user, data: voice_recv.VoiceData):
            if user not in users:
                print(f"Got first packet from {user}")
                users.append(user)
            self.pcm_int += data.pcm

        if ctx.author.voice is None:
            await ctx.send("Please join a voice channel first.")
            return

        vc = await ctx.author.voice.channel.connect(cls=voice_recv.VoiceRecvClient, self_mute=True, reconnect=False)
        vc.listen(voice_recv.BasicSink(callback))
        self.running = True
        while self.running:
            await asyncio.sleep(10)
            if len(self.data_int) >= 4:
                self.data_int = self.data_int[1:]
            self.data_int.append(self.pcm_int)
            self.pcm_int = b''.join(self.data_int)
            pcm_to_wav(self.pcm_int, bitrate=ctx.voice_client.channel.bitrate)
            self.pcm_int = b''
            self.transcript = pipe(WAV_PATH + '.wav')
            print(self.transcript['text'])
            print(self.transcript['chunks'])

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

@bot.event
async def setup_hook():
    await bot.add_cog(Wav(bot))


bot.run(TOKEN)
