from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
from utils.download import download_audio
from config import BOT_TOKEN

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


# ── Telegram helpers (synchronous, no aiohttp needed) ──────────────

def tg_post(method: str, data: dict) -> dict:
    """Send a JSON request to the Telegram Bot API."""
    req = urllib.request.Request(
        f"{TELEGRAM_API}/{method}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def tg_send_audio(chat_id: int, info: dict):
    """Send an audio file to Telegram via multipart/form-data."""
    import requests as req_lib

    files = {"audio": open(info["audio_path"], "rb")}
    data = {"chat_id": chat_id, "caption": info["title"]}

    # Download and attach thumbnail if available
    thumb_path = None
    thumb_url = info.get("thumb_url")
    if thumb_url:
        try:
            r = req_lib.get(thumb_url, timeout=5)
            if r.status_code == 200:
                thumb_path = info["audio_path"] + "_thumb.jpg"
                with open(thumb_path, "wb") as f:
                    f.write(r.content)
                files["thumbnail"] = open(thumb_path, "rb")
        except Exception:
            pass

    req_lib.post(f"{TELEGRAM_API}/sendAudio", data=data, files=files)

    # Close file handles and clean up
    for f in files.values():
        f.close()
    if os.path.exists(info["audio_path"]):
        os.remove(info["audio_path"])
    if thumb_path and os.path.exists(thumb_path):
        os.remove(thumb_path)


# ── Vercel entry‑point ─────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 1. Read the incoming webhook payload
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            update = json.loads(body) if body else {}
        except Exception:
            self.send_response(400)
            self.end_headers()
            return

        # ── /start command ─────────────────────────────────────────
        if "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            text = msg.get("text", "")

            if text == "/start":
                keyboard = {
                    "inline_keyboard": [
                        [{"text": "📢 Подписаться на канал",
                          "url": "https://t.me/+J7NoSh8Z3RhMjky"}],
                        [{"text": "🛠 Сообщить об ошибке",
                          "callback_data": "report_error"}],
                    ]
                }
                tg_post("sendMessage", {
                    "chat_id": chat_id,
                    "text": "🎵 Отправь ссылку на YouTube — скачаю аудио!",
                    "reply_markup": keyboard,
                })

            # ── YouTube link ───────────────────────────────────────
            elif "youtube.com" in text or "youtu.be" in text:
                status = tg_post("sendMessage", {
                    "chat_id": chat_id,
                    "text": "⏳ Загружаю..."
                })
                status_msg_id = status["result"]["message_id"]

                try:
                    info = download_audio(text.strip(), "/tmp")
                    tg_send_audio(chat_id, info)
                    tg_post("deleteMessage", {
                        "chat_id": chat_id,
                        "message_id": status_msg_id,
                    })
                except Exception as e:
                    tg_post("editMessageText", {
                        "chat_id": chat_id,
                        "message_id": status_msg_id,
                        "text": f"❌ Ошибка: {str(e)[:200]}",
                    })

        # ── Callback queries (error report button) ─────────────────
        elif "callback_query" in update:
            cb = update["callback_query"]
            data = cb.get("data", "")
            chat_id = cb["message"]["chat"]["id"]
            if data == "report_error":
                tg_post("sendMessage", {
                    "chat_id": chat_id,
                    "text": "🛠 Пожалуйста, опиши проблему — я передам её администратору.",
                })
            tg_post("answerCallbackQuery", {"callback_query_id": cb["id"]})

        # 2. Always respond 200 OK to Telegram
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode())
