# Используем существующую версию Python
FROM python:3.13-bullseye

# Устанавливаем зависимости для аудио и ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libopus-dev \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта
COPY . /app

# Устанавливаем зависимости Python
RUN pip install --upgrade pip
RUN pip install discord.py==2.3.1 yt-dlp==2026.3.17.232108.dev0 python-dotenv

# Команда запуска бота
CMD ["python", "app/bot.py"]
