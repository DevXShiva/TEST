import asyncio
import os

async def encode_m3u8(url, output_path):
    # YT-DLP Command with Internal FFmpeg Fixes
    # --downloader aria2c (agar server pe aria2 hai toh aur fast hoga, nahi toh default bhi chalega)
    command = [
        'yt-dlp',
        '--quiet', '--no-warnings',
        '-i', url,
        '-o', output_path,
        # Ye part video corruption fix karega:
        '--recode-video', 'mp4',
        '--postprocessor-args', 
        'ffmpeg:-c:v libx264 -preset ultrafast -crf 26 -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart'
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # 15 minutes timeout
        await asyncio.wait_for(process.wait(), timeout=900)
        
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        print(f"YT-DLP Error: {e}")
        return False
