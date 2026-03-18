import discord
from discord.ext import commands
import yt_dlp
import subprocess
import os
import asyncio
import signal

# ---------------- CONFIG ----------------
TOKEN = "MTQ4MzQwMTkzMTc4NjU1NTQzNQ.Gb5o2r.KEhF_bwCDCrgoudZ1_Ac6xi9LKf20SDVbDzckQ"
RTMP_URL = "rtmp://your.rtmp.server/live/tjp4-hbx3-uawe-dgqe-64dp"
DOWNLOAD_DIR = "./downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ---------------- BOT SETUP ----------------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

current_process = None
current_file = None

# ---------------- HELPERS ----------------
def download_video(url):
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'quiet': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

        # если расширение не mp4 — заменим
        if not filename.endswith(".mp4"):
            filename = os.path.splitext(filename)[0] + ".mp4"

    return filename


def start_stream(filename):
    global current_process

    ffmpeg_cmd = [
        'ffmpeg',
        '-re',
        '-i', filename,
        '-c:v', 'libx264',
        '-preset', 'veryfast',
        '-maxrate', '3000k',
        '-bufsize', '6000k',
        '-pix_fmt', 'yuv420p',
        '-g', '50',
        '-c:a', 'aac',
        '-b:a', '160k',
        '-ar', '44100',
        '-f', 'flv',
        RTMP_URL
    ]

    current_process = subprocess.Popen(
        ffmpeg_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT
    )


def stop_stream():
    global current_process
    if current_process:
        current_process.send_signal(signal.SIGTERM)
        current_process.wait()
        current_process = None


def cleanup_file(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass


# ---------------- COMMANDS ----------------
@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user}")


@bot.command()
async def start(ctx, url: str):
    """Скачать видео и начать стрим"""
    global current_file

    if current_process:
        await ctx.send("⚠️ Стрим уже запущен!")
        return

    msg = await ctx.send("⬇️ Скачиваю видео...")

    try:
        loop = asyncio.get_event_loop()
        filename = await loop.run_in_executor(None, download_video, url)
        current_file = filename

        await msg.edit(content=f"✅ Скачано:\n`{filename}`")

        await ctx.send("📡 Запускаю стрим...")

        start_stream(filename)

        await ctx.send("🟢 Стрим запущен!")

    except Exception as e:
        await ctx.send(f"❌ Ошибка: {e}")


@bot.command()
async def stop(ctx):
    """Остановить стрим"""
    global current_file

    if not current_process:
        await ctx.send("⚠️ Нет активного стрима.")
        return

    stop_stream()
    cleanup_file(current_file)

    current_file = None

    await ctx.send("🔴 Стрим остановлен и файл удалён.")


@bot.command()
async def status(ctx):
    """Статус стрима"""
    if current_process:
        await ctx.send("🟢 Стрим активен.")
    else:
        await ctx.send("🔴 Стрим остановлен.")


# ---------------- RUN ----------------
bot.run(TOKEN)
