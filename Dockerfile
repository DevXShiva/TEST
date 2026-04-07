# Base image: Lightweight Python
FROM python:3.10-slim

# System dependencies: FFmpeg is mandatory for m3u8 and splitting
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Work directory setup
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Command to run the bot
CMD ["python", "bot.py"]
