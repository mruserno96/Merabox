import os
import re
import time
import asyncio
import requests
import aiohttp
from flask import Flask, request
import telebot

# ---------------- Config ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
TEMP_DIR = "downloads"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

os.makedirs(TEMP_DIR, exist_ok=True)

# ---------------- Helper Functions ----------------

def extract_terabox_links(text):
    pattern = r"(https?://(?:www\.)?(?:terabox\.com|teraboxapp\.com|d\.terabox\.com|1024tera\.com)[^\s]*)"
    return re.findall(pattern, text)

def get_file_list_1024tera(url):
    """Parse 1024Tera folder link and get video URLs"""
    headers = {"User-Agent": "Mozilla/5.0"}
    if "/sharing/" in url:
        url = url.replace("/sharing/link?", "/wap/share/filelist?")
    try:
        r = requests.get(url, headers=headers).json()
        files = []
        for item in r.get("file_list", []):
            if item["file_type"].startswith("video") and item["file_size"] <= MAX_FILE_SIZE:
                files.append({
                    "name": item["file_name"],
                    "size": item["file_size"],
                    "download_url": item.get("download_url")  # placeholder
                })
        return files
    except Exception as e:
        print("Error fetching folder:", e)
        return []

async def download_file(session, url, filename):
    """Async download file"""
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

async def send_video_with_cleanup(chat_id, url, filename):
    async with aiohttp.ClientSession() as session:
        file_path = await download_file(session, url, filename)
        if file_path:
            try:
                bot.send_chat_action(chat_id, "upload_video")
                bot.send_video(chat_id, open(file_path, "rb"))
            except Exception as e:
                bot.send_message(chat_id, f"Error sending video: {e}")
            await asyncio.sleep(600)  # 10 minutes
            os.remove(file_path)

async def send_folder_files(chat_id, files):
    total = len(files)
    for idx, f in enumerate(files, 1):
        await send_video_with_cleanup(chat_id, f["download_url"], f["name"])
        bot.send_message(chat_id, f"{idx}/{total} videos sent. Remaining: {total-idx}")

# ---------------- Bot Handlers ----------------

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    links = extract_terabox_links(message.text)
    if not links:
        return
    chat_id = message.chat.id
    bot.send_message(chat_id, f"Processing {len(links)} link(s)...")
    for link in links:
        if "1024tera.com" in link:
            files = get_file_list_1024tera(link)
            if files:
                asyncio.run(send_folder_files(chat_id, files))
            else:
                bot.send_message(chat_id, "No video found under 50 MB.")
        else:
            bot.send_message(chat_id, "Direct Terabox link handling coming soon.")

# ---------------- Flask Webhook ----------------

@app.route("/", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

def set_webhook():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)

# ---------------- Run App ----------------

if __name__ == "__main__":
    set_webhook()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
