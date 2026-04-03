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
    await db.add_user(message.from_user.id, message.from_user.username)
    await message.reply("🚀 **Ultra-Fast M3U8 to MP4 Bot**\nSend me a link to start.")

@app.on_message(filters.text & filters.private)
async def handle_link(client, message):
    url = message.text.strip()
    if "m3u8" not in url:
        return

    async with semaphore:
        status = await message.reply("⚡ **Processing...** Please wait.")
        file_path = f"video_{message.from_user.id}_{message.id}.mp4"

        try:
            success = await encode_m3u8(url, file_path)
            
            if success:
                await status.edit("🚀 **Uploading...**")
                await message.reply_video(
                    video=file_path,
                    caption="✅ Done!",
                    supports_streaming=True
                )
                await status.delete()
            else:
                await status.edit("❌ Failed to process. Link might be expired.")

        except Exception as e:
            await status.edit(f"❌ Error: {str(e)}")
        
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

if __name__ == "__main__":
    print("Bot is live!")
    app.run()
