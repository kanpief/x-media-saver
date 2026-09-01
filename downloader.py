import os
import re
import json
import time
import math
import requests
import yt_dlp
from urllib.parse import urlparse, parse_qs


# Tự động phát hiện vị trí FFmpeg
FFMPEG_PATH = None
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_PATH = "ffmpeg"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
}

def detect_platform(url: str) -> str:
    """Tự động nhận diện nền tảng từ URL (X/Twitter hoặc YouTube)."""
    if not url:
        return ""
    url_lower = url.lower()
    if any(k in url_lower for k in ["youtube.com", "youtu.be", "music.youtube.com"]):
        return "youtube"
    if any(k in url_lower for k in ["twitter.com", "x.com", "vxtwitter.com", "fxtwitter.com", "fixupx.com"]):
        return "twitter"
    return "unknown"

# ==================== X / TWITTER EXTRACTOR ====================

def extract_tweet_id(url: str) -> str:
    """Trích xuất Tweet ID từ các dạng link X / Twitter khác nhau."""
    if not url:
        return ""
    match = re.search(r'(?:twitter\.com|x\.com|vxtwitter\.com|fxtwitter\.com|fixupx\.com)/[^/]+/status/(\d+)', url)
    if match:
        return match.group(1)
    
    match_status = re.search(r'/status/(\d+)', url)
    if match_status:
        return match_status.group(1)

    if re.match(r'^\d+$', url.strip()):
        return url.strip()
    return ""

def optimize_image_url(img_url: str) -> str:
    """Chuyển đổi URL ảnh của Twitter sang chất lượng gốc cao nhất (:orig hoặc format=jpg&name=orig)."""
    if not img_url:
        return img_url
    
    parsed = urlparse(img_url)
    if "twimg.com" in parsed.netloc:
        query = parse_qs(parsed.query)
        if "format" in query:
            fmt = query.get("format", ["jpg"])[0]
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?format={fmt}&name=orig"
        
        path = parsed.path
        path = re.sub(r':(large|medium|small|thumb|\d+x\d+)$', '', path)
        return f"{parsed.scheme}://{parsed.netloc}{path}:orig"
    
    return img_url

def extract_via_syndication(tweet_id: str) -> dict:
    """Lấy thông tin và media qua CDN Syndication API của Twitter."""
    url = f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&token=5"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    if resp.status_code != 200:
        return None
    data = resp.json()
    if not data or data.get("__typename") != "Tweet":
        if not data:
            return None

    user = data.get("user", {})
    author_name = user.get("name", "X User")
    author_username = user.get("screen_name", "")
    author_avatar = user.get("profile_image_url_https", "")
    if author_avatar:
        author_avatar = author_avatar.replace("_normal.", "_400x400.")
    text = data.get("text", "")
    created_at = data.get("created_at", "")

    photos = []
    videos = []

    if "photos" in data and isinstance(data["photos"], list):
        for p in data["photos"]:
            raw_url = p.get("url", "")
            orig_url = optimize_image_url(raw_url)
            photos.append({
                "type": "image",
                "preview_url": raw_url,
                "download_url": orig_url,
                "width": p.get("width"),
                "height": p.get("height"),
                "alt": p.get("altText", "")
            })

    if "video" in data:
        v_info = data["video"]
        variants = v_info.get("variants", [])
        mp4_variants = [v for v in variants if v.get("type") == "video/mp4" or ".mp4" in v.get("src", "")]
        
        def get_variant_quality_score(item):
            src = item.get("src", "")
            res_match = re.search(r'/(\d+)x(\d+)/', src)
            if res_match:
                return int(res_match.group(1)) * int(res_match.group(2))
            return 0

        mp4_variants.sort(key=get_variant_quality_score, reverse=True)

        if mp4_variants:
            quality_list = []
            for v in mp4_variants:
                src = v.get("src", "")
                res_match = re.search(r'/(\d+)x(\d+)/', src)
                res_label = f"{res_match.group(1)}x{res_match.group(2)}" if res_match else "HD MP4"
                quality_list.append({
                    "url": src,
                    "resolution": res_label,
                })

            videos.append({
                "type": "video",
                "preview_url": v_info.get("poster", photos[0]["preview_url"] if photos else ""),
                "download_url": mp4_variants[0].get("src"),
                "duration_ms": v_info.get("durationMillis", 0),
                "qualities": quality_list,
            })

    if photos or videos:
        return {
            "platform": "twitter",
            "tweet_id": tweet_id,
            "author_name": author_name,
            "author_username": author_username,
            "author_avatar": author_avatar,
            "text": text,
            "created_at": created_at,
            "photos": photos,
            "videos": videos,
            "source": "syndication"
        }
    return None

