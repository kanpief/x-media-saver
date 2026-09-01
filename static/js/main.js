document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const form = document.getElementById("extract-form");
    const inputUrl = document.getElementById("tweet-url-input");
    const btnPaste = document.getElementById("btn-paste");
    const btnClear = document.getElementById("btn-clear");
    const btnSubmit = document.getElementById("btn-submit");
    const btnText = btnSubmit.querySelector(".btn-text");
    const btnLoader = btnSubmit.querySelector(".btn-loader");
    
    const skeleton = document.getElementById("skeleton-loading");
    const resultContainer = document.getElementById("result-container");
    const toastContainer = document.getElementById("toast-container");
    
    const btnOpenFolder = document.getElementById("btn-open-folder");
    const btnToggleHistory = document.getElementById("btn-toggle-history");
    const historyModal = document.getElementById("history-modal");
    const btnCloseHistory = document.getElementById("btn-close-history");
    const btnClearHistory = document.getElementById("btn-clear-history");
    const historyList = document.getElementById("history-list");

    const lightboxModal = document.getElementById("lightbox-modal");
    const lightboxImg = document.getElementById("lightbox-img");
    const lightboxClose = document.getElementById("lightbox-close");
    const lightboxDownloadBtn = document.getElementById("lightbox-download-btn");

    let currentTweetData = null;

    // Toast Notification System
    function showToast(message, type = "info", duration = 3500) {
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        
        let icon = "fa-circle-info";
        if (type === "success") icon = "fa-circle-check";
        if (type === "error") icon = "fa-triangle-exclamation";

        toast.innerHTML = `
            <i class="fa-solid ${icon}"></i>
            <span>${message}</span>
        `;
        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(15px) scale(0.9)";
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    // Input handlers
    inputUrl.addEventListener("input", () => {
        if (inputUrl.value.trim().length > 0) {
            btnClear.classList.remove("hidden");
        } else {
            btnClear.classList.add("hidden");
        }
    });

    btnClear.addEventListener("click", () => {
        inputUrl.value = "";
        btnClear.classList.add("hidden");
        inputUrl.focus();
    });

    btnPaste.addEventListener("click", async () => {
        try {
            const text = await navigator.clipboard.readText();
            if (text) {
                inputUrl.value = text.trim();
                btnClear.classList.remove("hidden");
                showToast("Đã dán liên kết từ bộ nhớ tạm!", "info", 2000);
                form.dispatchEvent(new Event("submit"));
            }
        } catch (err) {
            inputUrl.focus();
            showToast("Vui lòng nhấn Ctrl+V để dán liên kết.", "info", 2500);
        }
    });

    // Form Submit Handler
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const url = inputUrl.value.trim();
        if (!url) {
            showToast("Vui lòng nhập đường link bài viết X (Twitter)!", "error");
            return;
        }

        // Set Loading State
        btnSubmit.disabled = true;
        btnText.classList.add("hidden");
        btnLoader.classList.remove("hidden");
        resultContainer.classList.add("hidden");
        skeleton.classList.remove("hidden");

        try {
            const resp = await fetch("/api/extract", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ url })
            });
            const res = await resp.json();

            if (!res.success) {
                throw new Error(res.error || "Không thể trích xuất media từ bài viết này.");
            }

            currentTweetData = res.data;
            renderTweetResult(res.data);
            showToast("Trích xuất dữ liệu thành công!", "success");
        } catch (err) {
            showToast(err.message, "error", 5000);
        } finally {
            btnSubmit.disabled = false;
            btnText.classList.remove("hidden");
            btnLoader.classList.add("hidden");
            skeleton.classList.add("hidden");
        }
    });

    // Render Tweet Result
    function renderTweetResult(data) {
        const hasPhotos = data.photos && data.photos.length > 0;
        const hasVideos = data.videos && data.videos.length > 0;

        let mediaHtml = "";

        if (hasVideos) {
            const video = data.videos[0];
            const qualities = video.qualities || [];
            
            let qualityOptionsHtml = qualities.map((q, idx) => `
                <option value="${q.url}">${q.resolution || `Chất lượng ${idx+1}`}</option>
            `).join("");

            mediaHtml = `
                <div class="media-container video-wrapper">
                    <video id="player-video" controls poster="${video.preview_url || ''}">
                        <source src="${video.download_url}" type="video/mp4">
                        Trình duyệt của bạn không hỗ trợ thẻ video.
                    </video>
                </div>

                <div class="download-actions-card">
                    <div class="actions-top">
                        <div class="quality-select-wrapper">
                            <label for="select-video-quality"><i class="fa-solid fa-sliders"></i> Độ phân giải:</label>
                            <select id="select-video-quality" class="select-quality">
                                ${qualityOptionsHtml}
                            </select>
                        </div>
                        <div class="badge-info">
                            <span class="tweet-badge"><i class="fa-solid fa-film"></i> Video MP4 Không Nén</span>
                        </div>
                    </div>
                    <div class="actions-buttons">
                        <button id="btn-dl-video-server" class="btn btn-primary">
                            <i class="fa-solid fa-download"></i> Lưu vào máy tính
                        </button>
                        <a id="btn-dl-video-browser" href="/api/stream-file?url=${encodeURIComponent(video.download_url)}&name=X_${data.author_username}_${data.tweet_id}&ext=mp4" class="btn btn-secondary" target="_blank">
                            <i class="fa-solid fa-globe"></i> Tải qua trình duyệt
                        </a>
                    </div>
                </div>
            `;
        } else if (hasPhotos) {
            const count = data.photos.length;
            const gridClass = count === 1 ? "grid-1" : (count === 2 ? "grid-2" : (count === 3 ? "grid-3" : "grid-4"));

            let photoItems = data.photos.map((p, idx) => `
                <div class="media-item" data-orig="${p.download_url}" data-preview="${p.preview_url}">
                    <span class="media-badge-orig"><i class="fa-solid fa-expand"></i> Gốc :orig</span>
                    <img src="${p.preview_url}" alt="Photo ${idx+1}" loading="lazy">
                    <div class="media-overlay">
                        <div class="btn-preview-circle"><i class="fa-solid fa-magnifying-glass-plus"></i></div>
                    </div>
                </div>
            `).join("");

            mediaHtml = `
                <div class="media-container image-grid ${gridClass}">
                    ${photoItems}
                </div>

                <div class="download-actions-card">
                    <div class="actions-top">
                        <span class="tweet-badge"><i class="fa-solid fa-images"></i> Tìm thấy ${count} ảnh gốc sắc nét</span>
                    </div>
                    <div class="actions-buttons">
                        <button id="btn-dl-photos-server" class="btn btn-primary">
                            <i class="fa-solid fa-cloud-arrow-down"></i> Tải tất cả (${count} ảnh) vào máy
                        </button>
                        ${count === 1 ? `
                            <a href="/api/stream-file?url=${encodeURIComponent(data.photos[0].download_url)}&name=X_${data.author_username}_${data.tweet_id}&ext=jpg" class="btn btn-secondary" target="_blank">
                                <i class="fa-solid fa-globe"></i> Tải trực tiếp qua trình duyệt
                            </a>
                        ` : ''}
                    </div>
                </div>
            `;
        } else {
            mediaHtml = `<div class="p-4 text-center text-muted">Không tìm thấy ảnh hoặc video trong bài viết này.</div>`;
        }

        resultContainer.innerHTML = `
            <div class="result-card glass-panel">
                <!-- Tweet Author Header -->
                <div class="tweet-author-header">
                    <div class="author-profile">
                        <img class="author-avatar" src="${data.author_avatar || 'https://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png'}" alt="Avatar">
                        <div class="author-meta">
                            <h4>${escapeHtml(data.author_name)} <i class="fa-solid fa-circle-check verified-icon"></i></h4>
                            <span class="author-handle">@${escapeHtml(data.author_username || 'user')}</span>
                        </div>
                    </div>
                    <a href="https://x.com/i/status/${data.tweet_id}" target="_blank" class="btn btn-sm btn-secondary" title="Xem trên X">
                        <i class="fa-brands fa-x-twitter"></i> Xem bài viết
                    </a>
                </div>

                <!-- Tweet Text Content -->
                ${data.text ? `<p class="tweet-text">${formatTweetText(data.text)}</p>` : ''}

                <!-- Media Section -->
                ${mediaHtml}
            </div>
        `;

        resultContainer.classList.remove("hidden");
        attachResultEvents(data);
    }

    // Attach Event Listeners to Result Card Elements
    function attachResultEvents(data) {
        // Image Lightbox Triggers
        const mediaItems = resultContainer.querySelectorAll(".media-item");
        mediaItems.forEach(item => {
            item.addEventListener("click", () => {
                const origUrl = item.getAttribute("data-orig");
                lightboxImg.src = origUrl;
                lightboxDownloadBtn.href = `/api/stream-file?url=${encodeURIComponent(origUrl)}&name=X_${data.author_username}_orig&ext=jpg`;
                lightboxModal.classList.remove("hidden");
            });
        });

        // Video Quality Switcher
        const selectQuality = document.getElementById("select-video-quality");
        const videoPlayer = document.getElementById("player-video");
        const btnDlVideoBrowser = document.getElementById("btn-dl-video-browser");
        if (selectQuality && videoPlayer) {
            selectQuality.addEventListener("change", (e) => {
                const newUrl = e.target.value;
                const currentTime = videoPlayer.currentTime;
                const isPaused = videoPlayer.paused;
                videoPlayer.src = newUrl;
                videoPlayer.currentTime = currentTime;
                if (!isPaused) videoPlayer.play();
                
                if (btnDlVideoBrowser) {
                    btnDlVideoBrowser.href = `/api/stream-file?url=${encodeURIComponent(newUrl)}&name=X_${data.author_username}_${data.tweet_id}&ext=mp4`;
                }
            });
        }

        // Download Video To Server
        const btnDlVideoServer = document.getElementById("btn-dl-video-server");
        if (btnDlVideoServer) {
            btnDlVideoServer.addEventListener("click", async () => {
                const targetUrl = selectQuality ? selectQuality.value : data.videos[0].download_url;
                btnDlVideoServer.disabled = true;
                btnDlVideoServer.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Đang lưu...`;
                
                try {
                    const resp = await fetch("/api/download-server", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            items: [{ url: targetUrl, type: "video" }],
                            tweet_id: data.tweet_id,
                            author: data.author_username
                        })
                    });
                    const res = await resp.json();
                    if (res.success) {
                        showToast("Đã lưu video thành công vào thư mục Downloads!", "success");
                    } else {
                        showToast(res.error || "Lỗi khi lưu video.", "error");
                    }
                } catch (err) {
                    showToast(err.message, "error");
                } finally {
                    btnDlVideoServer.disabled = false;
                    btnDlVideoServer.innerHTML = `<i class="fa-solid fa-download"></i> Lưu vào máy tính`;
                }
            });
        }

        // Download Photos To Server
        const btnDlPhotosServer = document.getElementById("btn-dl-photos-server");
        if (btnDlPhotosServer) {
            btnDlPhotosServer.addEventListener("click", async () => {
                btnDlPhotosServer.disabled = true;
                btnDlPhotosServer.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Đang tải ${data.photos.length} ảnh...`;

                const items = data.photos.map(p => ({ url: p.download_url, type: "image" }));
                try {
                    const resp = await fetch("/api/download-server", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            items: items,
                            tweet_id: data.tweet_id,
                            author: data.author_username
                        })
                    });
                    const res = await resp.json();
                    if (res.success) {
                        showToast(`Đã lưu toàn bộ ${res.files.length} ảnh gốc vào thư mục Downloads!`, "success");
                    } else {
                        showToast(res.error || "Lỗi khi tải ảnh.", "error");
                    }
                } catch (err) {
                    showToast(err.message, "error");
                } finally {
                    btnDlPhotosServer.disabled = false;
                    btnDlPhotosServer.innerHTML = `<i class="fa-solid fa-cloud-arrow-down"></i> Tải tất cả (${data.photos.length} ảnh) vào máy`;
                }
            });
        }
    }

    // Open Downloads Folder
    btnOpenFolder.addEventListener("click", async () => {
        try {
            const resp = await fetch("/api/open-folder", { method: "POST" });
            const res = await resp.json();
            if (res.success) {
                showToast("Đang mở thư mục lưu trữ...", "info");
            } else {
                showToast("Không thể mở thư mục: " + res.error, "error");
            }
        } catch (err) {
            showToast("Lỗi mở thư mục.", "error");
        }
    });

    // History Modal Handlers
    btnToggleHistory.addEventListener("click", async () => {
        historyModal.classList.remove("hidden");
        loadHistory();
    });

    btnCloseHistory.addEventListener("click", () => {
        historyModal.classList.add("hidden");
    });

    historyModal.addEventListener("click", (e) => {
        if (e.target === historyModal) historyModal.classList.add("hidden");
    });

    btnClearHistory.addEventListener("click", async () => {
        if (!confirm("Bạn có chắc chắn muốn xóa toàn bộ lịch sử tải xuống?")) return;
        try {
            await fetch("/api/history", { method: "DELETE" });
            showToast("Đã xóa lịch sử!", "info");
            loadHistory();
        } catch (err) {
            showToast("Lỗi xóa lịch sử.", "error");
        }
    });

    async function loadHistory() {
        historyList.innerHTML = `<div class="text-center text-muted p-4"><i class="fa-solid fa-spinner fa-spin"></i> Đang tải...</div>`;
        try {
            const resp = await fetch("/api/history");
            const res = await resp.json();
            const history = res.history || [];
            
            if (history.length === 0) {
                historyList.innerHTML = `<div class="text-center text-muted p-4">Chưa có lịch sử tải xuống nào.</div>`;
                return;
            }

            historyList.innerHTML = history.map(item => `
                <div class="history-item">
                    <div class="history-meta">
                        <h5>@${escapeHtml(item.author || 'User')} - ID: ${item.tweet_id}</h5>
                        <p>${item.count} tệp • ${item.downloaded_at}</p>
                    </div>
                    <button class="btn btn-sm btn-secondary" onclick="openExplorer()">
                        <i class="fa-solid fa-folder"></i> Xem
                    </button>
                </div>
            `).join("");
        } catch (err) {
            historyList.innerHTML = `<div class="text-danger p-4">Không thể tải danh sách lịch sử.</div>`;
        }
    }

    window.openExplorer = () => {
        fetch("/api/open-folder", { method: "POST" });
    };

    // Lightbox Close Handlers
    lightboxClose.addEventListener("click", () => {
        lightboxModal.classList.add("hidden");
    });
    lightboxModal.addEventListener("click", (e) => {
        if (e.target === lightboxModal) lightboxModal.classList.add("hidden");
    });

    // Helper Functions
    function escapeHtml(str) {
        if (!str) return "";
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }

    function formatTweetText(text) {
        if (!text) return "";
        let escaped = escapeHtml(text);
        // Hashtags
        escaped = escaped.replace(/(#[a-zA-Z0-9_\u00c0-\u1ef9]+)/g, '<span style="color: #60a5fa;">$1</span>');
        // Mentions
        escaped = escaped.replace(/(@[a-zA-Z0-9_]+)/g, '<span style="color: #a78bfa;">$1</span>');
        // Links
        escaped = escaped.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" style="color: #38bdf8; text-decoration: underline;">$1</a>');
        return escaped;
    }
});
