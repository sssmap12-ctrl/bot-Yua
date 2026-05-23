import os
import aiohttp
import json
import asyncio
from aiohttp import web
from utils.download import download_audio
from config import BOT_TOKEN, ADMIN_CHAT_ID

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

async def _post(method: str, payload: dict, files: dict | None = None):
    url = f"{BASE_URL}/{method}"
    async with aiohttp.ClientSession() as sess:
        if files:
            data = aiohttp.FormData()
            for k, v in payload.items():
                data.add_field(k, str(v))
            for name, fileobj in files.items():
                data.add_field(name, fileobj, filename=os.path.basename(fileobj.name))
            async with sess.post(url, data=data) as resp:
                return await resp.json()
        else:
            async with sess.post(url, json=payload) as resp:
                return await resp.json()

async def send_audio(chat_id: int, data: dict):
    # Prepare optional thumbnail download
    files = {"audio": open(data["audio_path"], "rb")}
    if data.get("thumb_url"):
        async with aiohttp.ClientSession() as s:
            async with s.get(data["thumb_url"]) as r:
                if r.status == 200:
                    thumb_bytes = await r.read()
                    files["thumb"] = aiohttp.BytesPayload(thumb_bytes, filename="thumb.jpg")
    await _post(
        "sendAudio",
        {
            "chat_id": chat_id,
            "caption": data["title"],
            "disable_notification": True,
        },
        files,
    )
    # close file handles
    for f in files.values():
        f.close()

async def handle_callback(cb):
    data = cb["data"]
    chat_id = cb["message"]["chat"]["id"]
    if data == "report_error":
        await _post(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": "🛠 Пожалуйста, опишите проблему, я передам её администратору.",
            },
        )
    # future: video download callback can be added here

async def webhook(request):
    update = await request.json()
    # start command – show keyboard
    if "message" in update and update["message"].get("text") == "/start":
        keyboard = {
            "inline_keyboard": [
                [{"text": "Подписаться на канал", "url": "https://t.me/+J7NoSh8Z3RhMjky"}],
                [{"text": "Сообщить об ошибке", "callback_data": "report_error"}],
            ]
        }
        await _post(
            "sendMessage",
            {
                "chat_id": update["message"]["chat"]["id"],
                "text": "🎵 Отправь ссылку на YouTube — получу MP3",
                "reply_markup": json.dumps(keyboard),
            },
        )
        return web.Response()
    # handle YouTube link
    if "message" in update and "text" in update["message"]:
        url = update["message"]["text"].strip()
        if not ("youtube.com" in url or "youtu.be" in url):
            return web.Response()
        chat_id = update["message"]["chat"]["id"]
        # Immediately acknowledge Telegram with a thin status message (200 OK)
        # We'll send a separate "Загружаю..." message and then continue in background
        status = await _post(
            "sendMessage",
            {"chat_id": chat_id, "text": "⏳ Загружаю..."},
        )
        # Spawn background task – Vercel may keep it alive long enough
        async def _process():
            out_dir = "/tmp"
            data = download_audio(url, out_dir)
            await send_audio(chat_id, data)
            # delete the "Загружаю..." message
            await _post(
                "deleteMessage",
                {"chat_id": chat_id, "message_id": status["result"]["message_id"]},
            )
            # cleanup temp file
            if os.path.exists(data["audio_path"]):
                os.remove(data["audio_path"])
        # schedule without awaiting – immediate 200 response
        asyncio.create_task(_process())
        return web.Response()
    # callback queries
    if "callback_query" in update:
        await handle_callback(update["callback_query"])
        return web.Response()
    return web.Response()

app = web.Application()
app.router.add_post("/", webhook)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    web.run_app(app, port=port)
