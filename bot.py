import os
import yt_dlp
from aiogram import Bot, Dispatcher, types
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command

TOKEN = "8841128083:AAHNLQNSY6TPuOAzNO_aGbOBEIbkFVTvCoA"
bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(msg: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Подписаться на канал", url="https://t.me/+J7NoSh8Z3RhMjky")],
                                         [InlineKeyboardButton(text="Сообщить об ошибке", callback_data="report_error")]])
    await msg.answer("🎵 Отправь ссылку на YouTube — получу MP3", reply_markup=keyboard)

@dp.message()
async def download(msg: types.Message):
    url = msg.text.strip()
    if "youtube.com" not in url and "youtu.be" not in url:
        return

    status = await msg.answer("⏳ Загружаю...")
    
    # Extract video info first to get title and thumbnail
    ydl_info_opts = {
        'quiet': True,
        'skip_download': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_info_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        title = info.get('title', f"track_{msg.message_id}")
        safe_title = "_".join(title.split())
        thumbnail_url = info.get('thumbnail')
    except Exception as e:
        await status.edit_text(f"❌ Ошибка получения информации: {str(e)[:100]}")
        return

    # Download audio
    filename = f"audio_{msg.message_id}_{safe_title}"
    mp3_file = f"{filename}.mp3"
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': filename,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        if os.path.exists(mp3_file):
            # Download thumbnail for cover if available
            thumb_path = None
            if thumbnail_url:
                import requests, pathlib, uuid
                try:
                    resp = requests.get(thumbnail_url, timeout=10)
                    if resp.status_code == 200:
                        ext = pathlib.Path(thumbnail_url).suffix or '.jpg'
                        thumb_path = f"{filename}_thumb{ext}"
                        with open(thumb_path, 'wb') as f:
                            f.write(resp.content)
                except Exception:
                    thumb_path = None
            # Prepare keyboard for optional video download
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Скачать видео", callback_data=f"download_video|{url}|{msg.message_id}")]])
            await bot.send_audio(msg.chat.id, FSInputFile(mp3_file), caption=title, thumb=FSInputFile(thumb_path) if thumb_path else None, reply_markup=keyboard)
            await status.delete()
            os.remove(mp3_file)
            if thumb_path:
                os.remove(thumb_path)
        else:
            await status.edit_text("❌ Ошибка: файл не создан")
    except Exception as e:
        await status.edit_text(f"❌ Ошибка: {str(e)[:100]}")

# ⚠️ ЭТА СТРОКА ОБЯЗАТЕЛЬНА ДЛЯ ЗАПУСКА
if __name__ == "__main__":
    print("Бот запущен...")
    dp.run_polling(bot)

# Callback handling for video download and error reports
@dp.callback_query()
async def handle_callbacks(cb: CallbackQuery):
    data = cb.data
    if data == "report_error":
        await cb.message.answer("🛠 Пожалуйста, опишите проблему, и мы постараемся её решить.")
        # Here you could forward the message to admin; placeholder admin_id
        # await bot.send_message(admin_id, f"Error report from {cb.from_user.id}: ...")
        await cb.answer()
    elif data.startswith("download_video"):
        # data format: download_video|<url>|<msg_id>
        parts = data.split("|")
        if len(parts) == 3:
            _, url, orig_msg_id = parts
            status = await cb.message.answer("⏳ Скачиваю видео...")
            filename = f"video_{orig_msg_id}"
            video_file = f"{filename}.mp4"
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best',
                'outtmpl': filename,
                'quiet': True,
                'merge_output_format': 'mp4',
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                if os.path.exists(video_file):
                    await bot.send_video(cb.message.chat.id, FSInputFile(video_file))
                    await status.delete()
                    os.remove(video_file)
                else:
                    await status.edit_text("❌ Ошибка: видео не создано")
            except Exception as e:
                await status.edit_text(f"❌ Ошибка: {str(e)[:100]}")
        await cb.answer()