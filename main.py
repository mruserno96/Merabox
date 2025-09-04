from flask import Flask, request
import requests, os, tempfile, re, json, threading

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
    if "message" not in data:
        return {"ok": True}

    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "")

    if text == "/start":
        send_message(chat_id, "👋 Welcome!\nSend me a Terabox link and I’ll fetch the highest quality video for you.")
        return {"ok": True}

    if any(domain in text for domain in VALID_DOMAINS):
        send_message(chat_id, "⏱ Processing your link... Please wait.")
        threading.Thread(target=process_video, args=(chat_id, text)).start()
    else:
        send_message(chat_id, "⚠️ Please send a valid Terabox link.")

    return {"ok": True}


# ✅ Send text
def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", json={"chat_id": chat_id, "text": text})


# ✅ Send video
def send_video(chat_id, file_path):
    with open(file_path, "rb") as f:
        requests.post(f"{API_URL}/sendVideo", data={"chat_id": chat_id}, files={"video": f})


# ✅ Background processor
def process_video(chat_id, url):
    try:
        video_path = extract_and_download(url)
        if video_path:
            send_video(chat_id, video_path)
            os.remove(video_path)
        else:
            send_message(chat_id, "⚠️ Could not extract valid video link.")
    except Exception as e:
        print("❌ Exception:", e)
        send_message(chat_id, "⚠️ Could not extract valid video link.")


# ✅ Extract video (multi-method)
def extract_and_download(url: str):
    session = requests.Session()
    res = session.get(url, allow_redirects=True, timeout=30)
    html = res.text
    print("Resolved URL:", res.url)

    video_links = []

    # Method 1: JSON in HTML
    m = re.search(r'window\.playInfo\s*=\s*(\{.*?\});', html, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            video_links = collect_video_links(data)
            print("✅ Found links in window.playInfo:", len(video_links))
        except Exception as e:
            print("❌ Failed HTML JSON parse:", e)

    # Method 2: API with surl
    if not video_links:
        surl = re.search(r"surl=([a-zA-Z0-9_-]+)", url)
        if surl:
            api = f"https://www.1024tera.com/api/play/playinfo?surl={surl.group(1)}"
            print("📡 Trying API with surl:", api)
            r = session.get(api, timeout=30)
            try:
                data = r.json()
                video_links = collect_video_links(data)
                print("✅ Found links in surl API:", len(video_links))
            except Exception as e:
                print("❌ surl API failed:", e, r.text[:200])

    # Method 3: API with shareid & uk
    if not video_links:
        shareid = re.search(r"shareid=(\d+)", html)
        uk = re.search(r"uk=(\d+)", html)
        if shareid and uk:
            api = f"https://www.terabox.com/api/play/playinfo?shareid={shareid.group(1)}&uk={uk.group(1)}"
            print("📡 Trying API with shareid & uk:", api)
            r = session.get(api, timeout=30)
            try:
                data = r.json()
                video_links = collect_video_links(data)
                print("✅ Found links in shareid+uk API:", len(video_links))
            except Exception as e:
                print("❌ shareid+uk API failed:", e, r.text[:200])

    if not video_links:
        print("⚠️ No video links found at all")
        return None

    # Pick highest quality
    pref = ["1080", "720", "480", "360"]
    selected = next((l for q in pref for l in video_links if q in l), video_links[0])
    print("🎬 Selected:", selected)

    # Download
    vres = session.get(selected, stream=True, timeout=120)
    if vres.status_code == 200:
        tmp = tempfile.mktemp(suffix=".mp4")
        with open(tmp, "wb") as f:
            for chunk in vres.iter_content(1024*1024):
                if chunk:
                    f.write(chunk)
        return tmp

    return None


# ✅ Recursive link collector
def collect_video_links(obj):
    links = []
    def _scan(o):
        if isinstance(o, dict):
            for v in o.values():
                _scan(v)
        elif isinstance(o, list):
            for i in o:
                _scan(i)
        elif isinstance(o, str):
            if any(ext in o for ext in [".mp4", ".mkv", ".webm", ".mov"]):
                links.append(o.replace("\\u002F", "/"))
    _scan(obj)
    return links


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
