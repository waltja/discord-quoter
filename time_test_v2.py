import os
import subprocess
import asyncio
import time
import torch
import discord
from discord.ext import commands, voice_recv
from collections import defaultdict
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq, pipeline

TOKEN = "MTM3MDYwMjk5Mjc3NjI1MzUzMQ.G6W0RR.avQa1j_tnylZfNa6kCcM8R2Q4t0AXau445ribg"
MODEL_ID = "openai/whisper-large-v3"

# — Whisper Setup —
device    = "cuda" if torch.cuda.is_available() else "cpu"
dtype     = torch.float16 if device == "cuda" else torch.float32
processor = AutoProcessor.from_pretrained(MODEL_ID)
model     = AutoModelForSpeechSeq2Seq.from_pretrained(
    MODEL_ID, torch_dtype=dtype, low_cpu_mem_usage=False, use_safetensors=True
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

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

class AudioClip(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.buffers = defaultdict(bytearray)

    def packet_callback(self, user, data: voice_recv.VoiceData):
        if user:
            self.buffers[user.id].extend(data.pcm)

    def save_pcm_to_wav(self, pcm_bytes, wav_path="clip.wav"):
        with open("raw_input.pcm", "wb") as f:
            f.write(pcm_bytes)
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "f32le",    # raw float32 PCM from BasicSink
            "-ar", "48000",
            "-ac", "1",
            "-i", "raw_input.pcm",
            "-ar", "16000",
            "-c:a", "pcm_s16le",
            wav_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @commands.command()
    async def clip(self, ctx):
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You need to be in a voice channel.")
        vc = await ctx.author.voice.channel.connect(
            cls=voice_recv.VoiceRecvClient
        )
        self.buffers.clear()
        sink = voice_recv.BasicSink(self.packet_callback)
        vc.listen(sink)
        await ctx.send("🎙 Recording 10 seconds...")
        await asyncio.sleep(10)
        vc.stop_listening()
        await vc.disconnect()

        if not self.buffers:
            return await ctx.send("No audio captured.")
        uid, pcm = max(self.buffers.items(), key=lambda kv: len(kv[1]))
        wav_file = f"{ctx.guild.id}_{uid}.wav"
        self.save_pcm_to_wav(pcm, wav_file)

        start = time.perf_counter()
        result = pipe(wav_file)
        duration = time.perf_counter() - start
        transcript = result["text"].strip()

        txt_file = wav_file.replace(".wav", ".txt")
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write(f"Transcription time: {duration:.2f}s\n\n{transcript}\n")

        await ctx.send(
            f"✅ Transcribed in {duration:.2f}s. "
            f"Saved `{wav_file}` and `{txt_file}`."
        )

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

bot.add_cog(AudioClip(bot))
bot.run(TOKEN)
