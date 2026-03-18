import discord
from discord.ext import commands
import yt_dlp
import subprocess
import asyncio
import os
from dotenv import load_dotenv

# ---------- Загрузка переменных из .env ----------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
YOUTUBE_RTMP = os.getenv("YOUTUBE_RTMP")
COOKIES_FILE = os.getenv("COOKIES_FILE", "cookies.txt")
DOWNLOAD_FOLDER = os.getenv("DOWNLOAD_FOLDER", "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ---------- Инициализация бота ----------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- Глобальные переменные ----------
ffmpeg_process = None
video_queue = asyncio.Queue()
current_video = None
current_file = None

# ---------- Функции ----------

def download_audio_file(url: str):
    """Скачиваем аудио через yt-dlp в файл"""
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(DOWNLOAD_FOLDER, "%(title)s.%(ext)s"),
        "cookiefile": COOKIES_FILE if os.path.exists(COOKIES_FILE) else None,
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)
        return file_path, info.get("title", "audio")

def start_ffmpeg_audio(file_path: str):
    """Запуск ffmpeg для стрима только аудио (-vn)"""
    command = [
        "ffmpeg",
        "-re",
        "-i", file_path,
        "-vn",  # только аудио
        "-c:a", "aac",
        "-b:a", "160k",
        "-ar", "44100",
        "-f", "flv",
        YOUTUBE_RTMP
    ]
    return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

async def monitor_ffmpeg(ctx):
    """Мониторинг ffmpeg и авто-рестарт"""
    global ffmpeg_process, current_video, current_file
    if ffmpeg_process is None:
        return
    await asyncio.sleep(1)
    while ffmpeg_process.poll() is None:
        await asyncio.sleep(5)

    await ctx.send(f"⚠️ Стрим завершён: {current_video}")

    # Удаляем временный файл
    if current_file and os.path.exists(current_file):
        try:
            os.remove(current_file)
        except Exception as e:
            await ctx.send(f"❌ Не удалось удалить файл: {current_file}, {e}")

    ffmpeg_process = None
    current_video = None
    current_file = None

    # Авто-рестарт следующего видео из очереди
    if not video_queue.empty():
        await start_next_stream(ctx)

async def start_next_stream(ctx):
    """Запуск следующего видео из очереди"""
    global ffmpeg_process, current_video, current_file
    if video_queue.empty():
        current_video = None
        await ctx.send("✅ Очередь пуста. Стрим завершён.")
        return

    current_video = await video_queue.get()
    await ctx.send(f"▶️ Подготовка к стриму: {current_video}")

    try:
        file_path, title = download_audio_file(current_video)
        current_file = file_path

        ffmpeg_process = start_ffmpeg_audio(file_path)
        await ctx.send(f"🔊 Стрим начался: {title}")

        bot.loop.create_task(monitor_ffmpeg(ctx))

    except Exception as e:
        await ctx.send(f"❌ Ошибка при стриме: {e}")
        ffmpeg_process = None
        current_video = None
        current_file = None
        await start_next_stream(ctx)

# ---------- Команды ----------

@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user}")

@bot.command()
async def add(ctx, url: str):
    """Добавить видео в очередь"""
    await video_queue.put(url)
    await ctx.send(f"➕ Видео добавлено в очередь: {url}")
    if ffmpeg_process is None:
        await start_next_stream(ctx)

@bot.command()
async def skip(ctx):
    """Пропустить текущее видео"""
    global ffmpeg_process
    if ffmpeg_process:
        ffmpeg_process.terminate()
        await ctx.send("⏭ Пропускаем текущее видео...")
    else:
        await ctx.send("⚠️ Сейчас нет активного стрима.")

@bot.command()
async def stop(ctx):
    """Остановить стрим и очистить очередь"""
    global ffmpeg_process, current_video, current_file
    if ffmpeg_process:
        ffmpeg_process.terminate()
        ffmpeg_process = None
    while not video_queue.empty():
        await video_queue.get()
    if current_file and os.path.exists(current_file):
        try:
            os.remove(current_file)
        except:
            pass
    current_video = None
    current_file = None
    await ctx.send("🛑 Стрим остановлен и очередь очищена.")

@bot.command()
async def status(ctx):
    """Показать статус текущего стрима и очереди"""
    queue_list = list(video_queue._queue)
    await ctx.send(
        f"▶️ Текущее видео: {current_video}\n"
        f"📺 Очередь ({len(queue_list)}):\n" +
        ("\n".join(queue_list) if queue_list else "Очередь пуста")
    )

bot.run(TOKEN)
