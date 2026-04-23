import os
import asyncio
import time
import subprocess
import re
from flask import Flask
from threading import Thread
from pyrogram import Client, filters, enums
from config import API_ID, API_HASH, BOT_TOKEN
from utils.progress import progress_for_pyrogram
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser

# --- FLASK SERVER FOR DEPLOYMENT ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running Live!"

def run_flask():
    # Render automatically sets a PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- BOT INITIALIZATION ---
bot = Client("FastUploader", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- HELPERS FOR METADATA ---
def get_metadata(file_path):
    metadata = extractMetadata(createParser(file_path))
    if not metadata:
        return 0, 0, 0
    duration = metadata.get('duration').seconds if metadata.has('duration') else 0
    width = metadata.get('width') if metadata.has('width') else 0
    height = metadata.get('height') if metadata.has('height') else 0
    return duration, width, height

# --- SPLIT LOGIC ---
async def split_video(file_path, target_size_gb=1.9):
    file_size = os.path.getsize(file_path)
    target_size = target_size_gb * 1024 * 1024 * 1024
    if file_size <= target_size:
        return [file_path]

    parts = []
    duration, _, _ = get_metadata(file_path)
    num_parts = int(file_size // target_size) + 1
    part_duration = duration // num_parts

    base_name, extension = os.path.splitext(file_path)
    
    for i in range(num_parts):
        start_time = i * part_duration
        part_name = f"{base_name}_part{i+1}{extension}"
        cmd = [
            "ffmpeg", "-i", file_path,
            "-ss", str(start_time),
            "-t", str(part_duration),
            "-c", "copy", "-map", "0",
            part_name
        ]
        subprocess.run(cmd, capture_output=True)
        parts.append(part_name)
    
    return parts

# --- CORE DOWNLOAD & UPLOAD ENGINE ---
async def process_m3u8_leech(client, message, url, smsg):
    user_id = message.from_user.id
    timestamp = int(time.time())
    output_name = f"vid_{user_id}_{timestamp}.mp4"

    try:
        await smsg.edit(f"📥 **Downloading Video...**\n🔗 `{url[:50]}...`")
        download_cmd = [
            "yt-dlp", 
            "--concurrent-fragments", "10", 
            "-o", output_name, 
            "--merge-output-format", "mp4", 
            "--no-warnings",
            url
        ]
        process = await asyncio.create_subprocess_exec(*download_cmd)
        await process.wait()

        if not os.path.exists(output_name):
            await smsg.edit(f"❌ **Download Failed for:** `{url}`")
            return

        await smsg.edit("✂️ **Checking file size...**")
        video_files = await split_video(output_name)

        for index, file in enumerate(video_files):
            part_info = f" (Part {index+1})" if len(video_files) > 1 else ""
            await smsg.edit(f"🖼 **Generating Metadata {part_info}...**")
            
            part_thumb = f"thumb_{index}_{timestamp}.jpg"
            subprocess.run(["ffmpeg", "-ss", "00:00:05", "-i", file, "-vframes", "1", part_thumb])
            
            duration, width, height = get_metadata(file)

            await smsg.edit(f"📤 **Uploading {part_info}...**")
            await client.send_video(
                chat_id=message.chat.id,
                video=file,
                caption=f"✅ **Video Uploaded**{part_info}\n🚀 *Fast Engine*",
                thumb=part_thumb if os.path.exists(part_thumb) else None,
                duration=duration,
                width=width,
                height=height,
                supports_streaming=True,
                progress=progress_for_pyrogram,
                progress_args=(f"📤 **Uploading{part_info}...**", smsg, time.time())
            )
            
            if os.path.exists(part_thumb): os.remove(part_thumb)
            if len(video_files) > 1 and os.path.exists(file): os.remove(file)

    except Exception as e:
        await message.reply_text(f"❌ **Error on link:** `{url}`\n`{e}`")
    finally:
        if os.path.exists(output_name): os.remove(output_name)

# --- NEW /M COMMAND FOR MULTIPLE LINKS ---
@bot.on_message(filters.command("m") & filters.private)
async def multi_m3u8_uploader(client, message):
    if len(message.command) < 2:
        return await message.reply_text("❌ **Usage:** Send `/m` followed by links (one per line).")

    links = message.text.split("\n")[0:] 
    if "/m" in links[0]:
        links[0] = links[0].replace("/m", "").strip()
    
    links = [link.strip() for link in links if link.strip()]
    
    if not links:
        return await message.reply_text("❌ **No links found!**")

    smsg = await message.reply_text(f"⏳ **Queue Started:** {len(links)} links found.\nBot will process them one by one.")

    for i, url in enumerate(links):
        await smsg.edit(f"🔄 **Processing Link {i+1} of {len(links)}...**")
        await process_m3u8_leech(client, message, url, smsg)

    await smsg.edit("✅ **All tasks completed in sequence!**")

# Purana automatic detection
@bot.on_message(filters.regex(r'.*?\.m3u8') & filters.private)
async def auto_m3u8_uploader(client, message):
    url = message.text.strip()
    smsg = await message.reply_text("🚀 **Initializing Single Leech...**")
    await process_m3u8_leech(client, message, url, smsg)
    await smsg.delete()

# --- MAIN RUN BLOCK ---
if __name__ == "__main__":
    # Start Flask in a separate thread
    Thread(target=run_flask).start()
    # Run the bot
    bot.run()
