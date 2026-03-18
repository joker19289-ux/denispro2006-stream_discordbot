import discord
from discord.ext import commands, tasks
import yt_dlp
import subprocess
import asyncio
import shlex
import signal

# ---------------- CONFIG ----------------
TOKEN = "MTQ4MzQwMTkzMTc4NjU1NTQzNQ.Gb5o2r.KEhF_bwCDCrgoudZ1_Ac6xi9LKf20SDVbDzckQ"
RTMP_URL = "rtmp://your.rtmp.server/live/tjp4-hbx3-uawe-dgqe-64dp"

# Настройки ffmpeg по умолчанию
DEFAULT_VIDEO_CODEC = "libx264"
DEFAULT_PRESET = "veryfast"
DEFAULT_MAXRATE = "3000k"
DEFAULT_BUFSIZE = "6000k"
DEFAULT_AUDIO_CODEC = "aac"
DEFAULT_AUDIO_BITRATE = "160k"
DEFAULT_AUDIO_RATE = "44100"

# ---------------- BOT SETUP ----------------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- STREAM STATE ----------------
playlist = []
current_process = None
current_video = None
streaming = False

# ---------------- HELPERS ----------------
def create_ffmpeg_cmd(pipe_url, quality=None):
    """Создаём команду ffmpeg для стрима через stdin"""
    video_codec = quality.get("vcodec", DEFAULT_VIDEO_CODEC) if quality else DEFAULT_VIDEO_CODEC
    preset = quality.get("preset", DEFAULT_PRESET) if quality else DEFAULT_PRESET
    maxrate = quality.get("maxrate", DEFAULT_MAXRATE) if quality else DEFAULT_MAXRATE
    bufsize = quality.get("bufsize", DEFAULT_BUFSIZE) if quality else DEFAULT_BUFSIZE
    audio_codec = quality.get("acodec", DEFAULT_AUDIO_CODEC) if quality else DEFAULT_AUDIO_CODEC
    audio_bitrate = quality.get("abitrate", DEFAULT_AUDIO_BITRATE) if quality else DEFAULT_AUDIO_BITRATE
    audio_rate = quality.get("arate", DEFAULT_AUDIO_RATE) if quality else DEFAULT_AUDIO_RATE

    cmd = [
        "ffmpeg",
        "-re",
        "-i", "pipe:0",          # input from stdin
        "-c:v", video_codec,
        "-preset", preset,
        "-maxrate", maxrate,
        "-bufsize", bufsize,
        "-pix_fmt", "yuv420p",
        "-g", "50",
        "-c:a", audio_codec,
        "-b:a", audio_bitrate,
        "-ar", str(audio_rate),
        "-f", "flv",
        pipe_url
    ]
    return cmd

async def stream_video(url, quality=None):
    """Стримим видео напрямую через yt-dlp + ffmpeg pipe"""
    global current_process, current_video, streaming

    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "outtmpl": "-",
        "noplaylist": True,
        "prefer_ffmpeg": True,
    }

    streaming = True
    current_video = url

    process = subprocess.Popen(create_ffmpeg_cmd(RTMP_URL, quality),
                               stdin=subprocess.PIPE,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.STDOUT)
    current_process = process

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])  # yt-dlp выводит данные в stdout → ffmpeg stdin
    except Exception as e:
        print(f"Ошибка yt-dlp: {e}")
    finally:
        if process:
            process.send_signal(signal.SIGTERM)
            process.wait()
        streaming = False
        current_process = None
        current_video = None

async def play_next(ctx):
    """Автоматическое проигрывание следующего видео из очереди"""
    global playlist
    while playlist:
        next_url = playlist.pop(0)
        await ctx.send(f"▶️ Начинаю стрим: {next_url}")
        await stream_video(next_url)
    await ctx.send("✅ Очередь завершена.")

# ---------------- COMMANDS ----------------
@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user}")

@bot.command()
async def add(ctx, url: str):
    """Добавить видео в очередь"""
    playlist.append(url)
    await ctx.send(f"➕ Видео добавлено в очередь ({len(playlist)} в очереди)")

@bot.command()
async def queue(ctx):
    """Показать очередь"""
    if not playlist:
        await ctx.send("🛑 Очередь пустая")
    else:
        msg = "\n".join([f"{i+1}. {url}" for i, url in enumerate(playlist)])
        await ctx.send(f"🎵 Очередь видео:\n{msg}")

@bot.command()
async def start(ctx, quality: str = None):
    """Начать стриминг очереди"""
    if streaming:
        await ctx.send("⚠️ Стрим уже идет")
        return
    if not playlist:
        await ctx.send("🛑 Очередь пустая, добавьте видео через !add")
        return

    # парсим качество/битрейт
    quality_opts = None
    if quality:
        # формат: vcodec=libx264,maxrate=3000k,bufsize=6000k,acodec=aac,abitrate=160k,arate=44100
        quality_opts = {}
        for kv in quality.split(","):
            k, v = kv.split("=")
            quality_opts[k.strip()] = v.strip()

    await ctx.send("📡 Запускаю очередь...")
    await play_next(ctx)

@bot.command()
async def skip(ctx):
    """Пропустить текущее видео"""
    global current_process
    if not streaming or not current_process:
        await ctx.send("⚠️ Нечего пропускать")
        return
    current_process.send_signal(signal.SIGTERM)
    await ctx.send("⏭ Пропущено текущее видео")

@bot.command()
async def stop(ctx):
    """Остановить стрим"""
    global playlist, current_process, streaming
    playlist.clear()
    if current_process:
        current_process.send_signal(signal.SIGTERM)
        current_process.wait()
    streaming = False
    current_process = None
    await ctx.send("🔴 Стрим остановлен и очередь очищена")

@bot.command()
async def status(ctx):
    """Показать статус"""
    if streaming and current_video:
        await ctx.send(f"🟢 Сейчас стримим: {current_video}\nОсталось в очереди: {len(playlist)}")
    else:
        await ctx.send("🔴 Стрим остановлен")