def extract_via_vxtwitter(tweet_id: str) -> dict:
    """Trích xuất qua vxTwitter API."""
    url = f"https://api.vxtwitter.com/Twitter/status/{tweet_id}"
    resp = requests.get(url, headers=HEADERS, timeout=8)
    if resp.status_code != 200:
        return None
    data = resp.json()
    if not data:
        return None

    author_name = data.get("user_name", "X User")
    author_username = data.get("user_screen_name", "")
    author_avatar = data.get("user_profile_image_url", "")
    if author_avatar:
        author_avatar = author_avatar.replace("_normal.", "_400x400.")
    text = data.get("text", "")
    created_at = data.get("date", "")

    photos = []
    videos = []

    media_extended = data.get("media_extended", [])
    if media_extended:
        for m in media_extended:
            mtype = m.get("type", "")
            raw_url = m.get("url", "")
            if not raw_url:
                continue

            if mtype == "image":
                photos.append({
                    "type": "image",
                    "preview_url": raw_url,
                    "download_url": optimize_image_url(raw_url),
                    "width": m.get("size", {}).get("width"),
                    "height": m.get("size", {}).get("height"),
                })
            elif mtype in ["video", "gif"]:
                videos.append({
                    "type": mtype,
                    "preview_url": m.get("thumbnail_url", ""),
                    "download_url": raw_url,
                    "qualities": [{"url": raw_url, "resolution": "Bản gốc Full HD (Highest)"}]
                })

    if photos or videos:
        return {
            "platform": "twitter",
            "tweet_id": tweet_id,
            "author_name": author_name,
            "author_username": author_username,
            "author_avatar": author_avatar,
            "text": text,
            "created_at": created_at,
            "photos": photos,
            "videos": videos,
            "source": "vxtwitter"
        }
    return None

def extract_tweet_media(url_or_id: str) -> dict:
    """Trích xuất ảnh và video từ X/Twitter."""
    tweet_id = extract_tweet_id(url_or_id)
    if not tweet_id:
        raise ValueError("Không tìm thấy Tweet ID hợp lệ trong liên kết. Vui lòng kiểm tra lại liên kết X.")

    try:
        data = extract_via_syndication(tweet_id)
        if data and (data["photos"] or data["videos"]):
            return data
    except Exception as e:
        print(f"Syndication error: {e}")

    try:
        data = extract_via_vxtwitter(tweet_id)
        if data and (data["photos"] or data["videos"]):
            return data
    except Exception as e:
        print(f"VxTwitter error: {e}")

    raise ValueError("Không tìm thấy ảnh hoặc video trong bài viết này, hoặc bài viết đang ở chế độ riêng tư.")


# ==================== YOUTUBE & MP3 EXTRACTOR ====================

def format_duration(seconds: int) -> str:
    """Định dạng số giây sang mm:ss hoặc hh:mm:ss."""
    if not seconds:
        return "0:00"
    try:
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
    except Exception:
        return "0:00"

def clean_youtube_url(url: str) -> str:

    """Loại bỏ các tham số playlist, radio mix (&list=, &start_radio=, &index=) để chỉ trích xuất đúng 1 video đích tức thì."""
    if not url:
        return url
    shorts_match = re.search(r'youtube\.com/shorts/([a-zA-Z0-9_-]+)', url)
    if shorts_match:
        return f"https://www.youtube.com/watch?v={shorts_match.group(1)}"
    ytbe_match = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', url)
    if ytbe_match:
        return f"https://www.youtube.com/watch?v={ytbe_match.group(1)}"
    watch_match = re.search(r'[?&]v=([a-zA-Z0-9_-]+)', url)
    if watch_match:
        return f"https://www.youtube.com/watch?v={watch_match.group(1)}"
    return url

def get_yt_opts(extra_opts=None):
    """Tạo cấu hình yt-dlp tối ưu vượt qua bot-check của YouTube (kể cả trên IP Datacenter Render)."""
    cookies_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
    cookies_env = os.environ.get("YOUTUBE_COOKIES") or os.environ.get("COOKIES")
    if cookies_env and not os.path.exists(cookies_file):
        try:
            with open(cookies_file, "w", encoding="utf-8") as f:
                f.write(cookies_env)
        except Exception:
            pass

    opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'extract_flat': False,
        'extractor_args': {
            'youtube': {
                'player_client': ['tv_embedded', 'android_vr', 'android'],
                'player_skip': ['webpage', 'configs']
            }
        },
        'http_headers': HEADERS,
    }
    if FFMPEG_PATH:
        opts['ffmpeg_location'] = FFMPEG_PATH
    
    if os.path.exists(cookies_file):
        opts['cookiefile'] = cookies_file

    if extra_opts:
        opts.update(extra_opts)
    return opts

