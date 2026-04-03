import asyncio
import os

async def encode_m3u8(url, output_path):
    """
    Ultra-fast transcoding optimized for Telegram.
    """
    command = [
        'ffmpeg', '-hide_banner', '-loglevel', 'error',
        '-protocol_whitelist', 'file,http,https,tcp,tls,crypto',
        '-i', url,
        '-c:v', 'libx264',
        '-preset', 'ultrafast',  # Max speed
        '-crf', '26',            # Fast compression
        '-pix_fmt', 'yuv420p',   # Standard TG format
        '-c:a', 'aac',
        '-b:a', '128k',
        '-movflags', '+faststart',
        '-threads', '0',         # Use all CPU cores
        output_path,
        '-y'
    ]
    
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await process.wait()
    return os.path.exists(output_path)
