import os
import sys
import json
import time
import subprocess
import webbrowser
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context, after_this_request
import requests

DOWNLOAD_THREADS = {}

from downloader import (
    extract_media, 
    download_file, 
    download_youtube_file, 
    optimize_image_url, 
    HEADERS,
    detect_platform,
    is_safe_url,
    extract_url_from_text
)

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_history_item(item):
    history = load_history()
    history = [h for h in history if h.get("id") != item.get("id")]
    history.insert(0, item)
    history = history[:50]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def sanitize_filename(filename: str) -> str:
    """Làm sạch tên file, chống tấn công Path Traversal và ký tự không hợp lệ."""
    clean = "".join(c for c in filename if c.isalnum() or c in (' ', '_', '-', '.')).strip()
    return clean.replace("..", "_")[:80] or "media_file"

@app.errorhandler(500)
def handle_500(e):
    return jsonify({"success": False, "error": "Lỗi máy chủ nội bộ. Vui lòng thử lại!"}), 500

@app.errorhandler(404)
def handle_404(e):
    return jsonify({"success": False, "error": "Không tìm thấy đường dẫn yêu cầu."}), 404

@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({"success": False, "error": str(e)}), 500

@app.route("/")
def index():
    return render_template("index.html")

@app.after_request
def add_security_headers(response):
    """Cung cấp các tiêu đề bảo mật cao cấp (CSP, HSTS, X-Content-Type-Options, etc.)."""
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://kit.fontawesome.com https://ka-f.fontawesome.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://ka-f.fontawesome.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com https://ka-f.fontawesome.com data:; "
        "img-src 'self' data: https: blob: http:; "
        "media-src 'self' blob: https: http:; "
        "connect-src 'self' https://ka-f.fontawesome.com https://cdnjs.cloudflare.com https://fonts.googleapis.com https: http:; "
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.route("/api/extract", methods=["POST"])
def api_extract():
    data = request.get_json(silent=True) or {}
    raw_url = data.get("url", "").strip()
    if not raw_url:
        return jsonify({"success": False, "error": "Vui lòng nhập đường link X (Twitter), YouTube, TikTok hoặc Douyin!"}), 400

    clean_url = extract_url_from_text(raw_url)
    if not clean_url or not is_safe_url(clean_url):
        return jsonify({"success": False, "error": "Định dạng liên kết không an toàn hoặc không hợp lệ!"}), 400

    try:
        media_info = extract_media(clean_url)
        return jsonify({"success": True, "data": media_info})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/download-server", methods=["POST"])
