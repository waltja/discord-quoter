import subprocess

import discord
import asyncio
import wave
from discord.ext import commands
from collections import defaultdict
from faster_whisper import WhisperModel

# ---------- Bot & Intents ----------
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states   = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- Globals ----------
recorder         = None
transcribe_task  = None
model = WhisperModel("medium.en", device="cuda", compute_type="float16")


# ---------- Custom PCM Recorder ----------
from collections import defaultdict
from discord.ext import voice_recv

class PCMRecorder(voice_recv.AudioSink):
    def __init__(self):
        super().__init__()
        self.buffers = defaultdict(bytearray)

    def wants_opus(self) -> bool:
        return False

    def write(self, user, data):
        if user is None:
            return   # drop unmapped packets
        self.buffers[user.id].extend(data.pcm)

    def cleanup(self):
        return self.buffers


# ---------- Transcription Loop ----------
import wave
import asyncio
from functools import partial

# helper that runs in a ThreadPoolExecutor
def transcribe_chunk(model, guild_id, uid, pcm_bytes):
    # 1) write raw 48 kHz WAV
    wav48 = f"{guild_id}_{uid}_48k.wav"
    with wave.open(wav48, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(48000)
        wf.writeframes(pcm_bytes)

    # 2) resample to 16 kHz
    wav16 = f"{guild_id}_{uid}_16k.wav"
    subprocess.run([
        "ffmpeg", "-y",
        "-i", wav48,
        "-ar", "16000",
        "-ac", "1",
        wav16
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 3) feed the 16 kHz file to Whisper
    segments, _ = model.transcribe(
        wav16,
        language="en",
        beam_size=5,
        temperature=0.0,
        no_speech_threshold=0.6,
        condition_on_previous_text=False,
        vad_filter=True,
    )
    return " ".join(seg.text.strip() for seg in segments).strip()

async def transcription_loop(ctx, interval=15):
    loop = asyncio.get_event_loop()
    while True:
        await asyncio.sleep(interval)
        tasks = []
        guild = ctx.guild.id

        # snapshot and clear buffers to avoid repeats
        for uid, pcm in list(recorder.buffers.items()):
            if len(pcm) < 48000*2*3:
                continue
            pcm_bytes = bytes(pcm)
            recorder.buffers[uid].clear()
            fn = partial(transcribe_chunk, model, guild, uid, pcm_bytes)
            tasks.append(loop.run_in_executor(None, fn))

        # gather and post
        for text in await asyncio.gather(*tasks):
            if text:
                # extract uid from the task order, or embed in returned tuple
                await ctx.send(f"{text}")


# ---------- Commands ----------
from discord.ext import voice_recv

@bot.command()
@commands.has_role('BeBetter')
async def join(ctx):
    if ctx.author.voice and ctx.author.voice.channel:
        # note the cls=…
        await ctx.author.voice.channel.connect(
            cls=voice_recv.VoiceRecvClient
        )
        await ctx.send("Joined (with receive enabled).")

@bot.command()
async def leave(ctx):
    if vc := ctx.voice_client:
        vc.stop_listening()
        await vc.disconnect()
        await ctx.send("Left VC.")

@bot.command()
async def startrecording(ctx):
    global recorder, transcribe_task
    vc = ctx.voice_client
    if not vc:
        return await ctx.send("I need to be in a VC first.")
    recorder = PCMRecorder()
    vc.listen(recorder)                # begin receive
    transcribe_task = bot.loop.create_task(transcription_loop(ctx))
    await ctx.send("Recording started.")

@bot.command()
async def stoprecording(ctx):
    vc = ctx.voice_client
    if vc:
        vc.stop_listening()            # stop receive
    if transcribe_task:
        transcribe_task.cancel()
    await ctx.send("Recording stopped.")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# ---------- Run ----------
bot.run("MTM3MDYwMjk5Mjc3NjI1MzUzMQ.G6W0RR.avQa1j_tnylZfNa6kCcM8R2Q4t0AXau445ribg")
