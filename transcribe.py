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

async def stt(filename):
    pass