def api_download_server():
    """Tải trực tiếp vào thư mục downloads trên máy chủ."""
    data = request.get_json() or {}
    platform = data.get("platform", "twitter")
    timestamp = int(time.time())

    # 1. Xử lý tải YouTube (Video MP4 hoặc MP3)
    if platform == "youtube":
        yt_url = data.get("url")
        target_type = data.get("type", "video")
        quality_id = data.get("quality_id", "best")
        title = data.get("title", "YouTube_Media")
        clean_title = sanitize_filename(title)[:40]
        ext = "mp3" if target_type == "mp3" else "mp4"
        filename = f"YT_{clean_title}_{timestamp}.{ext}"
        filepath = os.path.join(DOWNLOADS_DIR, filename)

        try:
            final_path = download_youtube_file(yt_url, target_type, quality_id, filepath)
            saved_file = {
                "filename": os.path.basename(final_path),
                "filepath": final_path,
                "type": target_type,
                "size_bytes": os.path.getsize(final_path) if os.path.exists(final_path) else 0
            }
            save_history_item({
                "id": f"yt_{timestamp}",
                "platform": "youtube",
                "title": title,
                "type": target_type,
                "count": 1,
                "files": [saved_file],
                "downloaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            return jsonify({
                "success": True,
                "message": f"Đã tải và lưu {'Audio MP3' if target_type == 'mp3' else 'Video MP4'} thành công!",
                "files": [saved_file],
                "download_dir": DOWNLOADS_DIR
            })
        except Exception as e:
            return jsonify({"success": False, "error": f"Lỗi tải YouTube: {str(e)}"}), 500

    # 2. Xử lý tải TikTok & Douyin
    elif platform in ["tiktok", "douyin"]:
        items = data.get("items", [])
        title = data.get("title", "TikTok_Media")
        clean_title = sanitize_filename(title)[:40]
        author = sanitize_filename(data.get("author", "creator"))[:20]

        if not items:
            return jsonify({"success": False, "error": "Không có tệp nào để tải!"}), 400

        saved_files = []
        for idx, item in enumerate(items):
            url = item.get("url")
            mtype = item.get("type", "video")
            ext = item.get("ext", "mp4")
            if not url:
                continue

            filename = f"{platform.upper()}_{author}_{clean_title}_{idx+1}_{timestamp}.{ext}"
            filepath = os.path.join(DOWNLOADS_DIR, filename)

            try:
                download_file(url, filepath)
                saved_files.append({
                    "filename": filename,
                    "filepath": filepath,
                    "type": mtype,
                    "size_bytes": os.path.getsize(filepath)
                })
            except Exception as e:
                print(f"Lỗi tải {url}: {e}")

        if saved_files:
            return jsonify({
                "success": True,
                "message": f"Đã tải thành công {len(saved_files)} tệp {platform.capitalize()}!",
                "files": saved_files,
                "download_dir": DOWNLOADS_DIR
            })
        else:
            return jsonify({"success": False, "error": "Không thể tải được tệp nào. Vui lòng thử lại!"}), 500

    # 3. Xử lý tải X / Twitter
    items = data.get("items", [])
    tweet_id = data.get("tweet_id", "tweet")
    author = sanitize_filename(data.get("author", "unknown"))[:20]

    if not items:
        return jsonify({"success": False, "error": "Không có tệp nào để tải!"}), 400

    saved_files = []
    for idx, item in enumerate(items):
        url = item.get("url")
        mtype = item.get("type", "file")
        if not url:
            continue
        
        ext = "mp4" if mtype == "video" else ("gif" if mtype == "gif" else "png")
        if ".png" in url:
            ext = "png"
        elif ".mp4" in url:
            ext = "mp4"

        filename = f"X_{author}_{tweet_id}_{idx+1}_{timestamp}.{ext}"
        filepath = os.path.join(DOWNLOADS_DIR, filename)

        try:
            download_file(url, filepath)
            saved_files.append({
                "filename": filename,
                "filepath": filepath,
                "type": mtype,
                "size_bytes": os.path.getsize(filepath)
            })
        except Exception as e:
            print(f"Lỗi tải {url}: {e}")

    if saved_files:
        save_history_item({
            "id": f"{tweet_id}_{timestamp}",
            "platform": "twitter",
            "tweet_id": tweet_id,
            "author": author,
            "count": len(saved_files),
            "files": saved_files,
            "downloaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return jsonify({
            "success": True, 
            "message": f"Đã tải thành công {len(saved_files)} tệp vào thư mục Downloads!",
            "files": saved_files,
            "download_dir": DOWNLOADS_DIR
        })
    else:
        return jsonify({"success": False, "error": "Không thể tải được tệp nào. Vui lòng thử lại!"}), 500

@app.route("/api/download-zip", methods=["POST"])
def api_download_zip():
    """Tải nhiều ảnh/video cùng lúc, đóng gói thành 1 file ZIP trả về browser."""
    import zipfile, io
    from concurrent.futures import ThreadPoolExecutor, as_completed

    data = request.get_json() or {}
    items = data.get("items", [])
    zip_name = sanitize_filename(data.get("zip_name", "Media_Pro_Pack"))

    if not items:
        return jsonify({"success": False, "error": "Không có tệp nào để tải!"}), 400

    def fetch_one(item):
        url = item.get("url")
        name = sanitize_filename(item.get("name", "file"))
        ext = item.get("ext", "png")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20, stream=True)
            resp.raise_for_status()
            return (f"{name}.{ext}", resp.content)
        except Exception:
            return (f"{name}.{ext}", None)

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_STORED) as zf:
        with ThreadPoolExecutor(max_workers=min(len(items), 8)) as pool:
            futures = {pool.submit(fetch_one, item): item for item in items}
            for future in as_completed(futures):
                filename, content = future.result()
                if content:
                    zf.writestr(filename, content)

    zip_buf.seek(0)
    return Response(
        zip_buf.read(),
        mimetype="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}.zip"'}
    )

