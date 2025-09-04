import os
import re
import asyncio
import aiohttp
import requests
from flask import Flask, request
from telebot.async_telebot import AsyncTeleBot
import telebot.types

# ---------------- Config ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
TEMP_DIR = "downloads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

bot = AsyncTeleBot(BOT_TOKEN)
app = Flask(__name__)

os.makedirs(TEMP_DIR, exist_ok=True)

# ---------------- Helper Functions ----------------

def extract_terabox_links(text: str):
    """Find Terabox/1024Terabox links in text"""
    pattern = r"(https?://(?:www\.)?(?:terabox\.com|teraboxapp\.com|d\.terabox\.com|1024tera(?:box)?\.com)[^\s]*)"
    return re.findall(pattern, text)

def resolve_terabox_link(url: str):
    """
    Use unofficial Terabox resolver API to get direct video link
    (Free public API: https://teraboxapi.com/)
    """
    try:
        api = "https://teraboxapi.com/api/v1/get"
        r = requests.get(api, params={"url": url}, timeout=15)
        data = r.json()
        if data.get("status") == "success":
            video_url = data["data"]["download_link"]
            filename = data["data"].get("name", "video.mp4")
            size = int(data["data"].get("size", 0))
            return {"url": video_url, "name": filename, "size": size}
    except Exception as e:
        print("Resolver error:", e)
    return None

async def download_file(session, url, filename):
    """Download video to TEMP_DIR"""
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                path = os.path.join(TEMP_DIR, filename)
                with open(path, "wb") as f:
                    while True:
                        chunk = await resp.content.read(1024*1024)
                        if not chunk:
                            break
                        f.write(chunk)
                return path
    except Exception as e:
        print("Download error:", e)
    return None

async def send_video_with_cleanup(chat_id, video):
    async with aiohttp.ClientSession() as session:
        file_path = await download_file(session, video["url"], video["name"])
        if file_path:
            try:
                await bot.send_chat_action(chat_id, "upload_video")
                with open(file_path, "rb") as f:
                    await bot.send_video(chat_id, f, caption=video["name"])
            except Exception as e:
                await bot.send_message(chat_id, f"❌ Error sending video: {e}")
            finally:
                os.remove(file_path)
        else:
            await bot.send_message(chat_id, "⚠️ Failed to download video.")

# ---------------- Bot Handlers ----------------

@bot.message_handler(commands=["start"])
async def start_handler(message):
    await bot.send_message(
        message.chat.id,
        "👋 Welcome! Send me a Terabox / 1024Terabox link and I’ll fetch the video (≤50MB)."
    )

@bot.message_handler(func=lambda m: True)
async def handle_message(message):
    links = extract_terabox_links(message.text)
    if not links:
        return
    chat_id = message.chat.id
    await bot.send_message(chat_id, f"🔎 Processing {len(links)} link(s)...")
    for link in links:
        video = resolve_terabox_link(link)
        if video and video["size"] <= MAX_FILE_SIZE:
            await send_video_with_cleanup(chat_id, video)
        elif video:
            await bot.send_message(chat_id, f"⚠️ {video['name']} is too large (>50MB).")
        else:
            await bot.send_message(chat_id, "❌ Could not fetch video link.")

# ---------------- Flask Webhook ----------------

@app.route("/", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    print("📩 Incoming update:", json_str)  # Debug logs
    update = telebot.types.Update.de_json(json_str)
    asyncio.run(bot.process_new_updates([update]))
    return "!", 200

def set_webhook():
    asyncio.run(bot.remove_webhook())
    asyncio.run(bot.set_webhook(url=WEBHOOK_URL))

# ---------------- Run App ----------------

if __name__ == "__main__":
    set_webhook()
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Bot is running on port {port}, webhook set to {WEBHOOK_URL}")
    app.run(host="0.0.0.0", port=port)
