import os
import subprocess
import time
import discord
from discord.ext import commands, voice_recv
from collections import defaultdict
import torch
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq, pipeline

# -------- Discord Bot Setup --------
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
TOKEN = "MTM3MDYwMjk5Mjc3NjI1MzUzMQ.G6W0RR.avQa1j_tnylZfNa6kCcM8R2Q4t0AXau445ribg"

# -------- Whisper-Large-v3 Setup --------
device = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.float16 if device == "cuda" else torch.float32
model_id = "openai/whisper-large-v3"

processor = AutoProcessor.from_pretrained(model_id)
model = AutoModelForSpeechSeq2Seq.from_pretrained(
    model_id,
    torch_dtype=dtype,
    low_cpu_mem_usage=False,
    use_safetensors=True
).to(device)

forced_decoder_ids = processor.get_decoder_prompt_ids(language="en", task="transcribe")

pipe = pipeline(
    "automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    return_timestamps=False,
    chunk_length_s=30,
    stride_length_s=(5, 5),
    device=0,
    torch_dtype=dtype,
    generate_kwargs={"forced_decoder_ids": forced_decoder_ids}
)

# -------- PCM Recorder --------
class ShortRecorder(voice_recv.AudioSink):
    def __init__(self):
        super().__init__()
        self.buffer = defaultdict(bytearray)

    def wants_opus(self) -> bool:
        return False

    def write(self, user, data):
        if user is not None:
            self.buffer[user.id].extend(data.pcm)

    def get_clip(self, uid):
        return bytes(self.buffer.get(uid, b""))

    def cleanup(self):
        return self.buffer

# -------- Utility: Save PCM to 16k WAV --------
import subprocess

def save_pcm_to_wav(pcm_bytes, filename="sample.wav"):
    # dump raw float32 PCM
    with open("../raw_input.pcm", "wb") as f:
        f.write(pcm_bytes)

    # have FFmpeg read f32le and downsample to 16 kHz, 16‑bit WAV
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "f32le",         # ← raw float32
        "-ar", "48000",        # ← input sample rate
        "-ac", "1",            # ← mono
        "-i", "raw_input.pcm",
        "-ar", "16000",        # ← output sample rate
        "-c:a", "pcm_s16le",   # ← 16‑bit PCM
        filename
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


import asyncio
# -------- !clip Command --------
@bot.command()
async def clip(ctx):
    # if not ctx.author.voice or not ctx.author.voice.channel:
    #     return await ctx.send("You need to be in a voice channel.")
    channel = bot.get_channel(1328180896859164704)
    vc = await channel.connect(cls=voice_recv.VoiceRecvClient)
    await ctx.send("🎙 Recording 10 seconds...")

    def callback(user, data: voice_recv.VoiceData):
        print(f"Got packet from {user}")

    recorder = voice_recv.BasicSink(callback)
    vc.listen(recorder)
    await asyncio.sleep(10)       # ← fixed here
    vc.stop_listening()
    await vc.disconnect()

    buffers = recorder.cleanup()
    if not buffers:
        return await ctx.send("No audio captured.")

    uid = max(buffers, key=lambda k: len(buffers[k]))
    pcm_data = recorder.get_clip(uid)

    save_pcm_to_wav(pcm_data, "../sample.wav")

    start = time.perf_counter()
    result = pipe("sample.wav")
    duration = time.perf_counter() - start

    text = result["text"].strip()
    with open("../sample.txt", "w", encoding="utf-8") as f:
        f.write(f"Transcription time: {duration:.2f} s\n\n{text}\n")

    await ctx.send(f"✅ Transcribed in {duration:.2f}s. Saved `sample.wav` & `sample.txt`.")

# -------- Run Bot --------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

bot.run(TOKEN)
