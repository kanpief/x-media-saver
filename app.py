import os
import sys
import json
import time
import subprocess
import webbrowser
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context
import requests
from downloader import extract_tweet_media, download_file, optimize_image_url, HEADERS

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
    # Tránh trùng lặp id nếu vừa thêm
    history = [h for h in history if h.get("id") != item.get("id")]
    history.insert(0, item)
    history = history[:50]  # Giữ tối đa 50 mục gần nhất
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/extract", methods=["POST"])
def api_extract():
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"success": False, "error": "Vui lòng nhập đường link bài viết X (Twitter)!"}), 400

    try:
        media_info = extract_tweet_media(url)
        return jsonify({"success": True, "data": media_info})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/download-server", methods=["POST"])
def api_download_server():
    """Tải trực tiếp vào thư mục downloads trên máy tính."""
    data = request.get_json() or {}
    items = data.get("items", [])
    tweet_id = data.get("tweet_id", "tweet")
    author = data.get("author", "unknown")

    if not items:
        return jsonify({"success": False, "error": "Không có tệp nào để tải!"}), 400

    saved_files = []
    timestamp = int(time.time())

    for idx, item in enumerate(items):
        url = item.get("url")
        mtype = item.get("type", "file")
        if not url:
            continue
        
        # Đặt tên tệp chuẩn hóa
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
        # Lưu vào lịch sử
        save_history_item({
            "id": f"{tweet_id}_{timestamp}",
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
    """Chuyển tiếp luồng tải về trình duyệt để lưu về máy qua download manager của trình duyệt."""
    file_url = request.args.get("url")
    custom_name = request.args.get("name", "twitter_media")
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
    print("  🚀 X/Twitter Media Downloader đang khởi chạy...")
    print(f"  🌐 Cổng lắng nghe (Port): {port}")
    print("  📁 Thư mục lưu mặc định:", DOWNLOADS_DIR)
    print("=" * 60)
    
    # Tự động mở trình duyệt nếu chạy offline trên máy cá nhân
    if not is_render and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        threading.Thread(target=open_browser, daemon=True).start()

    app.run(host="0.0.0.0", port=port, debug=not is_render)

