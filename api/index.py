import json, os, asyncio
import aiohttp
from utils.download import download_audio
from config import BOT_TOKEN

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

async def _post(method: str, data: dict):
    async with aiohttp.ClientSession() as sess:
        async with sess.post(f"{TELEGRAM_API}/{method}", json=data) as resp:
            return await resp.json()

async def _send_audio(chat_id: int, info: dict):
    # Prepare multipart form
    files = {"audio": open(info["audio_path"], "rb")}
    payload = {"chat_id": chat_id, "caption": info["title"]}
    thumb_url = info.get("thumb_url")
    if thumb_url:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(thumb_url) as r:
                if r.status == 200:
                    thumb_bytes = await r.read()
                    files["thumb"] = aiohttp.BytesPayload(thumb_bytes, filename="thumb.jpg")
    async with aiohttp.ClientSession() as sess:
        await sess.post(f"{TELEGRAM_API}/sendAudio", data=payload, files=files)
    # Cleanup temporary audio file
    if os.path.exists(info["audio_path"]):
        os.remove(info["audio_path"])

async def _process(chat_id: int, url: str, status_msg_id: int):
    info = download_audio(url, "/tmp")
    await _send_audio(chat_id, info)
    await _post("deleteMessage", {"chat_id": chat_id, "message_id": status_msg_id})

def handler(event, context):
    """Vercel serverless entrypoint.
    `event` contains the HTTP request; we parse the Telegram update from its body.
    Must return a dict with `statusCode` and optional `body`.
    """
    try:
        body = event.get("body", "")
        update = json.loads(body) if body else {}
    except Exception:
        return {"statusCode": 400, "body": "bad request"}

    loop = asyncio.get_event_loop()

    # /start command – send welcome keyboard
    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")
        if text == "/start":
            keyboard = {
                "inline_keyboard": [
                    [{"text": "Подписаться на канал", "url": "https://t.me/+J7NoSh8Z3RhMjky"}],
                    [{"text": "Сообщить об ошибке", "callback_data": "report_error"}]
                ]
            }
            loop.create_task(
                _post("sendMessage", {
                    "chat_id": chat_id,
                    "text": "🎵 Отправь ссылку на YouTube — получу MP3",
                    "reply_markup": json.dumps(keyboard)
                })
            )
            return {"statusCode": 200, "body": ""}

        # Assume any other message is a YouTube link
        if "youtube.com" in text or "youtu.be" in text:
            # Immediate acknowledgment to Telegram
            status = asyncio.run(_post("sendMessage", {"chat_id": chat_id, "text": "⏳ Загружаю..."}))
            # Schedule background processing (non‑blocking response)
            loop.create_task(_process(chat_id, text, status["result"]["message_id"]))
            return {"statusCode": 200, "body": ""}

    # Callback queries (e.g., error report button)
    if "callback_query" in update:
        cb = update["callback_query"]
        data = cb.get("data", "")
        chat_id = cb["message"]["chat"]["id"]
        if data == "report_error":
            loop.create_task(
                _post("sendMessage", {
                    "chat_id": chat_id,
                    "text": "🛠 Пожалуйста, опиши проблему, я передам её администратору."
                })
            )
        return {"statusCode": 200, "body": ""}

    return {"statusCode": 200, "body": ""}
