import os
import re
import json
import math
import requests
import yt_dlp
from urllib.parse import urlparse, parse_qs

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
}

def extract_tweet_id(url: str) -> str:
    """Trích xuất Tweet ID từ các dạng link X / Twitter khác nhau."""
    if not url:
        return ""
    # Các dạng: x.com/user/status/12345, twitter.com/i/web/status/12345, fixupx, vxtwitter, fxtwitter
    match = re.search(r'(?:twitter\.com|x\.com|vxtwitter\.com|fxtwitter\.com|fixupx\.com)/[^/]+/status/(\d+)', url)
    if match:
        return match.group(1)
    
    # Dạng link rút gọn hoặc chỉ chứa /status/12345
    match_status = re.search(r'/status/(\d+)', url)
    if match_status:
        return match_status.group(1)

    # Nếu người dùng chỉ dán trực tiếp ID
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
        # Xóa extension suffix như :large, :small, :medium
        path = re.sub(r':(large|medium|small|thumb|\d+x\d+)$', '', path)
        return f"{parsed.scheme}://{parsed.netloc}{path}:orig"
    
    return img_url

def compute_syndication_token(tweet_id_str: str) -> str:
    try:
        tweet_id = int(tweet_id_str)
        # Token formula fallback
        return "5"
    except Exception:
        return "5"

def extract_via_syndication(tweet_id: str) -> dict:
    """Lấy thông tin và media qua CDN Syndication API của Twitter."""
    token = compute_syndication_token(tweet_id)
    url = f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&token={token}"
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
    # Thay avatar sang kích thước nét 400x400
    if author_avatar:
        author_avatar = author_avatar.replace("_normal.", "_400x400.")
    text = data.get("text", "")
    created_at = data.get("created_at", "")

    photos = []
    videos = []

    # Xử lý Photos
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

    # Xử lý Video block
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

    # Xử lý mediaDetails nếu photos/videos trống
    if not photos and not videos and "mediaDetails" in data:
        for media in data["mediaDetails"]:
            mtype = media.get("type")
            if mtype == "photo":
                raw_url = media.get("media_url_https", "")
                photos.append({
                    "type": "image",
                    "preview_url": raw_url,
                    "download_url": optimize_image_url(raw_url),
                })
            elif mtype in ["video", "animated_gif"]:
                v_info = media.get("video_info", {})
                variants = v_info.get("variants", [])
                mp4s = [v for v in variants if v.get("content_type") == "video/mp4"]
                mp4s.sort(key=lambda x: x.get("bitrate", 0), reverse=True)
                if mp4s:
                    quality_list = [{"url": v.get("url"), "resolution": f"MP4 ({v.get('bitrate', 0)//1000}kbps)"} for v in mp4s]
                    videos.append({
                        "type": "video" if mtype == "video" else "gif",
                        "preview_url": media.get("media_url_https", ""),
                        "download_url": mp4s[0].get("url"),
                        "qualities": quality_list
                    })

    if photos or videos:
        return {
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
    """Trích xuất qua vxTwitter API (rất ổn định cho cả ảnh và video)."""
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
    elif "mediaURLs" in data and data["mediaURLs"]:
        for raw_url in data["mediaURLs"]:
            if ".mp4" in raw_url:
                videos.append({
                    "type": "video",
                    "preview_url": "",
                    "download_url": raw_url,
                    "qualities": [{"url": raw_url, "resolution": "Bản gốc Full HD (Highest)"}]
                })
            else:
                photos.append({
                    "type": "image",
                    "preview_url": raw_url,
                    "download_url": optimize_image_url(raw_url)
                })

    if photos or videos:
        return {
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

def extract_via_ytdlp(tweet_url: str) -> dict:
    """Dự phòng cuối cùng qua yt-dlp."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(tweet_url, download=False)
            if not info:
                return None
            
            formats = info.get('formats', [])
            mp4_formats = [f for f in formats if f.get('ext') == 'mp4' or f.get('vcodec') != 'none']
            videos = []
            
            if mp4_formats:
                mp4_formats.sort(key=lambda x: (x.get('height') or 0, x.get('tbr') or 0), reverse=True)
                quality_list = []
                for f in mp4_formats:
                    res = f.get('format_note') or f"{f.get('height', 'HD')}p"
                    quality_list.append({
                        "url": f.get('url'),
                        "resolution": f"MP4 - {res}"
                    })
                videos.append({
                    "type": "video",
                    "preview_url": info.get('thumbnail', ''),
                    "download_url": mp4_formats[0].get('url'),
                    "qualities": quality_list
                })

            if videos:
                return {
                    "tweet_id": info.get('id', ''),
                    "author_name": info.get('uploader', 'X User'),
                    "author_username": info.get('uploader_id', ''),
                    "author_avatar": "",
                    "text": info.get('description', info.get('title', '')),
                    "created_at": info.get('upload_date', ''),
                    "photos": [],
                    "videos": videos,
                    "source": "yt-dlp"
                }
        except Exception:
            return None
    return None

def extract_tweet_media(url_or_id: str) -> dict:
    """Hàm tổng hợp kiểm tra trích xuất media qua nhiều phương thức."""
    tweet_id = extract_tweet_id(url_or_id)
    if not tweet_id:
        raise ValueError("Không tìm thấy Tweet ID hợp lệ trong liên kết. Vui lòng kiểm tra lại liên kết.")

    # 1. Thử Syndication API
    try:
        data = extract_via_syndication(tweet_id)
        if data and (data["photos"] or data["videos"]):
            return data
    except Exception as e:
        print(f"Syndication extraction error: {e}")

    # 2. Thử VxTwitter API
    try:
        data = extract_via_vxtwitter(tweet_id)
        if data and (data["photos"] or data["videos"]):
            return data
    except Exception as e:
        print(f"VxTwitter extraction error: {e}")

    # 3. Thử yt-dlp
    try:
        tweet_url = f"https://x.com/i/status/{tweet_id}"
        data = extract_via_ytdlp(tweet_url)
        if data and (data["photos"] or data["videos"]):
            return data
    except Exception as e:
        print(f"yt-dlp extraction error: {e}")

    raise ValueError("Không tìm thấy ảnh hoặc video trong bài viết này, hoặc bài viết đang ở chế độ riêng tư.")

def download_file(url: str, save_path: str, chunk_size: int = 65536) -> str:
    """Tải một file từ URL và lưu vào đĩa theo chunk, kèm headers."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    resp = requests.get(url, headers=HEADERS, stream=True, timeout=30)
    resp.raise_for_status()
    with open(save_path, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)
    return save_path
