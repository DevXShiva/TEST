import asyncio
import os
import time
import yt_dlp
import subprocess

async def split_video(file_path, max_size_mb=1900):
    """
    Video ko parts mein split karta hai bina quality loss ke (Stream Copying).
    """
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    
    # Agar size limit se chota hai, toh wahi file list mein bhej do
    if file_size_mb <= max_size_mb:
        return [file_path]

    print(f"Large file detected ({file_size_mb:.2f} MB). Splitting into parts...")
    
    # Video ki duration nikalne ke liye ffprobe ka use
    duration_cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', file_path
    ]
    duration = float(subprocess.check_output(duration_cmd).decode().strip())
    
    # Calculate number of parts
    num_parts = int(file_size_mb // max_size_mb) + 1
    part_duration = duration / num_parts
    
    parts = []
    base_name, extension = os.path.splitext(file_path)

    for i in range(num_parts):
        part_output = f"{base_name}_part{i+1}{extension}"
        start_time = i * part_duration
        
        # FFmpeg command for fast splitting (using copy codec)
        split_cmd = [
            'ffmpeg', '-hide_banner', '-loglevel', 'error',
            '-ss', str(start_time),
            '-t', str(part_duration),
            '-i', file_path,
            '-c', 'copy', '-map', '0', # Stream copy (very fast)
            '-movflags', '+faststart',
            part_output, '-y'
        ]
        
        process = await asyncio.create_subprocess_exec(*split_cmd)
        await process.wait()
        
        if os.path.exists(part_output):
            parts.append(part_output)
    
    return parts

async def encode_m3u8(url, output_path, status_message):
    """
    yt-dlp library with live progress and automatic 2GB splitting.
    """
    last_update_time = 0

    def progress_hook(d):
        nonlocal last_update_time
        if d['status'] == 'downloading':
            current_time = time.time()
            # Telegram Flood Wait se bachne ke liye 4 sec delay
            if current_time - last_update_time < 4:
                return

            downloaded = d.get('_downloaded_bytes_str', 'N/A')
            speed = d.get('_speed_str', 'N/A')
            
            try:
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
            except:
                pass

    ydl_opts = {
        'format': 'best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [progress_hook],
        'postprocessor_args': [
            '-c:v', 'libx264', '-preset', 'ultrafast', 
            '-crf', '26', '-pix_fmt', 'yuv420p', 
            '-c:a', 'aac', '-movflags', '+faststart'
        ],
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
    }

    try:
        loop = asyncio.get_event_loop()
        # Download video
        await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([url]))
        
        if os.path.exists(output_path):
            # Download ke baad check karo split ki zaroorat hai ya nahi
            video_list = await split_video(output_path)
            return video_list # List of file paths return karega
        
        return []
    except Exception as e:
        print(f"YT-DLP/Split Error: {e}")
        return []
