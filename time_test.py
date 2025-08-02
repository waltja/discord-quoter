import time
import torch
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq, pipeline

# Load model and processor
device = "cuda" if torch.cuda.is_available() else "cpu"
model_id = "openai/whisper-large-v3"
torch_dtype = torch.float16 if device == "cuda" else torch.float32

print(f"Using device: {device}, dtype: {torch_dtype}")

processor = AutoProcessor.from_pretrained(model_id)
model = AutoModelForSpeechSeq2Seq.from_pretrained(
    model_id,
    torch_dtype=torch_dtype,
    low_cpu_mem_usage=False,
    use_safetensors=True
).to(device)

# Use forced decoder IDs to enforce English transcription
forced_decoder_ids = processor.get_decoder_prompt_ids(
    language="en",
    task="transcribe"
)

pipe = pipeline(
    "automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    return_timestamps=False,  # no timestamp = faster
    device=0,
    torch_dtype=torch_dtype,
    generate_kwargs={"forced_decoder_ids": forced_decoder_ids}
)


# Convert to "sample.wav"
from pydub import AudioSegment
def mp3_to_sample_wav(mp3_path, wav_path="sample.wav"):
    audio = AudioSegment.from_file(mp3_path, format="mp3")

    # Convert to mono 16 kHz 16‑bit
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)

    audio.export(wav_path, format="wav")
mp3_to_sample_wav("sample-0.mp3")


# Transcribe with timing
start = time.perf_counter()
result = pipe("sample.wav")
end = time.perf_counter()

print("\nTranscript:")
print(result["text"].strip())
print(f"\nTime taken: {end - start:.2f} seconds")
