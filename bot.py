import os
import asyncio
import time
import subprocess
from pyrogram import Client, filters, enums
from config import API_ID, API_HASH, BOT_TOKEN
from utils.progress import progress_for_pyrogram
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser

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
        # FFmpeg split command (Fast -c copy)
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

@bot.on_message(filters.regex(r'.*?\.m3u8') & filters.private)
async def fast_m3u8_uploader(client, message):
    user_id = message.from_user.id
    url = message.text.strip()
    smsg = await message.reply_text("🚀 **Initializing High-Speed Engine...**")
    
    timestamp = int(time.time())
    output_name = f"vid_{user_id}_{timestamp}.mp4"
    thumb_name = f"th_{user_id}_{timestamp}.jpg"

    try:
        # STEP 1: DOWNLOAD
        await smsg.edit("📥 **Downloading (Parallel Mode)...**")
        download_cmd = ["yt-dlp", "--hls-prefer-native", "--concurrent-fragments", "10", "-o", output_name, "--merge-output-format", "mp4", url]
        process = await asyncio.create_subprocess_exec(*download_cmd)
        await process.wait()

        if not os.path.exists(output_name):
            return await smsg.edit("❌ **Download Failed!**")

        # STEP 2: SPLIT CHECK
        await smsg.edit("✂️ **Checking file size & Splitting if needed...**")
        video_files = await split_video(output_name)

        # STEP 3: PROCESS EACH PART
        for index, file in enumerate(video_files):
            part_info = f" (Part {index+1})" if len(video_files) > 1 else ""
            await smsg.edit(f"🖼 **Generating Metadata {part_info}...**")
            
            # Auto Thumb from each part
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
            
            # Part cleanup
            if os.path.exists(part_thumb): os.remove(part_thumb)
            if len(video_files) > 1 and os.path.exists(file): os.remove(file)

    except Exception as e:
        await smsg.edit(f"❌ **Error:** `{e}`")

    finally:
        # FINAL CLEANUP
        if os.path.exists(output_name): os.remove(output_name)
        await smsg.delete()

bot.run()
