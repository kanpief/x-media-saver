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

# Danh sách domain được hỗ trợ
SUPPORTED_PLATFORMS = {
    "twitter": ["twitter.com", "x.com", "vxtwitter.com", "fxtwitter.com", "fixupx.com"],
    "youtube": ["youtube.com", "youtu.be", "music.youtube.com"],
    "tiktok": ["tiktok.com", "vt.tiktok.com", "vm.tiktok.com"],
    "douyin": ["douyin.com", "iesdouyin.com", "v.douyin.com"],
    "facebook": ["facebook.com", "fb.watch", "fb.com"],
    "instagram": ["instagram.com", "instagr.am", "ig.me"]
}

# ==================== AN TOÀN & BẢO MẬT (SECURITY & SANITIZATION) ====================

def is_safe_url(url: str) -> bool:
    """Kiểm tra URL có hợp lệ và ngăn chặn các cuộc tấn công SSRF (IP nội bộ, localhost)."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ["http", "https"]:
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        hostname_lower = hostname.lower()
        if hostname_lower in ["localhost", "127.0.0.1", "0.0.0.0", "::1"]:
            return False
        if hostname_lower.startswith("192.168.") or hostname_lower.startswith("10.") or hostname_lower.startswith("172."):
            return False
        if hostname_lower.endswith(".local") or hostname_lower.endswith(".internal"):
            return False
        return True
    except Exception:
        return False

def extract_url_from_text(raw_text: str) -> str:
    """Trích xuất liên kết sạch từ văn bản chia sẻ, loại bỏ các ký tự tiếng Trung hoặc văn bản thừa."""
    if not raw_text:
        return ""
    text = raw_text.strip()
    match = re.search(r'(https?://[^\s<>"\'\u4e00-\u9fa5，。！？]+)', text)
    if match:
        url = match.group(1).strip()
        # Loại bỏ dấu gạch chéo hoặc dấu câu thừa ở cuối
        return re.sub(r'[,;。，]+$', '', url)
    return text

def detect_platform(url: str) -> str:
    """Tự động nhận diện nền tảng từ URL (X/Twitter, YouTube, TikTok, Douyin, Facebook, Instagram)."""
    if not url:
        return "invalid"
    clean_url = extract_url_from_text(url).lower()
    for platform, domains in SUPPORTED_PLATFORMS.items():
        if any(d in clean_url for d in domains):
            return platform
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
    clean_url = extract_url_from_text(url_or_id)
    tweet_id = extract_tweet_id(clean_url)
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

    raise ValueError("Không tìm thấy ảnh hoặc video trong bài viết X này, hoặc bài viết đang ở chế độ riêng tư.")


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
    clean_url = extract_url_from_text(url)
    shorts_match = re.search(r'youtube\.com/shorts/([a-zA-Z0-9_-]+)', clean_url)
    if shorts_match:
        return f"https://www.youtube.com/watch?v={shorts_match.group(1)}"
    ytbe_match = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', clean_url)
    if ytbe_match:
        return f"https://www.youtube.com/watch?v={ytbe_match.group(1)}"
    watch_match = re.search(r'[?&]v=([a-zA-Z0-9_-]+)', clean_url)
    if watch_match:
        return f"https://www.youtube.com/watch?v={watch_match.group(1)}"
    return clean_url

def get_yt_opts(extra_opts=None):
    """Tạo cấu hình yt-dlp tối ưu."""
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
    """Trích xuất thông tin tiêu đề, tác giả, thumbnail trực tiếp qua YouTube oEmbed API."""
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
    """Tải và chuyển đổi MP3/MP4 qua Cloud Converter Server khi yt-dlp bị chặn."""
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
    for _ in range(40):
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

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    ext = "mp3" if target_type == "mp3" else "mp4"
    base_output = os.path.splitext(output_path)[0]
    final_file = f"{base_output}.{ext}"

    download_file(download_url, final_file)
    return final_file

def extract_youtube_media(url: str) -> dict:
    """Trích xuất thông tin video YouTube, phân loại các định dạng Video MP4 & Audio MP3 siêu nhanh."""
    clean_url = clean_youtube_url(url)
    
    video_id = ""
    v_match = re.search(r'[?&]v=([a-zA-Z0-9_-]+)', clean_url)
    if v_match:
        video_id = v_match.group(1)

    title = "YouTube Video"
    uploader = "YouTube Channel"
    duration = 0
    view_count = "N/A"
    thumbnail = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg" if video_id else ""

    # Bước 1: Trích xuất siêu nhanh qua oEmbed API (không bao giờ bị bot block, phản hồi tức thì < 200ms)
    if video_id:
        oembed_data = extract_via_oembed(video_id)
        if oembed_data:
            title = oembed_data.get("title", title)
            uploader = oembed_data.get("uploader", uploader)
            thumbnail = oembed_data.get("thumbnail", thumbnail)

    # Bước 2: Thử lấy thêm thông tin thời lượng và view qua yt-dlp
    client_candidates = [
        ['android', 'ios'],
        None
    ]
    
    for clients in client_candidates:
        try:
            extra = {
                'skip_download': True,
                'noplaylist': True,
                'extract_flat': False
            }
            if clients:
                extra['extractor_args'] = {'youtube': {'player_client': clients}}
            ydl_opts = get_yt_opts(extra)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(clean_url, download=False)
                if info:
                    if "entries" in info and info["entries"]:
                        info = info["entries"][0]
                    title = info.get('title') or title
                    uploader = info.get('uploader') or uploader
                    duration = info.get('duration') or duration
                    view_count = f"{info.get('view_count', 0):,}" if info.get('view_count') else "N/A"
                    thumbnail = info.get('thumbnail') or thumbnail
                    break
        except Exception:
            continue

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

def download_youtube_file(url: str, target_type: str, quality_id: str, output_path: str, progress_callback=None) -> str:
    """Tải và chuyển đổi YouTube video hoặc MP3 audio."""
    clean_url = clean_youtube_url(url)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    base_output = os.path.splitext(output_path)[0]

    try:
        extra_opts = {
            'outtmpl': f"{base_output}.%(ext)s",
            'noplaylist': True,
            'retries': 5,
            'fragment_retries': 5,
            'buffersize': 32768,
            'http_chunk_size': 10485760,
        }
        
        if progress_callback:
            extra_opts['progress_hooks'] = [progress_callback]

        if target_type == "mp3":
            extra_opts.update({
                'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best',
                'concurrent_fragment_downloads': 8,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': quality_id or '320',
                }],
                'postprocessor_args': ['-threads', '2'],
            })
        else:
            format_spec = quality_id or 'bestvideo+bestaudio/best'
            extra_opts.update({
                'format': format_spec,
                'concurrent_fragment_downloads': 8,
                'merge_output_format': 'mp4',
                'postprocessor_args': ['-threads', '2'],
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

    return convert_via_cloud_api(clean_url, target_type, quality_id, output_path)


# ==================== TIKTOK & DOUYIN EXTRACTOR ====================

def resolve_douyin_shortlink(url: str) -> tuple[str, str]:
    """Giải mã chuyển hướng shortlink Douyin (v.douyin.com) để lấy Canonical URL và Item ID."""
    clean_url = extract_url_from_text(url)
    final_url = clean_url
    item_id = ""

    if "v.douyin.com" in clean_url or "douyin.com" in clean_url:
        try:
            resp = requests.get(
                clean_url,
                headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"},
                allow_redirects=True,
                timeout=8
            )
            final_url = resp.url
        except Exception as e:
            print(f"Douyin redirect resolve error: {e}")

    id_match = re.search(r'/(?:video|note)/(\d+)', final_url)
    if id_match:
        item_id = id_match.group(1)
    elif re.search(r'^\d+$', clean_url.strip()):
        item_id = clean_url.strip()

    return final_url, item_id

def extract_douyin_media(raw_url: str) -> dict:
    """Trích xuất Video Không Logo, MP3 và Album ảnh từ Douyin (抖音)."""
    clean_url = extract_url_from_text(raw_url)
    if not clean_url:
        raise ValueError("Vui lòng nhập liên kết Douyin hợp lệ.")

    final_url, item_id = resolve_douyin_shortlink(clean_url)
    canonical_url = f"https://www.douyin.com/video/{item_id}" if item_id else final_url

    # Bước 1: Thử qua yt-dlp (hỗ trợ cookies.txt nếu có)
    cookies_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
    opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'http_headers': HEADERS
    }
    if os.path.exists(cookies_file):
        opts['cookiefile'] = cookies_file

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(canonical_url, download=False)
            if info:
                title = info.get("title") or info.get("description") or "Douyin Video"
                uploader = info.get("uploader") or info.get("creator") or "Douyin User"
                video_url = info.get("url") or ""
                thumbnail = info.get("thumbnail") or ""
                duration = info.get("duration", 0)
                duration_str = format_duration(duration) if duration else "HD"

                return {
                    "platform": "douyin",
                    "id": item_id or str(info.get("id") or int(time.time())),
                    "title": title,
                    "author_name": uploader,
                    "author_username": "douyin",
                    "author_avatar": thumbnail or "https://p16-sign-sg.tiktokcdn.com/tos-alisg-avt-0068/default.jpeg",
                    "cover": thumbnail,
                    "duration": duration,
                    "duration_str": duration_str,
                    "has_video": bool(video_url),
                    "video_url": video_url,
                    "has_music": bool(video_url),
                    "music_url": video_url,
                    "music_title": "Âm thanh gốc Douyin",
                    "music_author": uploader,
                    "has_images": False,
                    "photos": [],
                    "url": clean_url
                }
    except Exception as e:
        print(f"Douyin yt-dlp attempt: {e}")

    # Bước 2: Thử qua TikWM API với canonical URL
    try:
        target_for_api = canonical_url if item_id else clean_url
        resp = requests.post(
            "https://www.tikwm.com/api/",
            data={"url": target_for_api, "hd": 1},
            headers=HEADERS,
            timeout=10
        )
        if resp.status_code == 200:
            res_json = resp.json()
            if res_json.get("code") == 0:
                data = res_json.get("data", {})
                author = data.get("author", {})
                author_name = author.get("nickname") or author.get("unique_id") or "Douyin User"
                author_username = author.get("unique_id") or "user"
                author_avatar = author.get("avatar") or "https://p16-sign-sg.tiktokcdn.com/tos-alisg-avt-0068/default.jpeg"
                
                title = data.get("title") or "Douyin Media"
                ret_id = str(data.get("id") or item_id or int(time.time()))
                duration = data.get("duration", 0)
                duration_str = format_duration(duration) if duration else "HD"

                video_url = data.get("hdplay") or data.get("play") or ""
                wm_video_url = data.get("wmplay") or ""
                cover = data.get("cover") or data.get("origin_cover") or ""

                music_url = data.get("music") or ""
                music_info = data.get("music_info", {})
                music_title = music_info.get("title") or "Âm thanh gốc"
                music_author = music_info.get("author") or author_name

                raw_images = data.get("images") or []
                photos = []
                if raw_images and isinstance(raw_images, list):
                    for idx, img_url in enumerate(raw_images):
                        photos.append({
                            "index": idx + 1,
                            "type": "image",
                            "preview_url": img_url,
                            "download_url": img_url,
                            "alt": f"Photo {idx + 1}"
                        })

                has_images = len(photos) > 0
                has_video = bool(video_url) and not has_images
                has_music = bool(music_url)

                return {
                    "platform": "douyin",
                    "id": ret_id,
                    "title": title,
                    "author_name": author_name,
                    "author_username": author_username,
                    "author_avatar": author_avatar,
                    "cover": cover,
                    "duration": duration,
                    "duration_str": duration_str,
                    "has_video": has_video,
                    "video_url": video_url,
                    "video_wm_url": wm_video_url,
                    "has_music": has_music,
                    "music_url": music_url,
                    "music_title": music_title,
                    "music_author": music_author,
                    "has_images": has_images,
                    "photos": photos,
                    "url": clean_url
                }
    except Exception as e:
        print(f"Douyin TikWM error: {e}")

    raise ValueError("Không thể trích xuất Douyin này do cơ chế chống bot của ByteDance. Vui lòng mở Cài đặt (⚙️) và dán Cookies Douyin để tải mượt mà!")


def resolve_tiktok_shortlink(url: str) -> tuple[str, str]:
    """Giải mã chuyển hướng shortlink TikTok (vt.tiktok.com, vm.tiktok.com, m.tiktok.com)."""
    clean_url = extract_url_from_text(url)
    final_url = clean_url
    item_id = ""

    if any(s in clean_url.lower() for s in ["vt.tiktok.com", "vm.tiktok.com", "m.tiktok.com"]):
        try:
            resp = requests.get(
                clean_url,
                headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"},
                allow_redirects=True,
                timeout=8
            )
            final_url = resp.url
        except Exception as e:
            print(f"TikTok redirect resolve error: {e}")

    id_match = re.search(r'/(?:video|photo)/(\d+)', final_url)
    if id_match:
        item_id = id_match.group(1)
    elif re.search(r'^\d+$', clean_url.strip()):
        item_id = clean_url.strip()

    return final_url, item_id


def extract_tiktok_media(raw_url: str) -> dict:
    """Trích xuất Video Không Logo, MP3 và Album ảnh từ TikTok với cơ chế đa tầng."""
    clean_url = extract_url_from_text(raw_url)
    if not clean_url:
        raise ValueError("Vui lòng nhập liên kết TikTok hợp lệ.")

    final_url, item_id = resolve_tiktok_shortlink(clean_url)
    canonical_url = f"https://www.tiktok.com/@user/video/{item_id}" if item_id else final_url

    # Bước 1: Thử TikWM API với clean_url và canonical_url
    for target in [clean_url, canonical_url, final_url]:
        if not target:
            continue
        try:
            resp = requests.post(
                "https://www.tikwm.com/api/",
                data={"url": target, "hd": 1},
                headers=HEADERS,
                timeout=12
            )
            if resp.status_code == 200:
                res_json = resp.json()
                if res_json.get("code") == 0:
                    data = res_json.get("data", {})
                    
                    author = data.get("author", {})
                    author_name = author.get("nickname") or author.get("unique_id") or "TikTok User"
                    author_username = author.get("unique_id") or "user"
                    author_avatar = author.get("avatar") or "https://p16-sign-sg.tiktokcdn.com/tos-alisg-avt-0068/default.jpeg"
                    
                    title = data.get("title") or "TikTok Media"
                    ret_id = str(data.get("id") or item_id or int(time.time()))
                    duration = data.get("duration", 0)
                    duration_str = format_duration(duration) if duration else "HD"

                    video_url = data.get("hdplay") or data.get("play") or ""
                    wm_video_url = data.get("wmplay") or ""
                    cover = data.get("cover") or data.get("origin_cover") or ""

                    music_url = data.get("music") or ""
                    music_info = data.get("music_info", {})
                    music_title = music_info.get("title") or "Âm thanh gốc"
                    music_author = music_info.get("author") or author_name

                    raw_images = data.get("images") or []
                    photos = []
                    if raw_images and isinstance(raw_images, list):
                        for idx, img_url in enumerate(raw_images):
                            photos.append({
                                "index": idx + 1,
                                "type": "image",
                                "preview_url": img_url,
                                "download_url": img_url,
                                "alt": f"Photo {idx + 1}"
                            })

                    has_images = len(photos) > 0
                    has_video = bool(video_url) and not has_images
                    has_music = bool(music_url)

                    return {
                        "platform": "tiktok",
                        "id": ret_id,
                        "title": title,
                        "author_name": author_name,
                        "author_username": author_username,
                        "author_avatar": author_avatar,
                        "cover": cover,
                        "duration": duration,
                        "duration_str": duration_str,
                        "has_video": has_video,
                        "video_url": video_url,
                        "video_wm_url": wm_video_url,
                        "has_music": has_music,
                        "music_url": music_url,
                        "music_title": music_title,
                        "music_author": music_author,
                        "has_images": has_images,
                        "photos": photos,
                        "url": clean_url
                    }
        except Exception as e:
            print(f"TikTok TikWM attempt error for {target[:40]}: {e}")

    # Bước 2: Thử qua yt-dlp nếu có
    cookies_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
    opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'http_headers': HEADERS
    }
    if os.path.exists(cookies_file):
        opts['cookiefile'] = cookies_file

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            target_ydl = canonical_url if item_id else final_url
            info = ydl.extract_info(target_ydl, download=False)
            if info:
                title = info.get("title") or info.get("description") or "TikTok Video"
                uploader = info.get("uploader") or info.get("creator") or "TikTok User"
                video_url = info.get("url") or ""
                thumbnail = info.get("thumbnail") or ""
                duration = info.get("duration", 0)
                duration_str = format_duration(duration) if duration else "HD"

                return {
                    "platform": "tiktok",
                    "id": item_id or str(info.get("id") or int(time.time())),
                    "title": title,
                    "author_name": uploader,
                    "author_username": "user",
                    "author_avatar": thumbnail or "https://p16-sign-sg.tiktokcdn.com/tos-alisg-avt-0068/default.jpeg",
                    "cover": thumbnail,
                    "duration": duration,
                    "duration_str": duration_str,
                    "has_video": bool(video_url),
                    "video_url": video_url,
                    "has_music": bool(video_url),
                    "music_url": video_url,
                    "music_title": "Âm thanh gốc TikTok",
                    "music_author": uploader,
                    "has_images": False,
                    "photos": [],
                    "url": clean_url
                }
    except Exception as e:
        print(f"TikTok yt-dlp error: {e}")

    raise ValueError("Không thể trích xuất TikTok này. Video có thể đã bị xóa, đặt ở chế độ riêng tư hoặc yêu cầu đăng nhập!")


def extract_tiktok_douyin_media(raw_url: str) -> dict:
    """Điều phối trích xuất TikTok hoặc Douyin."""
    clean_url = extract_url_from_text(raw_url).lower()
    if any(d in clean_url for d in ["douyin.com", "iesdouyin.com"]):
        return extract_douyin_media(raw_url)
    return extract_tiktok_media(raw_url)


# ==================== FACEBOOK EXTRACTOR ====================

def resolve_facebook_shortlink(url: str) -> str:
    """Giải mã chuyển hướng shortlink Facebook (fb.watch, /share/v/, /share/r/, fb.com)."""
    clean_url = extract_url_from_text(url)
    if any(s in clean_url.lower() for s in ["fb.watch", "/share/v/", "/share/r/", "fb.com"]):
        try:
            resp = requests.get(
                clean_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"},
                allow_redirects=True,
                timeout=8
            )
            clean_url = resp.url
        except Exception as e:
            print(f"Facebook redirect resolve error: {e}")

    # Làm sạch các query tracking của Facebook
    clean_url = re.sub(r'[?&](?:mibextid|rdid|__cft__|__tn__|ref)=[^&]+', '', clean_url)
    return clean_url


def parse_facebook_html_direct(url: str, cookies_dict: dict = None) -> dict:
    """Bóc tách trực tiếp luồng stream HD/SD từ mã nguồn HTML Facebook."""
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
            "Referer": "https://www.facebook.com/"
        }
        resp = session.get(url, headers=headers, cookies=cookies_dict or {}, timeout=10)
        html = resp.text

        hd_url = None
        sd_url = None

        # 1. playable_url_quality_hd
        m_hd = re.search(r'["\']playable_url_quality_hd["\']\s*:\s*["\'](https?:\\?/\\?/[^"\']+)["\']', html)
        if m_hd:
            hd_url = m_hd.group(1).replace(r'\/', '/')

        # 2. playable_url (SD)
        m_sd = re.search(r'["\']playable_url["\']\s*:\s*["\'](https?:\\?/\\?/[^"\']+)["\']', html)
        if m_sd:
            sd_url = m_sd.group(1).replace(r'\/', '/')

        # 3. browser_native_hd_url / browser_native_sd_url
        if not hd_url:
            m_b_hd = re.search(r'["\']browser_native_hd_url["\']\s*:\s*["\'](https?:\\?/\\?/[^"\']+)["\']', html)
            if m_b_hd:
                hd_url = m_b_hd.group(1).replace(r'\/', '/')

        if not sd_url:
            m_b_sd = re.search(r'["\']browser_native_sd_url["\']\s*:\s*["\'](https?:\\?/\\?/[^"\']+)["\']', html)
            if m_b_sd:
                sd_url = m_b_sd.group(1).replace(r'\/', '/')

        # 4. og:video
        if not hd_url and not sd_url:
            m_og = re.search(r'<meta\s+property=["\']og:video["\']\s+content=["\'](https?://[^"\']+)["\']', html)
            if m_og:
                sd_url = m_og.group(1)

        title = "Facebook Video"
        m_title = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html)
        if m_title:
            title = m_title.group(1)

        thumbnail = ""
        m_thumb = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html)
        if m_thumb:
            thumbnail = m_thumb.group(1)

        qualities = []
        if hd_url:
            qualities.append({
                "url": hd_url,
                "resolution": "Bản HD Sắc Nét (1080p/720p)",
                "format_id": "hd"
            })
        if sd_url:
            qualities.append({
                "url": sd_url,
                "resolution": "Bản SD Tiêu Chuẩn (480p/360p)",
                "format_id": "sd"
            })

        best_url = hd_url or sd_url
        if best_url:
            return {
                "platform": "facebook",
                "id": str(int(time.time())),
                "title": title,
                "author_name": "Facebook Creator",
                "author_username": "facebook",
                "author_avatar": "https://z-m-static.xx.fbcdn.net/rsrc.php/v3/yq/r/c5H4h0d9n4F.png",
                "cover": thumbnail,
                "duration_str": "HD",
                "has_video": True,
                "video_url": best_url,
                "qualities": qualities,
                "has_music": True,
                "music_url": best_url,
                "music_title": "Âm thanh gốc",
                "music_author": "Facebook Creator",
                "has_images": False,
                "photos": [],
                "url": url
            }
    except Exception as e:
        print(f"Facebook HTML direct parse error: {e}")
    return None


def extract_facebook_media(raw_url: str) -> dict:
    """Trích xuất Video & Reels từ Facebook chất lượng HD / SD."""
    clean_url = extract_url_from_text(raw_url)
    if not clean_url:
        raise ValueError("Vui lòng nhập liên kết Facebook hợp lệ.")

    resolved_url = resolve_facebook_shortlink(clean_url)

    # Bước 1: Trích xuất qua yt-dlp (hỗ trợ cookies.txt)
    cookies_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
    opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'http_headers': HEADERS
    }
    if os.path.exists(cookies_file):
        opts['cookiefile'] = cookies_file

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(resolved_url, download=False)
            if info:
                if "entries" in info and info["entries"]:
                    info = info["entries"][0]

                title = info.get("title") or info.get("description") or "Facebook Video"
                uploader = info.get("uploader") or info.get("creator") or "Facebook User"
                thumbnail = info.get("thumbnail") or ""
                duration = info.get("duration", 0)
                duration_str = format_duration(duration) if duration else "HD"

                formats = info.get("formats", [])
                video_qualities = []
                best_video_url = info.get("url") or ""

                for f in formats:
                    f_url = f.get("url")
                    if not f_url:
                        continue
                    f_id = f.get("format_id", "")
                    f_note = f.get("format_note") or f.get("resolution") or f_id
                    
                    if f_id in ["hd", "sd"] or f.get("vcodec") != "none":
                        label = "Bản HD Sắc Nét (1080p/720p)" if f_id == "hd" else ("Bản SD Tiêu Chuẩn (480p/360p)" if f_id == "sd" else f"Chất lượng {f_note}")
                        video_qualities.append({
                            "url": f_url,
                            "resolution": label,
                            "format_id": f_id
                        })
                        if not best_video_url or f_id == "hd":
                            best_video_url = f_url

                if not video_qualities and best_video_url:
                    video_qualities.append({
                        "url": best_video_url,
                        "resolution": "Bản gốc MP4 HD",
                        "format_id": "best"
                    })

                item_id = str(info.get("id") or int(time.time()))

                return {
                    "platform": "facebook",
                    "id": item_id,
                    "title": title,
                    "author_name": uploader,
                    "author_username": "facebook",
                    "author_avatar": "https://z-m-static.xx.fbcdn.net/rsrc.php/v3/yq/r/c5H4h0d9n4F.png",
                    "cover": thumbnail,
                    "duration": duration,
                    "duration_str": duration_str,
                    "has_video": True,
                    "video_url": best_video_url,
                    "qualities": video_qualities,
                    "has_music": True,
                    "music_url": best_video_url,
                    "music_title": "Âm thanh gốc",
                    "music_author": uploader,
                    "has_images": False,
                    "photos": [],
                    "url": resolved_url
                }
    except Exception as e:
        print(f"Facebook yt-dlp error: {e}")

    # Bước 2: Thử bóc tách trực tiếp từ HTML
    direct_res = parse_facebook_html_direct(resolved_url)
    if direct_res:
        return direct_res

    raise ValueError("Không thể tải video Facebook này. Video có thể ở chế độ riêng tư, trong nhóm kín hoặc yêu cầu đăng nhập. Bạn có thể mở Cài đặt (⚙️) và dán Cookies Facebook để tải mượt mà!")


# ==================== INSTAGRAM EXTRACTOR ====================

def extract_instagram_media(raw_url: str) -> dict:
    """Trích xuất Ảnh, Reels, Video & Album Carousel từ Instagram."""
    clean_url = extract_url_from_text(raw_url)
    if not clean_url:
        raise ValueError("Vui lòng nhập liên kết Instagram hợp lệ.")

    # Trích xuất shortcode từ URL
    shortcode_match = re.search(r'instagram\.com/(?:p|reel|tv|stories)/([a-zA-Z0-9_-]+)', clean_url)
    shortcode = shortcode_match.group(1) if shortcode_match else str(int(time.time()))

    # Bước 1: Thử trích xuất qua yt-dlp
    opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'http_headers': HEADERS
    }
    cookies_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
    if os.path.exists(cookies_file):
        opts['cookiefile'] = cookies_file

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            if info:
                if "entries" in info and info["entries"]:
                    info = info["entries"][0]

                title = info.get("title") or info.get("description") or "Instagram Media"
                uploader = info.get("uploader") or info.get("channel") or "Instagram User"
                video_url = info.get("url") or ""
                thumbnail = info.get("thumbnail") or ""
                duration = info.get("duration", 0)
                duration_str = format_duration(duration) if duration else "HD"

                has_video = bool(video_url)
                photos = []
                if not has_video and thumbnail:
                    photos.append({
                        "index": 1,
                        "type": "image",
                        "preview_url": thumbnail,
                        "download_url": thumbnail,
                        "alt": "Instagram Photo"
                    })

                return {
                    "platform": "instagram",
                    "id": shortcode,
                    "title": title,
                    "author_name": uploader,
                    "author_username": uploader,
                    "author_avatar": "https://www.instagram.com/static/images/ico/favicon.ico/7016fd3039e1.ico",
                    "cover": thumbnail,
                    "duration": duration,
                    "duration_str": duration_str,
                    "has_video": has_video,
                    "video_url": video_url,
                    "has_music": has_video,
                    "music_url": video_url,
                    "music_title": "Âm thanh gốc",
                    "music_author": uploader,
                    "has_images": len(photos) > 0,
                    "photos": photos,
                    "url": clean_url
                }
    except Exception as e:
        print(f"Instagram yt-dlp error: {e}")

    # Bước 2: Thử qua Instaloader
    try:
        import instaloader
        L = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False
        )
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        uploader = post.owner_username or "Instagram Creator"
        caption = post.caption or "Instagram Post"
        is_video = post.is_video
        video_url = post.video_url if is_video else ""
        cover = post.url
        
        photos = []
        sidecar_nodes = list(post.get_sidecar_nodes())
        if sidecar_nodes:
            for idx, node in enumerate(sidecar_nodes):
                photos.append({
                    "index": idx + 1,
                    "type": "video" if node.is_video else "image",
                    "preview_url": node.display_url,
                    "download_url": node.video_url if node.is_video else node.display_url,
                    "alt": f"Slide {idx + 1}"
                })
        elif not is_video and cover:
            photos.append({
                "index": 1,
                "type": "image",
                "preview_url": cover,
                "download_url": cover,
                "alt": "Instagram Photo"
            })

        return {
            "platform": "instagram",
            "id": shortcode,
            "title": caption,
            "author_name": uploader,
            "author_username": uploader,
            "author_avatar": "https://www.instagram.com/static/images/ico/favicon.ico/7016fd3039e1.ico",
            "cover": cover,
            "duration_str": "HD",
            "has_video": is_video,
            "video_url": video_url,
            "has_music": is_video,
            "music_url": video_url,
            "music_title": "Âm thanh gốc",
            "music_author": uploader,
            "has_images": len(photos) > 0 and not is_video,
            "photos": photos,
            "url": clean_url
        }
    except Exception as e:
        print(f"Instaloader error: {e}")

    raise ValueError("Không thể trích xuất bài viết Instagram này. Bài viết có thể ở chế độ riêng tư hoặc yêu cầu đăng nhập.")


# ==================== MAIN DISPATCHER ====================

def extract_media(url: str) -> dict:
    """Tự động phân loại và trích xuất từ X/Twitter, YouTube, TikTok, Douyin, Facebook hoặc Instagram."""
    if not is_safe_url(url):
        clean_url = extract_url_from_text(url)
        if not is_safe_url(clean_url):
            raise ValueError("Liên kết không an toàn hoặc không hợp lệ. Vui lòng kiểm tra lại!")

    platform = detect_platform(url)
    
    if platform == "youtube":
        return extract_youtube_media(url)
    elif platform == "twitter":
        return extract_tweet_media(url)
    elif platform in ["tiktok", "douyin"]:
        return extract_tiktok_douyin_media(url)
    elif platform == "facebook":
        return extract_facebook_media(url)
    elif platform == "instagram":
        return extract_instagram_media(url)
    else:
        # Thử lần lượt các nền tảng
        for fn in [extract_tiktok_douyin_media, extract_facebook_media, extract_instagram_media, extract_tweet_media, extract_youtube_media]:
            try:
                return fn(url)
            except Exception:
                continue
        raise ValueError("Định dạng liên kết không được hỗ trợ! Hiện tại công cụ hỗ trợ: X (Twitter), YouTube, TikTok, Douyin, Facebook và Instagram.")

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
