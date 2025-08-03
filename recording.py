import asyncio
import wave
import discord
from discord.ext import commands, voice_recv
import torch
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
    model=AutoModelForSpeechSeq2Seq.from_pretrained(MODEL_ID, torch_dtype=dtype, low_cpu_mem_usage=True, use_safetensors=True).to(device),
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    return_timestamps=True,
    device=device,
    torch_dtype=dtype,
    generate_kwargs={"language": "english", "task": "transcribe"}
)


def pcm_to_wav(pcm_data, wavfile = 'sample', bitrate = 48000):
    with wave.open(wavfile+'.wav', 'wb') as wavefile:
        wavefile.setparams((1, 2, bitrate, 0, 'NONE', 'NONE'))
        wavefile.writeframes(pcm_data)

async def stt(audiofile):
    return pipe(audiofile)

# - discord.quoter Setup -
TOKEN = 'MTM3MDYwMjk5Mjc3NjI1MzUzMQ.G6W0RR.avQa1j_tnylZfNa6kCcM8R2Q4t0AXau445ribg'  # Replace with your bot token
GUILD_ID = 123456789012345678  # Replace with your server's ID
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

discord.opus._load_default()
bot = commands.Bot(command_prefix="!", intents=intents)

class Wav(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pcm_data: bytes = b''

    @commands.command()
    async def record(self, ctx):
        def callback(user, data: voice_recv.VoiceData):
            print(f"Got packet from {user}")
            self.pcm_data += data.pcm
        if ctx.author.voice is None:
            await ctx.send("Please join a voice channel first.")
            return
        try:
            vc = await ctx.author.voice.channel.connect(cls=voice_recv.VoiceRecvClient, self_mute=True, reconnect=False)
            vc.listen(voice_recv.BasicSink(callback))
            while True:
                await asyncio.sleep(5)
                pcm_to_wav(self.pcm_data, bitrate=ctx.voice_client.channel.bitrate, wavfile='temp')
                asyncio.run(stt, )
        except discord.errors.ConnectionClosed as e:
            print("Error: "+ str(e))
            return

    @commands.command()
    async def stop(self, ctx):
        pcm_to_wav(self.pcm_data, bitrate=ctx.voice_client.channel.bitrate)
        self.pcm_data = b''
        await ctx.voice_client.disconnect()

    @commands.command()
    async def kill(self, ctx):
        await ctx.send("Dying")
        print(str(ctx.author) + " killed me")
        await ctx.bot.close()

class Manager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def start(self, ctx):
        pass

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.event
async def setup_hook():
    await bot.add_cog(Wav(bot))


bot.run(TOKEN)
