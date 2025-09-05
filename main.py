from flask import Flask, request
import os, threading, tempfile, asyncio
from playwright.async_api import async_playwright
import requests, json, re, sys

sys.stdout.reconfigure(line_buffering=True)

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

VALID_DOMAINS = [
    "1024tera.com",
    "terabox.fun",
    "terabox.app",
    "teraboxapp.com",
    "1024terabox.com",
]

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "✅ Terabox Downloader Bot Running"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    print("📩 Incoming update:", data, flush=True)

    if "message" not in data:
        return {"ok": True}

    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "").strip()

    if text == "/start":
        send_message(chat_id, "👋 Welcome!\nSend me a Terabox shortlink and I’ll fetch the video for you.")
        return {"ok": True}

    if any(domain in text for domain in VALID_DOMAINS):
        send_message(chat_id, "⏱ Processing your link... Please wait.")
        threading.Thread(target=lambda: asyncio.run(process_video(chat_id, text))).start()
    else:
        send_message(chat_id, "⚠️ That doesn’t look like a Terabox link.")
    return {"ok": True}


# ✅ Telegram helpers
def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text})

def send_video(chat_id, file_path):
    with open(file_path, "rb") as f:
        requests.post(f"{API_URL}/sendVideo", data={"chat_id": chat_id}, files={"video": f})

def debug_log(chat_id, text):
    try:
        requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text[:3500]})
    except:
        pass


# ================== Playwright Extractor ==================
async def process_video(chat_id, url):
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(url, timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=60000)

            # Extract window.file_list or window.playInfo
            file_list = await page.evaluate("window.file_list || window.playInfo || null")
            if not file_list:
                send_message(chat_id, "⚠️ Could not extract file info from page.")
                await browser.close()
                return

            # Convert to JSON string for debug
            file_json = json.dumps(file_list, indent=2)
            debug_log(chat_id, "🔎 file_list JSON:\n" + file_json[:3500])

            # Extract parameters
            # fs_id, sign, uk, timestamp, surl
            try:
                file0 = file_list[0] if isinstance(file_list, list) else list(file_list.values())[0]
                fs_id = file0.get("fs_id")
                sign = file0.get("sign")
                uk = file0.get("uk")
                timestamp = file0.get("timestamp") or file0.get("time") or 0
                surl = file0.get("surl") or ""

                if not all([fs_id, sign, uk]):
                    send_message(chat_id, "⚠️ Missing required parameters in file info.")
                    await browser.close()
                    return

                # Build playable video URL
                video_url = f"https://www.1024tera.com/api/play/playinfo?app_id=250528&fid_list=[{fs_id}]&sign={sign}&timestamp={timestamp}&uk={uk}&surl={surl}"
                send_message(chat_id, f"✅ Playable Video URL:\n{video_url}")

                # Optional: download and send video (if <50MB)
                path = download_video(video_url)
                if path:
                    send_video(chat_id, path)
                    os.remove(path)

            except Exception as e:
                send_message(chat_id, f"❌ Error parsing file info: {e}")

            await browser.close()

    except Exception as e:
        print("❌ Exception:", e, flush=True)
        send_message(chat_id, f"⚠️ Could not process the link: {e}")


def download_video(video_url):
    try:
        r = requests.get(video_url, stream=True, timeout=60)
        r.raise_for_status()
        fd, path = tempfile.mkstemp(suffix=".mp4")
        with os.fdopen(fd, "wb") as f:
            for chunk in r.iter_content(1024*1024):
                f.write(chunk)
        return path
    except Exception as e:
        print("❌ Download error:", e, flush=True)
        return None


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
