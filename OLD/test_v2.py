import discord
from discord.ext import commands
from discord.ext import voice_recv
from collections import defaultdict
import wave
import subprocess
from faster_whisper import WhisperModel

# — Bot setup —
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states   = True
bot = commands.Bot(command_prefix="!", intents=intents)

# — Globals —
recorder: voice_recv.AudioSink = None
model = WhisperModel("base.en", device="cuda", compute_type="float16")

# — Recorder class —
class PCMRecorder(voice_recv.AudioSink):
    def __init__(self):
        super().__init__()
        self.buffers = defaultdict(bytearray)
    def wants_opus(self) -> bool:
        return False
    def write(self, user, data):
        if user is None:
            return
        self.buffers[user.id].extend(data.pcm)
    def cleanup(self):
        return self.buffers

# — Commands —

@bot.command()
async def join(ctx):
    if ctx.author.voice and ctx.author.voice.channel:
        await ctx.author.voice.channel.connect(cls=voice_recv.VoiceRecvClient)
        await ctx.send("Joined VC.")
    else:
        await ctx.send("You’re not in a voice channel.")

@bot.command()
async def leave(ctx):
    vc = ctx.voice_client
    if vc:
        vc.stop_listening()
        await vc.disconnect()
        await ctx.send("Left VC.")

@bot.command()
async def startrecording(ctx):
    global recorder
    vc = ctx.voice_client
    if not vc:
        return await ctx.send("Join a VC first.")
    recorder = PCMRecorder()
    vc.listen(recorder)
    await ctx.send("Recording started; speak freely.")

@bot.command()
async def stoprecording(ctx):
    global recorder

    # make sure a recording is in progress
    if recorder is None:
        return await ctx.send("No recording in progress.")

    # stop the voice listener
    vc = ctx.voice_client
    if vc:
        vc.stop_listening()

    await ctx.send("Recording stopped. Processing audio...")

    # now recorder.buffers is safe to consume
    for uid, pcm in recorder.cleanup().items():
        if len(pcm) < 48000 * 2 * 1:
            continue

        wav48 = f"{ctx.guild.id}_{uid}_48k.wav"
        with wave.open(wav48, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(pcm)

        wav16 = wav48.replace("_48k.wav", "_16k.wav")
        subprocess.run([
            "ffmpeg", "-y",
            "-i", wav48,
            "-ar", "16000",
            "-ac", "1",
            wav16
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        segments, _ = model.transcribe(
            wav16,
            language="en",
            beam_size=5,
            temperature=0.0,
            no_speech_threshold=0.6,
            condition_on_previous_text=False,
            vad_filter=True,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        if text:
            await ctx.send(f"<@{uid}> said:\n> {text}")

    recorder = None
    await ctx.send("All transcripts posted.")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

bot.run("MTM3MDYwMjk5Mjc3NjI1MzUzMQ.G6W0RR.avQa1j_tnylZfNa6kCcM8R2Q4t0AXau445ribg")
