import os
import uuid
import subprocess
import yt_dlp

# Maximum total duration (7 minutes) in seconds
MAX_SECONDS = 420

def _run_ffmpeg(args: list[str]):
    """Run ffmpeg with the given argument list, suppress output, raise on error."""
    subprocess.run(["ffmpeg", *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def download_audio(url: str, out_dir: str) -> dict:
    """Download a YouTube video as audio, trim to MAX_SECONDS, convert to M4A.

    Returns a dict with:
        title – track title (used as caption)
        audio_path – absolute path to the final .m4a file
        audio_ext – always "m4a"
        thumb_url – optional thumbnail URL (may be None)
    """
    # 1️⃣ Retrieve video info (title, thumbnail) without downloading
    with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    title = info.get("title", f"track_{uuid.uuid4().hex[:8]}")
    thumb_url = info.get("thumbnail")

    # 2️⃣ Download best audio as temporary MP3
    tmp_mp3_template = os.path.join(out_dir, f"{uuid.uuid4().hex}.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": tmp_mp3_template,
        "quiet": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # Resolve the generated MP3 filename
    mp3_filename = next(p for p in os.listdir(out_dir) if p.endswith('.mp3'))
    mp3_path = os.path.join(out_dir, mp3_filename)

    # 3️⃣ Trim to MAX_SECONDS (if longer)
    trimmed_mp3 = os.path.join(out_dir, f"trim_{uuid.uuid4().hex}.mp3")
    _run_ffmpeg(["-y", "-i", mp3_path, "-t", str(MAX_SECONDS), trimmed_mp3])
    os.remove(mp3_path)

    # 4️⃣ Convert trimmed MP3 to M4A (always)
    final_m4a = os.path.join(out_dir, f"{uuid.uuid4().hex}.m4a")
    _run_ffmpeg(["-y", "-i", trimmed_mp3, "-c:a", "aac", "-b:a", "192k", final_m4a])
    os.remove(trimmed_mp3)

    return {
        "title": title,
        "audio_path": final_m4a,
        "audio_ext": "m4a",
        "thumb_url": thumb_url,
    }
