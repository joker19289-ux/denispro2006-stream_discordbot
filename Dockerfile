FROM python:3.14-bullseye

# Устанавливаем зависимости для аудио
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libopus-dev \
    build-essential

# Копируем проект
WORKDIR /app
COPY . /app

# Устанавливаем зависимости Python
RUN pip install --upgrade pip
RUN pip install discord.py==2.3.1 yt-dlp==2026.3.17.232108.dev0 python-dotenv

# Запуск бота
CMD ["python", "bot.py"]
