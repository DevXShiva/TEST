import os
import asyncio
from pyrogram import Client, filters
from dotenv import load_dotenv
from database import db
from encoder import encode_m3u8

load_dotenv()

# Limit concurrent processing to prevent CPU overload
semaphore = asyncio.Semaphore(int(os.getenv("MAX_CONCURRENT_TASKS", 3)))

app = Client(
    "m3u8_bot",
    api_id=int(os.getenv("API_ID")),
    api_hash=os.getenv("API_HASH"),
    bot_token=os.getenv("BOT_TOKEN")
)

@app.on_message(filters.command("start") & filters.private)
async def start(client, message):
    await db.add_user(message.from_user.id, message.from_user.username or "User")
    await message.reply("🚀 **Ultra-Fast M3U8 to MP4 Bot**\n\nSend me any .m3u8 link. I will handle large files by splitting them if they exceed 2GB!")

@app.on_message(filters.text & filters.private)
async def handle_link(client, message):
    url = message.text.strip()
    
    # Check if link is valid
    if "m3u8" not in url and not url.startswith("http"):
        return

    async with semaphore:
        status = await message.reply("⚡ **Initializing...** Connecting to server.")
        file_path = f"video_{message.from_user.id}_{message.id}.mp4"

        try:
            # Ab encoder.py se hume list of parts milegi
            video_parts = await encode_m3u8(url, file_path, status)
            
            if video_parts and isinstance(video_parts, list):
                total_parts = len(video_parts)
                await status.edit(f"🚀 **Download Complete!** Found {total_parts} part(s).\nUploading to Telegram...")
                
                for index, part in enumerate(video_parts):
                    if total_parts > 1:
                        caption = f"📦 **Part {index + 1} of {total_parts}**\n\n🎬 `{os.path.basename(part)}`"
                    else:
                        caption = f"✅ **Downloaded Successfully!**\n\n🎬 `{os.path.basename(part)}`"

                    # Uploading part
                    await message.reply_video(
                        video=part,
                        caption=caption,
                        supports_streaming=True
                    )
                    
                    # Upload ke baad part file delete karein (agar wo split part hai)
                    if part != file_path and os.path.exists(part):
                        os.remove(part)
                
                await status.delete()
            else:
                await status.edit("❌ **Processing Failed!**\n\nReason: Possible expired link or server issue.")

        except Exception as e:
            if status:
                await status.edit(f"❌ **Error:** `{str(e)}`")
        
        finally:
            # Original file aur bache hue parts delete karna
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            # Extra safety: Clean up any remaining parts in the directory if needed

if __name__ == "__main__":
    print("🚀 Bot is starting...")
    app.run()
