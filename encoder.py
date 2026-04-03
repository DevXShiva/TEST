import asyncio
import os
import time
import yt_dlp

async def encode_m3u8(url, output_path, status_message):
    """
    yt-dlp library ka use karke download aur live progress update.
    """
    last_update_time = 0

    def progress_hook(d):
        nonlocal last_update_time
        if d['status'] == 'downloading':
            current_time = time.time()
            # Telegram Flood Wait se bachne ke liye har 4 second mein 1 update
            if current_time - last_update_time < 4:
                return

            # Data nikalna
            downloaded = d.get('_downloaded_bytes_str', 'N/A')
            speed = d.get('_speed_str', 'N/A')
            
            # Message ko edit karne ke liye task create karna
            try:
                # Pyrogram/Telethon ke message.edit ko async call dena
                asyncio.run_coroutine_threadsafe(
                    status_message.edit(
                        f"⚡ **Downloading Started...**\n\n"
                        f"📥 **Downloaded:** `{downloaded}`\n"
                        f"🚀 **Speed:** `{speed}`\n\n"
                        f"🛠️ *Status: Processing Chunks...*"
                    ),
                    asyncio.get_event_loop()
                )
                last_update_time = current_time
            except Exception as e:
                print(f"Update Error: {e}")

    # yt-dlp Options (Same settings for no corruption)
    ydl_opts = {
        'format': 'best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [progress_hook],
        'postprocessor_args': [
            '-c:v', 'libx264', 
            '-preset', 'ultrafast', 
            '-crf', '26', 
            '-pix_fmt', 'yuv420p', 
            '-c:a', 'aac', 
            '-movflags', '+faststart'
        ],
        # Force rewrite to mp4 after download
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
    }

    try:
        # Loop ke executor mein run karna taaki bot freeze na ho
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))
        
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        print(f"YT-DLP Library Error: {e}")
        return False
