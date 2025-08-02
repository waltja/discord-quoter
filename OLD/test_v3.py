import os
import torch
import wave
import subprocess
from collections import defaultdict
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
from discord.ext import commands, voice_recv
import discord

# — Bot & Intents —
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states   = True
bot = commands.Bot(command_prefix="!", intents=intents)

# — Whisper‑Large‑V3 setup —
device    = "cuda:0" if torch.cuda.is_available() else exit("no CUDA")
torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

model_id = "openai/whisper-large-v3"
import os
import logging
import warnings

# — 1) Suppress Discord voice_state INFO logs —
logging.getLogger('discord.voice_state').setLevel(logging.WARNING)

# — 2) Silence Transformers FutureWarnings and specific Whisper warnings —
warnings.filterwarnings('ignore', category=FutureWarning)  # all FutureWarnings
warnings.filterwarnings(
    'ignore',
    message=r"The attention mask is not set and cannot be inferred.*"
)
warnings.filterwarnings(
    'ignore',
    message=r"Whisper did not predict an ending timestamp.*"
)

# — 3) When you load your model, force eager attention to remove that warning —
from transformers import AutoModelForSpeechSeq2Seq

model = AutoModelForSpeechSeq2Seq.from_pretrained(
    model_id,
    torch_dtype=torch_dtype,
    low_cpu_mem_usage=False,
    use_safetensors=True,
    # if this kwarg isn’t accepted, do it immediately after:
    #   model.config.attn_implementation = "eager"
    attn_implementation="eager"
)

# — 4) In your pipeline, lock to English to skip the “will default to language detection” warning —
from transformers import AutoProcessor, pipeline

processor = AutoProcessor.from_pretrained(model_id)

# tell Whisper to transcribe (not translate) into English
forced_decoder_ids = processor.get_decoder_prompt_ids(
    language="en",
    task="transcribe"
)

pipe = pipeline(
    "automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    return_timestamps="word",
    chunk_length_s=30,
    stride_length_s=(5, 5),
    device=device,
    torch_dtype=torch_dtype,
    generate_kwargs={"forced_decoder_ids": forced_decoder_ids}
)


# — Globals —
recorder        = None
candidate_map   = {}  # msg.id -> (uid, start, text)

# — PCM Recorder —
class PCMRecorder(voice_recv.AudioSink):
    def __init__(self):
        super().__init__()
        self.buffers = defaultdict(bytearray)
    def wants_opus(self) -> bool:
        return False
    def write(self, user, data):
        if user:  # drop unknown SSRCs
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
        await ctx.send("You need to be in a voice channel.")

@bot.command()
async def leave(ctx):
    vc = ctx.voice_client
    if vc:
        vc.stop_listening()
        await vc.disconnect()
        await ctx.send("Left VC.")

@bot.command()
async def startrecording(ctx):
    global recorder, candidate_map
    vc = ctx.voice_client
    if not vc:
        return await ctx.send("Join a voice channel first.")
    recorder = PCMRecorder()
    vc.listen(recorder)
    candidate_map.clear()
    await ctx.send("Recording started.")

@bot.command()
async def stoprecording(ctx):
    global recorder, candidate_map
    vc = ctx.voice_client
    if vc:
        vc.stop_listening()
    if recorder is None:
        return await ctx.send("No recording in progress.")
    await ctx.send("Recording stopped. Transcribing...")

    for uid, pcm in recorder.cleanup().items():
        # skip very short
        if len(pcm) < 48000 * 2 * 1:
            continue

        # 1) write 48 kHz WAV
        wav48 = f"{ctx.guild.id}_{uid}_48k.wav"
        with wave.open(wav48, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(pcm)

        # 2) resample to 16 kHz
        wav16 = wav48.replace("_48k.wav", "_16k.wav")
        subprocess.run([
            "ffmpeg", "-y",
            "-i", wav48,
            "-ar", "16000", "-ac", "1",
            wav16
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 3) run HF Whisper pipeline
        result = pipe(wav16)
        # result["chunks"] is a list of dicts with 'text','timestamp'
        for chunk in result.get("chunks", []):
            text  = chunk.get("text", "").strip()
            ts    = chunk.get("timestamp", (None, None))
            start = ts[0]
            if text and start is not None:
                msg = await ctx.send(f"⏱ {start:.1f}s — <@{uid}>: “{text}”")
                candidate_map[msg.id] = (uid, start, text)

    recorder = None
    await ctx.send("All segments posted. React with 📌 to approve.")

@bot.event
async def on_reaction_add(reaction, user):
    # only handle 📌 on candidate messages
    if reaction.emoji == "📌" and reaction.message.id in candidate_map:
        uid, start, text = candidate_map.pop(reaction.message.id)
        # post approved quote to #quotes
        quotes = discord.utils.get(reaction.message.guild.text_channels, name="quotes")
        if quotes:
            await quotes.send(f"🗨️ <@{uid}> at {start:.1f}s:\n> {text}")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

bot.run("MTM3MDYwMjk5Mjc3NjI1MzUzMQ.G6W0RR.avQa1j_tnylZfNa6kCcM8R2Q4t0AXau445ribg")

