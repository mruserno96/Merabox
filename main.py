from fastapi import FastAPI, Request
import requests
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")  # put in environment on server
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = FastAPI()

# Set your webhook URL: https://your-app.onrender.com/webhook
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if "terabox" in text:
            # TODO: implement terabox download logic
            file_url = await get_terabox_link(text)
            requests.post(f"{API_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": f"Download link: {file_url}"
            })
        else:
            requests.post(f"{API_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "Send me a Terabox link."
            })
    return {"ok": True}


async def get_terabox_link(url: str) -> str:
    """
    Here you implement terabox direct link generator
    (either by scraping or using an API).
    For now return dummy.
    """
    return "https://example.com/download.mp4"
