from flask import Flask, request
import requests
import os
import tempfile

BOT_TOKEN = os.getenv("BOT_TOKEN")  # set on Render
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Valid Terabox domains
VALID_DOMAINS = [
    "terabox.fun",
    "terabox.app",
    "1024tera.com",
    "teraboxapp.com",
    "1024terabox.com"
]

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Terabox Test Bot running!"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if any(domain in text for domain in VALID_DOMAINS):
            try:
                video_path = download_terabox_video(text)

                if video_path:
                    send_video(chat_id, video_path)
                    os.remove(video_path)
                else:
                    send_message(chat_id, "⚠️ Could not extract valid video link.")
            except Exception as e:
                send_message(chat_id, f"❌ Error: {str(e)}")
        else:
            send_message(chat_id, "Send me a valid Terabox link (test mode).")

    return {"ok": True}

# ✅ send text
def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })

# ✅ send video file
def send_video(chat_id, file_path):
    with open(file_path, "rb") as f:
        requests.post(f"{API_URL}/sendVideo", data={"chat_id": chat_id}, files={"video": f})

# ✅ download video after resolving redirect
def download_terabox_video(url: str):
    session = requests.Session()
    res = session.get(url, allow_redirects=True, timeout=30)

    final_url = res.url
    print("Resolved URL:", final_url)

    # try downloading content
    video_res = session.get(final_url, stream=True, timeout=60)

    if video_res.status_code == 200 and "video" in video_res.headers.get("Content-Type", ""):
        tmp_file = tempfile.mktemp(suffix=".mp4")
        with open(tmp_file, "wb") as f:
            for chunk in video_res.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
        return tmp_file

    return None

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