@app.route("/api/stream-file")
def api_stream_file():
    """Chuyển tiếp luồng tải trực tiếp về trình duyệt với đầy đủ header chống block."""
    file_url = request.args.get("url")
    custom_name = sanitize_filename(request.args.get("name", "media"))
    ext = sanitize_filename(request.args.get("ext", "png"))

    if not file_url or not is_safe_url(file_url):
        return "URL tệp không hợp lệ", 400

    filename = f"{custom_name}.{ext}"

    req_headers = dict(HEADERS)
    if "tiktok" in file_url or "muscdn" in file_url or "byteoversea" in file_url:
        req_headers["Referer"] = "https://www.tiktok.com/"
    elif "douyin" in file_url:
        req_headers["Referer"] = "https://www.douyin.com/"

    try:
        req = requests.get(file_url, headers=req_headers, stream=True, timeout=30)
        req.raise_for_status()
        
        content_type = req.headers.get("content-type", "application/octet-stream")
        response = Response(
            stream_with_context(req.iter_content(chunk_size=65536)),
            content_type=content_type
        )
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        return f"Lỗi tải luồng tệp: {str(e)}", 500

def write_progress(task_id, data):
    if not task_id:
        return
    try:
        p_path = os.path.join(DOWNLOADS_DIR, f"progress_{task_id}.json")
        with open(p_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass

def read_progress(task_id):
    if not task_id:
        return None
    p_path = os.path.join(DOWNLOADS_DIR, f"progress_{task_id}.json")
    if os.path.exists(p_path):
        try:
            with open(p_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def clean_progress(task_id):
    if not task_id:
        return
    p_path = os.path.join(DOWNLOADS_DIR, f"progress_{task_id}.json")
    if os.path.exists(p_path):
        try:
            os.remove(p_path)
        except Exception:
            pass

@app.route("/api/progress/<task_id>")
def api_get_progress(task_id):
    """Lấy tiến trình tải tệp thời gian thực."""
    info = read_progress(task_id)
    if not info:
        info = {
            "status": "started",
            "percent": 10,
            "speed": "Đang kết nối",
            "downloaded": "0 MB",
            "total": "...",
            "eta": "Đang phân tích..."
        }
    return jsonify(info)

@app.route("/api/start-download")
def api_start_download():
    """Khởi chạy download yt-dlp trong background thread, trả task_id ngay lập tức."""
    yt_url = request.args.get("url")
    target_type = request.args.get("type", "mp3")
    quality = request.args.get("quality", "320")
    title = request.args.get("title", "youtube_media")
    task_id = request.args.get("task_id", "")

    if not yt_url or not task_id:
        return jsonify({"success": False, "error": "Thiếu URL hoặc task_id"}), 400

    clean_title = sanitize_filename(title)[:40] or "youtube"
    ext = "mp3" if target_type == "mp3" else "mp4"
    temp_filename = f"dl_{task_id}.{ext}"
    temp_path = os.path.join(DOWNLOADS_DIR, temp_filename)

    write_progress(task_id, {
        "status": "started", "percent": 8,
        "speed": "Đang kết nối", "downloaded": "0 MB",
        "total": "Đang phân tích", "eta": "..."
    })

    def run_download():
        def on_progress(d):
            if d.get('status') == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                percent = int(downloaded / total * 100) if total > 0 else 15
                speed = d.get('speed') or 0
                speed_str = f"{speed / (1024*1024):.1f} MB/s" if speed else "N/A"
                eta = d.get('eta') or 0
                write_progress(task_id, {
                    "status": "downloading",
                    "percent": min(max(percent, 10), 94),
                    "speed": speed_str,
                    "downloaded": f"{downloaded / (1024*1024):.1f} MB",
                    "total": f"{total / (1024*1024):.1f} MB" if total else "N/A",
                    "eta": f"{eta}s" if eta else "Đang tính..."
                })
            elif d.get('status') == 'finished':
                write_progress(task_id, {
                    "status": "converting", "percent": 97,
                    "speed": "Đang nén", "downloaded": "Hoàn tất",
                    "total": "Đóng gói", "eta": "1s"
                })
        try:
            final_path = download_youtube_file(yt_url, target_type, quality, temp_path, progress_callback=on_progress)
            DOWNLOAD_THREADS[task_id] = {"status": "ready", "path": final_path, "ext": ext, "title": clean_title}
            write_progress(task_id, {
                "status": "completed", "percent": 100,
                "speed": "Hoàn tất", "downloaded": "100%",
                "total": "Sẵn sàng", "eta": "0s"
            })
        except Exception as e:
            DOWNLOAD_THREADS[task_id] = {"status": "error", "error": str(e)}
            write_progress(task_id, {
                "status": "error", "percent": 0,
                "speed": "Lỗi", "downloaded": "0 MB",
                "total": "0 MB", "eta": str(e)
            })

    t = threading.Thread(target=run_download, daemon=True)
    t.start()
    return jsonify({"success": True, "task_id": task_id})


@app.route("/api/stream-youtube")
def api_stream_youtube():
    """Gửi file YouTube đã tải xong về trình duyệt."""
    task_id = request.args.get("task_id", "")
    if not task_id:
        yt_url = request.args.get("url")
        target_type = request.args.get("type", "mp3")
        quality = request.args.get("quality", "320")
        title = request.args.get("title", "youtube_media")
        clean_title = sanitize_filename(title)[:40] or "youtube"
        ext = "mp3" if target_type == "mp3" else "mp4"
        temp_path = os.path.join(DOWNLOADS_DIR, f"sync_{int(time.time())}.{ext}")
        try:
            final_path = download_youtube_file(yt_url, target_type, quality, temp_path)
            return send_file(final_path, as_attachment=True, download_name=f"{clean_title}.{ext}")
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    info = DOWNLOAD_THREADS.get(task_id)
    if not info:
        for _ in range(600):
            time.sleep(0.5)
            info = DOWNLOAD_THREADS.get(task_id)
            if info:
                break

    if not info or info.get("status") == "error":
        err = (info or {}).get("error", "Download chưa hoàn tất hoặc bị lỗi.")
        return jsonify({"success": False, "error": err}), 500

    final_path = info["path"]
    ext = info["ext"]
    clean_title = info["title"]

    if not os.path.exists(final_path):
        return jsonify({"success": False, "error": "File không tồn tại."}), 404

    @after_this_request
    def cleanup(response):
        try:
            clean_progress(task_id)
            DOWNLOAD_THREADS.pop(task_id, None)
            if os.environ.get("RENDER") and os.path.exists(final_path):
                os.remove(final_path)
        except Exception:
            pass
        return response

    return send_file(final_path, as_attachment=True, download_name=f"{clean_title}.{ext}")


@app.route("/api/save-cookies", methods=["POST"])
def api_save_cookies():
    """Lưu cookies người dùng nhập từ bảng Tùy Chỉnh vào file cookies.txt."""
    data = request.get_json() or {}
    cookies_content = data.get("cookies", "").strip()
    cookies_path = os.path.join(BASE_DIR, "cookies.txt")
    
    try:
        if cookies_content:
            with open(cookies_path, "w", encoding="utf-8") as f:
                f.write(cookies_content)
            return jsonify({"success": True, "message": "Đã lưu Cookies thành công!"})
        else:
            if os.path.exists(cookies_path):
                os.remove(cookies_path)
            return jsonify({"success": True, "message": "Đã xóa Cookies thành công!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    is_render = os.environ.get("RENDER") is not None

    print("=" * 60)
    print("  🚀 Universal Media Pro Saver (X, YouTube, TikTok, Douyin) đang chạy...")
    print(f"  🌐 Cổng lắng nghe (Port): {port}")
    print("  📁 Thư mục lưu mặc định:", DOWNLOADS_DIR)
    print("=" * 60)
    
    if not is_render and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        threading.Thread(target=open_browser, daemon=True).start()

    app.run(host="0.0.0.0", port=port, debug=not is_render)
