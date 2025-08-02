# python_audio_processor.py
# Watches for .pcm files, converts to .wav with padding, transcribes via Whisper, and posts to Discord

import os
import subprocess
import asyncio
from pathlib import Path
from pydub import AudioSegment
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
import torch
import aiohttp

# Directories
INPUT_DIR = Path(".")
OUTPUT_DIR = Path("./processed")
OUTPUT_DIR.mkdir(exist_ok=True)

# Discord config
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")  # Set this as an env variable
DISCORD_API_BASE = "https://discord.com/api/v10"

# Whisper setup
MODEL_ID = "openai/whisper-large-v3"
device = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.float16 if device == "cuda" else torch.float32

processor = AutoProcessor.from_pretrained(MODEL_ID)
model = AutoModelForSpeechSeq2Seq.from_pretrained(
    MODEL_ID, torch_dtype=dtype, low_cpu_mem_usage=False, use_safetensors=True
).to(device)

forced_decoder_ids = processor.get_decoder_prompt_ids(language="en", task="transcribe")

pipe = pipeline(
    "automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    return_timestamps=False,
    chunk_length_s=10,
    stride_length_s=(1, 1),
    device=0 if device == "cuda" else -1,
    torch_dtype=dtype,
    generate_kwargs={"forced_decoder_ids": forced_decoder_ids}
)

async def post_to_discord(channel_id: str, message: str):
    url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {DISCORD_TOKEN}", "Content-Type": "application/json"}
    json = {"content": message}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=json) as resp:
            if resp.status != 200 and resp.status != 201:
                print(f"Failed to send message: {resp.status} - {await resp.text()}")

async def process_file(wav_path: Path):
    print(f"Transcribing {wav_path.name}...")
    result = pipe(str(wav_path))

    transcript = result["text"].strip() if "text" in result else "(No speech detected.)"

    parts = wav_path.stem.split("__")
    if len(parts) >= 2:
        channel_id = parts[1]
        await post_to_discord(channel_id, f"📜 Transcript for `{wav_path.stem}`:\n{transcript}")
    else:
        print(f"Skipping post — malformed filename: {wav_path.name}")

    print(f"Done: {wav_path.name}")
    wav_path.unlink()  # Delete .wav file after transcription

async def watch_and_process():
    processed = set()
    while True:
        for pcm_file in INPUT_DIR.glob("recording_*.pcm"):
            if pcm_file.name in processed:
                continue

            stem_parts = pcm_file.stem.split("__")
            if len(stem_parts) < 3:
                print(f"Skipping invalid filename: {pcm_file.name}")
                processed.add(pcm_file.name)
                continue

            wav_file = OUTPUT_DIR / pcm_file.with_suffix(".wav").name
            if not wav_file.exists():
                print(f"Converting {pcm_file.name} -> {wav_file.name} (with 1s silence padding)")
                subprocess.run([
                    "ffmpeg", "-y",
                    "-f", "s16le",
                    "-ar", "48000",
                    "-ac", "2",
                    "-i", str(pcm_file),
                    "-af", "apad=pad_dur=1",
                    str(wav_file)
                ])
                pcm_file.unlink()

            await process_file(wav_file)
            processed.add(pcm_file.name)

        await asyncio.sleep(2)  # Check every 2 seconds

if __name__ == "__main__":
    asyncio.run(watch_and_process())
