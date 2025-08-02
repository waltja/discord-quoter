# Create Bot
import discord
from discord.ext import commands
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.reactions = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Create Transcription Model
from faster_whisper import WhisperModel
model = WhisperModel("tiny.en", compute_type="int8")  # or "cpu" if int8 doesn't work

# Create Listening Sink
import discord
from collections import defaultdict

class PCMRecorder(discord.AudioSink):
    def __init__(self):
        self.buffers = defaultdict(bytearray)

    def write(self, data: discord.AudioData):
        self.buffers[data.user.id].extend(data.pcm)

    def get_user_audio(self, user_id):
        return bytes(self.buffers[user_id])
recorder = PCMRecorder()

# Create transcription object
import asyncio
import wave
async def transcription_loop(ctx, sink, interval=15):
    while True:
        await asyncio.sleep(interval)

        for uid, buffer in sink.buffers.items():
            pcm = bytes(buffer)
            if len(pcm) < 48000 * 2 * 3:  # skip if < 3 sec
                continue

            # Save PCM to .wav
            filename = f"{uid}_temp.wav"
            with wave.open(filename, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(48000)
                wf.writeframes(pcm)

            # Transcribe
            segments, _ = model.transcribe(filename)
            text = " ".join(seg.text for seg in segments).strip()

            if text:
                await ctx.send(f"<@{uid}> said:\n> {text}")


# Commands/Events
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send("Sorry, you don't have the required role.")

@bot.command()
@commands.has_role("jahames")
async def test(ctx):
    await ctx.send('testing')

@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send("Joined voice channel")
    else:
        await ctx.send("You're not in a voice channel")

@bot.command()
async def start_recording(ctx):
    vc = ctx.voice_client
    if not vc:
        await ctx.send("Bot must be in a voice channel first.")
        return

    global recorder
    recorder = PCMRecorder()
    vc.listen(recorder)
    await ctx.send("Recording started.")

@bot.command()
async def stop_recording(ctx):
    vc = ctx.voice_client
    if vc:
        vc.stop_listening()

    for uid, pcm in recorder.buffers.items():
        filename = f"{uid}.wav"
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(pcm)
        await ctx.send(f"Saved audio for <@{uid}> as {filename}")


@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Left voice channel")




#TODO make helper def
# @bot.event
# async def on_reaction_add(reaction, user):
#     if user_has_role(user, "QuoteMaster") and reaction.emoji == "📌":
#         message = reaction.message
#         quote = lookup_quote_by_msg_id(message.id)
#         await quotes_channel.send(f"🗨️ <@{quote.user_id}> said at {quote.timestamp}:\n> {quote.text}")


if __name__ == '__main__':
    bot.run("MTM3MDYwMjk5Mjc3NjI1MzUzMQ.G6W0RR.avQa1j_tnylZfNa6kCcM8R2Q4t0AXau445ribg")