def extract_via_oembed(video_id: str) -> dict:
    """Trích xuất thông tin tiêu đề, tác giả, thumbnail trực tiếp qua YouTube oEmbed API (không bao giờ bị bot check)."""
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        resp = requests.get(url, headers=HEADERS, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "title": data.get("title", "YouTube Video"),
                "uploader": data.get("author_name", "YouTube Channel"),
                "thumbnail": f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
            }
    except Exception:
        pass
    return None

def convert_via_cloud_api(video_url: str, target_type: str, quality_id: str, output_path: str) -> str:
    """Tải và chuyển đổi MP3/MP4 qua Cloud Converter Server khi yt-dlp bị Render IP chặn."""
    fmt = "mp3" if target_type == "mp3" else ("1080" if "1080" in quality_id else "720")
    api_url = f"https://loader.to/ajax/download.php?button=1&start=1&end=1&format={fmt}&url={video_url}"
    
    resp = requests.get(api_url, headers=HEADERS, timeout=12)
    resp_data = resp.json()
    if not resp_data.get("success"):
        raise ValueError("Cloud API chuyển đổi phản hồi không thành công.")

    progress_url = resp_data.get("progress_url")
    if not progress_url:
        raise ValueError("Không nhận được luồng chuyển đổi từ máy chủ.")

    download_url = None
    for _ in range(40): # Đợi tối đa 60 giây cho các file nhạc dài
        time.sleep(1.5)
        try:
            pr_res = requests.get(progress_url, headers=HEADERS, timeout=8).json()
            if pr_res.get("download_url"):
                download_url = pr_res["download_url"]
                break
            if pr_res.get("success") == 1 and pr_res.get("progress") == 1000:
                download_url = pr_res.get("download_url")
                break
        except Exception:
            continue

    if not download_url:
        raise ValueError("Quá trình chuyển đổi vượt quá thời gian cho phép. Vui lòng thử lại!")

    # Tải file từ download_url về output_path
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    ext = "mp3" if target_type == "mp3" else "mp4"
    base_output = os.path.splitext(output_path)[0]
    final_file = f"{base_output}.{ext}"

    download_file(download_url, final_file)
    return final_file

