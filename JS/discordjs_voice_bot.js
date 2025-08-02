// discordjs_voice_bot.js
// Node.js bot that records 10s audio clips per user, with buffer flush, until stopped

const { Client, GatewayIntentBits } = require('discord.js');
const { joinVoiceChannel, EndBehaviorType, getVoiceConnection } = require('@discordjs/voice');
const fs = require('fs');
const prism = require('prism-media');
const path = require('path');

const TOKEN = 'MTM3MDYwMjk5Mjc3NjI1MzUzMQ.G6W0RR.avQa1j_tnylZfNa6kCcM8R2Q4t0AXau445ribg';
const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildVoiceStates,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent
  ]
});

let connection = null;
let recording = false;
const activeRecordings = new Map(); // Track active recording timers by userId

client.once('ready', () => {
  console.log(`Logged in as ${client.user.tag}`);
});

client.on('messageCreate', async message => {
  if (message.content === '!record') {
    if (recording) return message.reply('Already recording.');
    if (!message.member.voice.channel) return message.reply('You need to be in a voice channel.');

    const channel = message.member.voice.channel;
    connection = joinVoiceChannel({
      channelId: channel.id,
      guildId: message.guild.id,
      adapterCreator: message.guild.voiceAdapterCreator
    });

    const receiver = connection.receiver;
    recording = true;
    message.channel.send('🔴 Recording started. Use `!stop` to end.');

    const startRecordingLoop = (userId, username, channelId) => {
      const safeUsername = username.replace(/[^a-zA-Z0-9-_]/g, '_');

      const loop = () => {
        if (!recording) return;

        const timestamp = Date.now();
        const filename = path.join(__dirname, `recording_${timestamp}__${channelId}__${safeUsername}.pcm`);
        const audioStream = receiver.subscribe(userId, {
          end: {
            behavior: EndBehaviorType.AfterSilence,
            duration: 1000
          }
        });
        const decoder = new prism.opus.Decoder({ channels: 2, rate: 48000, frameSize: 960 });
        const out = fs.createWriteStream(filename);

        console.log(`Recording ${username}`);
        audioStream.pipe(decoder).pipe(out);

        audioStream.on('error', err => console.error(`AudioStream error: ${err.message}`));
        decoder.on('error', err => console.error(`Decoder error: ${err.message}`));
        out.on('error', err => console.error(`WriteStream error: ${err.message}`));

        setTimeout(() => {
          audioStream.destroy();
          setTimeout(() => {
            out.end();
            console.log(`✅ Saved 10s clip: ${filename}`);
            if (recording) loop();
          }, 500); // 0.5s buffer to flush output
        }, 10000);
      };

      loop();
    };

    receiver.speaking.on('start', userId => {
      if (activeRecordings.has(userId)) return;

      const user = message.guild.members.cache.get(userId);
      if (!user) return;

      activeRecordings.set(userId, true);
      startRecordingLoop(userId, user.user.username, message.channel.id);
    });
  }

  if (message.content === '!stop') {
    if (!recording) return message.reply('Not currently recording.');

    const conn = getVoiceConnection(message.guild.id);
    if (conn) conn.destroy();
    connection = null;
    recording = false;
    activeRecordings.clear();

    message.channel.send('🛑 Recording stopped.');
  }
});

client.login(TOKEN);
