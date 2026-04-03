# Use a lightweight Python image
FROM python:3.10-slim

# 1. Install FFmpeg and system dependencies
# We combine these to keep the image size small
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Copy only requirements first (to leverage Docker caching)
COPY requirements.txt .

# 4. Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of your application code
COPY . .

# 6. Command to run your bot
# Using -u (unbuffered) ensures logs appear in real-time
CMD ["python", "-u", "bot.py"]