def extract_youtube_media(url: str) -> dict:
    """Trích xuất thông tin video YouTube, phân loại các định dạng Video MP4 & Audio MP3 với cơ chế đa tầng."""
    clean_url = clean_youtube_url(url)
    
    # Lấy video ID
    video_id = ""
    v_match = re.search(r'[?&]v=([a-zA-Z0-9_-]+)', clean_url)
    if v_match:
        video_id = v_match.group(1)

    title = "YouTube Video"
    uploader = "YouTube Channel"
    duration = 0
    view_count = "N/A"
    thumbnail = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg" if video_id else ""

    # Bước 1: Thử trích xuất qua yt-dlp
    client_candidates = [
        ['tv_embedded', 'android_vr'],
        ['android', 'mweb'],
        ['ios', 'web_creator']
    ]
    
    extracted_via_ytdlp = False
    for clients in client_candidates:
        try:
            ydl_opts = get_yt_opts({
                'skip_download': True,
                'extractor_args': {
                    'youtube': {
                        'player_client': clients,
                        'player_skip': ['webpage', 'configs']
                    }
                }
            })
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(clean_url, download=False)
                if info:
                    if "entries" in info and info["entries"]:
                        info = info["entries"][0]
                    title = info.get('title', title)
                    uploader = info.get('uploader', uploader)
                    duration = info.get('duration', duration)
                    view_count = f"{info.get('view_count', 0):,}" if info.get('view_count') else "N/A"
                    thumbnail = info.get('thumbnail', thumbnail)
                    extracted_via_ytdlp = True
                    break
        except Exception:
            continue

    # Bước 2: Nếu yt-dlp bị Render IP chặn, fallback sang YouTube Official oEmbed API (không bao giờ bị bot check)
    if not extracted_via_ytdlp and video_id:
        oembed_data = extract_via_oembed(video_id)
        if oembed_data:
            title = oembed_data.get("title", title)
            uploader = oembed_data.get("uploader", uploader)
            thumbnail = oembed_data.get("thumbnail", thumbnail)
            duration = 0

    video_qualities = [
        {"id": "bestvideo+bestaudio/best", "label": "Full HD / 4K Tốt Nhất (MP4)", "format_id": "best", "ext": "mp4"},
        {"id": "bestvideo[height<=1080]+bestaudio/best[height<=1080]", "label": "1080p Full HD (MP4)", "format_id": "1080p", "ext": "mp4"},
        {"id": "bestvideo[height<=720]+bestaudio/best[height<=720]", "label": "720p HD (MP4)", "format_id": "720p", "ext": "mp4"},
        {"id": "bestvideo[height<=480]+bestaudio/best[height<=480]", "label": "480p Tiết Kiệm (MP4)", "format_id": "480p", "ext": "mp4"},
        {"id": "bestvideo[height<=360]+bestaudio/best[height<=360]", "label": "360p Nhẹ Nhất (MP4)", "format_id": "360p", "ext": "mp4"},
    ]

    audio_qualities = [
        {"id": "320", "label": "Chất lượng cực cao (MP3 320kbps)", "bitrate": "320k", "ext": "mp3"},
        {"id": "192", "label": "Chất lượng chuẩn Studio (MP3 192kbps)", "bitrate": "192k", "ext": "mp3"},
        {"id": "128", "label": "Chất lượng tiêu chuẩn (MP3 128kbps)", "bitrate": "128k", "ext": "mp3"},
    ]

    return {
        "platform": "youtube",
        "video_id": video_id,
        "title": title,
        "uploader": uploader,
        "duration": duration,
        "duration_str": format_duration(duration) if duration else "Chuẩn HD",
        "view_count": view_count,
        "thumbnail": thumbnail,
        "video_qualities": video_qualities,
        "audio_qualities": audio_qualities,
        "direct_stream_url": thumbnail,
        "url": clean_url
    }

def download_youtube_file(url: str, target_type: str, quality_id: str, output_path: str) -> str:
    """Tải và chuyển đổi YouTube video hoặc MP3 audio (tự động fallback sang Cloud Converter nếu bị chặn)."""
    clean_url = clean_youtube_url(url)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    base_output = os.path.splitext(output_path)[0]

    # Cách 1: Thử tải qua yt-dlp
    try:
        extra_opts = {
            'outtmpl': f"{base_output}.%(ext)s",
            'noplaylist': True,
        }
        if target_type == "mp3":
            extra_opts.update({
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
                'concurrent_fragment_downloads': 4,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': quality_id or '320',
                }],
            })
        else:
            format_spec = quality_id or 'bestvideo+bestaudio/best'
            extra_opts.update({
                'format': format_spec,
                'concurrent_fragment_downloads': 4,
                'merge_output_format': 'mp4',
            })


        ydl_opts = get_yt_opts(extra_opts)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([clean_url])

        expected_file = f"{base_output}.mp3" if target_type == "mp3" else f"{base_output}.mp4"
        if os.path.exists(expected_file):
            return expected_file
        for ext in [".mp4", ".mp3", ".m4a", ".webm", ".mkv"]:
            p = f"{base_output}{ext}"
            if os.path.exists(p):
                return p
    except Exception as e:
        print(f"yt-dlp download failed, switching to cloud converter: {e}")

    # Cách 2: Tự động fallback sang Cloud Converter Server
    return convert_via_cloud_api(clean_url, target_type, quality_id, output_path)



# ==================== MAIN DISPATCHER ====================

def extract_media(url: str) -> dict:
    """Tự động phân loại và trích xuất từ X/Twitter hoặc YouTube."""
    platform = detect_platform(url)
    if platform == "youtube":
        return extract_youtube_media(url)
    elif platform == "twitter":
        return extract_tweet_media(url)
    else:
        # Thử X trước, sau đó YouTube
        try:
            return extract_tweet_media(url)
        except Exception:
            try:
                return extract_youtube_media(url)
            except Exception:
                raise ValueError("Liên kết không được hỗ trợ. Vui lòng nhập link từ X (Twitter) hoặc YouTube!")

def download_file(url: str, save_path: str, chunk_size: int = 65536) -> str:
    """Tải một file từ URL trực tiếp và lưu vào đĩa."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    resp = requests.get(url, headers=HEADERS, stream=True, timeout=30)
    resp.raise_for_status()
    with open(save_path, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)
    return save_path
