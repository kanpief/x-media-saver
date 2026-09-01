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
from downloader import (
    extract_media, 
    download_file, 
    download_youtube_file, 
    optimize_image_url, 
    HEADERS,
    detect_platform
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

@app.route("/api/extract", methods=["POST"])
def api_extract():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"success": False, "error": "Vui lòng nhập đường link X (Twitter) hoặc YouTube!"}), 400

    try:
        media_info = extract_media(url)
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
        target_type = data.get("type", "video") # 'video' hoặc 'mp3'
        quality_id = data.get("quality_id", "best")
        title = data.get("title", "YouTube_Media")
        # Chuẩn hóa tên file
        clean_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).strip()[:40]
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

    # 2. Xử lý tải X / Twitter
    items = data.get("items", [])
    tweet_id = data.get("tweet_id", "tweet")
    author = data.get("author", "unknown")

    if not items:
        return jsonify({"success": False, "error": "Không có tệp nào để tải!"}), 400

    saved_files = []
    for idx, item in enumerate(items):
        url = item.get("url")
        mtype = item.get("type", "file")
        if not url:
            continue
        
        ext = "mp4" if mtype == "video" else ("gif" if mtype == "gif" else "jpg")
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

@app.route("/api/stream-file")
def api_stream_file():
    """Chuyển tiếp luồng tải trực tiếp về trình duyệt."""
    file_url = request.args.get("url")
    custom_name = request.args.get("name", "media")
    ext = request.args.get("ext", "jpg")

    if not file_url:
        return "Thiếu URL tệp", 400

    filename = f"{custom_name}.{ext}"

    req = requests.get(file_url, headers=HEADERS, stream=True)
    response = Response(
        stream_with_context(req.iter_content(chunk_size=65536)),
        content_type=req.headers.get("content-type", "application/octet-stream")
    )
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response

PROGRESS_REGISTRY = {}

@app.route("/api/progress/<task_id>")
def api_get_progress(task_id):
    """Lấy tiến trình tải tệp thời gian thực."""
    info = PROGRESS_REGISTRY.get(task_id, {
        "status": "idle",
        "percent": 0,
        "speed": "0 MB/s",
        "downloaded": "0 MB",
        "total": "0 MB",
        "eta": "Đang kết nối..."
    })
    return jsonify(info)

@app.route("/api/stream-youtube")
def api_stream_youtube():
    """Tải và stream YouTube Video / MP3 về trình duyệt qua Flask kèm theo dõi % thời gian thực."""
    yt_url = request.args.get("url")
    target_type = request.args.get("type", "mp3")
    quality = request.args.get("quality", "320")
    title = request.args.get("title", "youtube_media")
    task_id = request.args.get("task_id", "")

    if not yt_url:
        return "Thiếu URL YouTube", 400

    clean_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).strip()[:40] or "youtube"
    timestamp = int(time.time())
    ext = "mp3" if target_type == "mp3" else "mp4"
    temp_filename = f"temp_{clean_title}_{timestamp}.{ext}"
    temp_path = os.path.join(DOWNLOADS_DIR, temp_filename)

    def on_progress(d):
        if not task_id:
            return
        if d.get('status') == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            percent = int(downloaded / total * 100) if total > 0 else 0
            speed = d.get('speed') or 0
            speed_str = f"{speed / (1024*1024):.1f} MB/s" if speed else "N/A"
            eta = d.get('eta') or 0
            eta_str = f"{eta}s" if eta else "Đang tính..."
            PROGRESS_REGISTRY[task_id] = {
                "status": "downloading",
                "percent": min(percent, 95),
                "speed": speed_str,
                "downloaded": f"{downloaded / (1024*1024):.1f} MB",
                "total": f"{total / (1024*1024):.1f} MB" if total else "N/A",
                "eta": eta_str
            }
        elif d.get('status') == 'finished':
            PROGRESS_REGISTRY[task_id] = {
                "status": "converting",
                "percent": 98,
                "speed": "Đang nén",
                "downloaded": "Hoàn tất tải",
                "total": "Đóng gói tệp",
                "eta": "1s"
            }

    try:
        if task_id:
            PROGRESS_REGISTRY[task_id] = {
                "status": "started",
                "percent": 5,
                "speed": "Đang kết nối",
                "downloaded": "0 MB",
                "total": "Đang phân tích",
                "eta": "..."
            }

        final_path = download_youtube_file(yt_url, target_type, quality, temp_path, progress_callback=on_progress)
        
        if task_id:
            PROGRESS_REGISTRY[task_id] = {
                "status": "completed",
                "percent": 100,
                "speed": "Hoàn tất",
                "downloaded": "100%",
                "total": "Sẵn sàng",
                "eta": "0s"
            }

        @after_this_request
        def remove_temp(response):
            try:
                if os.path.exists(final_path):
                    if os.environ.get("RENDER"):
                        os.remove(final_path)
            except Exception:
                pass
            return response

        return send_file(
            final_path,
            as_attachment=True,
            download_name=f"{clean_title}.{ext}"
        )
    except Exception as e:
        if task_id:
            PROGRESS_REGISTRY[task_id] = {
                "status": "error",
                "percent": 0,
                "speed": "Lỗi",
                "downloaded": "0 MB",
                "total": "0 MB",
                "eta": str(e)
            }
        return f"Lỗi xử lý file: {str(e)}", 500



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

@app.route("/api/open-folder", methods=["POST"])
def api_open_folder():

    """Mở thư mục downloads trên Windows Explorer."""
    try:
        if os.environ.get("RENDER"):
            return jsonify({"success": False, "error": "Chức năng mở thư mục chỉ khả dụng khi chạy ứng dụng trên máy tính cá nhân!"}), 400
        
        if sys.platform == "win32":
            os.startfile(DOWNLOADS_DIR)
        elif sys.platform == "darwin":
            subprocess.run(["open", DOWNLOADS_DIR])
        else:
            subprocess.run(["xdg-open", DOWNLOADS_DIR])
        return jsonify({"success": True, "message": "Đã mở thư mục Downloads"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/history", methods=["GET", "DELETE"])
def api_history():
    if request.method == "DELETE":
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
        return jsonify({"success": True, "message": "Đã xóa lịch sử tải xuống"})
    return jsonify({"success": True, "history": load_history()})

def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    is_render = os.environ.get("RENDER") is not None

    print("=" * 60)
    print("  🚀 X & YouTube Media Pro Saver đang khởi chạy...")
    print(f"  🌐 Cổng lắng nghe (Port): {port}")
    print("  📁 Thư mục lưu mặc định:", DOWNLOADS_DIR)
    print("=" * 60)
    
    if not is_render and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        threading.Thread(target=open_browser, daemon=True).start()

    app.run(host="0.0.0.0", port=port, debug=not is_render)
