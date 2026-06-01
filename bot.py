import os
import asyncio
import time
import subprocess
import json
import shutil
from flask import Flask
from threading import Thread
from pyrogram import Client, filters
from config import API_ID, API_HASH, BOT_TOKEN
from utils.progress import progress_for_pyrogram

# --- FLASK SERVER FOR DEPLOYMENT ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is Running Live!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- BOT INITIALIZATION ---
bot = Client(
    "FastUploader",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Global Download Queue
download_queue = asyncio.Queue()

# --- HELPERS ---

def get_metadata(file_path):
    """Extracts duration, width, and height using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        
        duration = int(float(data.get("format", {}).get("duration", 0)))
        width, height = 0, 0
        
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                width = stream.get("width", 0)
                height = stream.get("height", 0)
                break
        return duration, width, height
    except Exception as e:
        print(f"Metadata Error: {e}")
        return 0, 0, 0

def parse_name(text):
    """Extracts custom name after -n flag."""
    if "-n" not in text:
        return None
    try:
        return text.split("-n", 1)[1].strip()
    except:
        return None

async def split_video(file_path, target_size_gb=1.9):
    """Splits video into parts if it exceeds the target size."""
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
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", file_path,
            "-ss", str(start_time),
            "-t", str(part_duration),
            "-c", "copy", "-map", "0",
            "-avoid_negative_ts", "make_zero",
            part_name
        ]
        subprocess.run(cmd)
        parts.append(part_name)
    return parts

# --- CORE ENGINE ---

async def process_m3u8_leech(client, message, url, smsg, custom_title=None):
    user_id = message.from_user.id
    timestamp = int(time.time())
    output_name = f"vid_{user_id}_{timestamp}.mp4"
    encoded_file = f"enc_{user_id}_{timestamp}.mp4"

    try:
        # 1. DOWNLOAD
        await smsg.edit(f"📥 **Downloading Highest Quality...**\n`{url[:50]}...`")
        download_cmd = [
            "yt-dlp", "-f", "bv*+ba/b",
            "--concurrent-fragments", "10",
            "--merge-output-format", "mp4",
            "--no-warnings", "-o", output_name, url
        ]
        process = await asyncio.create_subprocess_exec(*download_cmd)
        await process.wait()

        if not os.path.exists(output_name):
            await smsg.edit("❌ **Download Failed.**")
            return

        # 2. ENCODE TO X265
        await smsg.edit("🎞 **Encoding to H.265 (x265)...**\n*This may take time.*")
        encode_cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", output_name,
            "-c:v", "libx265", "-preset", "slow", "-crf", "18",
            "-tag:v", "hvc1", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart"
        ]
        if custom_title:
            encode_cmd.extend(["-metadata", f"title={custom_title}"])
        
        encode_cmd.append(encoded_file)
        
        process = await asyncio.create_subprocess_exec(*encode_cmd)
        await process.wait()

        # 3. SPLIT (If needed)
        await smsg.edit("✂️ **Checking file size & splitting...**")
        video_files = await split_video(encoded_file)

        # 4. UPLOAD PARTS
        for index, file in enumerate(video_files):
            part_info = f" (Part {index+1})" if len(video_files) > 1 else ""
            
            # Use custom title for file display name if provided
            upload_display_name = f"{custom_title}{part_info}.mp4" if custom_title else os.path.basename(file)
            temp_upload_file = os.path.join(os.path.dirname(file), upload_display_name)
            shutil.copy(file, temp_upload_file)

            # Thumbnail
            part_thumb = f"thumb_{index}_{timestamp}.jpg"
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error", "-ss", "00:00:15",
                "-i", temp_upload_file, "-frames:v", "1", "-q:v", "2", part_thumb
            ])

            duration, width, height = get_metadata(temp_upload_file)

            await client.send_video(
                chat_id=message.chat.id,
                video=temp_upload_file,
                caption=f"🎬 **{custom_title or 'Video'}**{part_info}\n\n✅ Uploaded Successfully",
                thumb=part_thumb if os.path.exists(part_thumb) else None,
                duration=duration, width=width, height=height,
                supports_streaming=True,
                progress=progress_for_pyrogram,
                progress_args=(f"📤 **Uploading{part_info}...**", smsg, time.time())
            )

            # Cleanup loop files
            for f in [part_thumb, temp_upload_file]:
                if os.path.exists(f): os.remove(f)
            if len(video_files) > 1 and os.path.exists(file): os.remove(file)

    except Exception as e:
        await message.reply_text(f"❌ **Error:**\n`{e}`")
    finally:
        for f in [output_name, encoded_file]:
            if os.path.exists(f): os.remove(f)

# --- QUEUE WORKER ---

async def queue_worker():
    while True:
        client, message, url, smsg, custom_title = await download_queue.get()
        try:
            await process_m3u8_leech(client, message, url, smsg, custom_title)
        except Exception as e:
            print(f"Queue Error: {e}")
        finally:
            await smsg.delete()
            download_queue.task_done()

# --- COMMAND HANDLERS ---

@bot.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    await message.reply_text(
        "🚀 **FastUploader H.265 Bot**\n\n"
        "**Usage:**\n"
        "1. Send an M3U8 link directly.\n"
        "2. `/l -n Title <link>` or reply to a link with `/l -n Title`.\n"
        "3. `/m <links>` for batch processing.\n\n"
        "All videos encoded to **x265 HEVC**."
    )

@bot.on_message(filters.command("l") & filters.private)
async def leech_command(client, message):
    custom_title = parse_name(message.text)
    url = None
    
    if message.reply_to_message:
        url = message.reply_to_message.text.strip()
    else:
        parts = message.text.split()
        for item in parts:
            if item.startswith("http"):
                url = item
                break

    if not url:
        return await message.reply_text("❌ Reply to a link or include one in the command.")

    smsg = await message.reply_text(f"⏳ Added to Queue. Position: {download_queue.qsize() + 1}")
    await download_queue.put((client, message, url, smsg, custom_title))

@bot.on_message(filters.command("m") & filters.private)
async def multi_m3u8_uploader(client, message):
    lines = message.text.split("\n")
    links = [l.strip() for l in lines if "http" in l]
    
    if not links:
        return await message.reply_text("❌ No links found.")

    for url in links:
        smsg = await message.reply_text(f"⏳ Added to Queue. Position: {download_queue.qsize() + 1}")
        await download_queue.put((client, message, url, smsg, None))

@bot.on_message(filters.private & filters.text & ~filters.command(["start", "m", "l"]))
async def auto_link_handler(client, message):
    if "m3u8" not in message.text.lower() and "http" not in message.text.lower():
        return
    
    url = message.text.strip()
    smsg = await message.reply_text(f"⏳ Added to Queue. Position: {download_queue.qsize() + 1}")
    await download_queue.put((client, message, url, smsg, None))

# --- MAIN START ---

if __name__ == "__main__":
    Thread(target=run_flask).start()
    bot.loop.create_task(queue_worker())
    print("🚀 Bot and Queue Worker Started!")
    bot.run()
