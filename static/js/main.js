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
    
    const tabBtns = document.querySelectorAll(".tab-btn");
    const btnOpenFolder = document.getElementById("btn-open-folder");
    const btnToggleHistory = document.getElementById("btn-toggle-history");
    const historyModal = document.getElementById("history-modal");
    const btnCloseHistory = document.getElementById("btn-close-history");
    const btnClearHistory = document.getElementById("btn-clear-history");
    const historyList = document.getElementById("history-list");

    // Settings Modal Elements
    const btnToggleSettings = document.getElementById("btn-toggle-settings");
    const settingsModal = document.getElementById("settings-modal");
    const btnCloseSettings = document.getElementById("btn-close-settings");
    const settingDefaultMp3 = document.getElementById("setting-default-mp3");
    const settingDefaultVideo = document.getElementById("setting-default-video");
    const settingAutoExtract = document.getElementById("setting-auto-extract");
    const settingCookiesInput = document.getElementById("setting-cookies-input");
    const btnSaveCookies = document.getElementById("btn-save-cookies");

    const lightboxModal = document.getElementById("lightbox-modal");
    const lightboxImg = document.getElementById("lightbox-img");
    const lightboxClose = document.getElementById("lightbox-close");
    const lightboxDownloadBtn = document.getElementById("lightbox-download-btn");

    let currentMediaData = null;
    let selectedYtMode = "mp3";

    // Load Settings from LocalStorage
    function loadSettings() {
        const defaultMp3 = localStorage.getItem("setting_default_mp3") || "320";
        const defaultVideo = localStorage.getItem("setting_default_video") || "best";
        const autoExtract = localStorage.getItem("setting_auto_extract") !== "false";

        if (settingDefaultMp3) settingDefaultMp3.value = defaultMp3;
        if (settingDefaultVideo) settingDefaultVideo.value = defaultVideo;
        if (settingAutoExtract) settingAutoExtract.checked = autoExtract;
    }
    loadSettings();

    // Save Settings
    if (settingDefaultMp3) {
        settingDefaultMp3.addEventListener("change", () => {
            localStorage.setItem("setting_default_mp3", settingDefaultMp3.value);
            showToast("Đã cập nhật chất lượng MP3 mặc định!", "success", 2000);
        });
    }

    if (settingDefaultVideo) {
        settingDefaultVideo.addEventListener("change", () => {
            localStorage.setItem("setting_default_video", settingDefaultVideo.value);
            showToast("Đã cập nhật độ phân giải Video mặc định!", "success", 2000);
        });
    }

    if (settingAutoExtract) {
        settingAutoExtract.addEventListener("change", () => {
            localStorage.setItem("setting_auto_extract", settingAutoExtract.checked);
            showToast(settingAutoExtract.checked ? "Đã bật tự động phân tích!" : "Đã tắt tự động phân tích!", "info", 2000);
        });
    }

    // Save Cookies to Server
    if (btnSaveCookies) {
        btnSaveCookies.addEventListener("click", async () => {
            const cookiesText = settingCookiesInput.value.trim();
            btnSaveCookies.disabled = true;
            btnSaveCookies.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Đang lưu...`;

            try {
                const resp = await fetch("/api/save-cookies", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ cookies: cookiesText })
                });
                const res = await safeJson(resp);
                if (res.success) {
                    showToast(res.message || "Đã lưu Cookies!", "success");
                } else {
                    showToast(res.error || "Lỗi lưu cookies", "error");
                }

            } catch (err) {
                showToast("Lỗi kết nối máy chủ", "error");
            } finally {
                btnSaveCookies.disabled = false;
                btnSaveCookies.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> Lưu Cookies`;
            }
        });
    }

    // Settings Modal Toggle
    if (btnToggleSettings) {
        btnToggleSettings.addEventListener("click", () => {
            settingsModal.classList.remove("hidden");
        });
    }

    if (btnCloseSettings) {
        btnCloseSettings.addEventListener("click", () => {
            settingsModal.classList.add("hidden");
        });
    }

    settingsModal.addEventListener("click", (e) => {
        if (e.target === settingsModal) settingsModal.classList.add("hidden");
    });

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

    // Tab Switching
    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            tabBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            const platform = btn.dataset.platform;
            if (platform === "youtube") {
                inputUrl.placeholder = "Dán link YouTube / Shorts vào đây... vd: https://youtu.be/...";
            } else if (platform === "twitter") {
                inputUrl.placeholder = "Dán link X (Twitter) vào đây... vd: https://x.com/user/status/...";
            } else {
                inputUrl.placeholder = "Dán link X (Twitter) hoặc YouTube / Shorts vào đây...";
            }
            inputUrl.focus();
        });
    });

    // Auto-switch tab based on input URL
    inputUrl.addEventListener("input", () => {
        const val = inputUrl.value.trim().toLowerCase();
        if (val.length > 0) {
            btnClear.classList.remove("hidden");
        } else {
            btnClear.classList.add("hidden");
        }

        if (val.includes("youtube.com") || val.includes("youtu.be")) {
            switchActiveTab("youtube");
        } else if (val.includes("twitter.com") || val.includes("x.com") || val.includes("vxtwitter.com")) {
            switchActiveTab("twitter");
        }
    });

    function switchActiveTab(platform) {
        tabBtns.forEach(btn => {
            if (btn.dataset.platform === platform) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
        });
    }

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
                showToast("Đã dán liên kết!", "info", 1800);
                
                const val = inputUrl.value.toLowerCase();
                if (val.includes("youtube.com") || val.includes("youtu.be")) {
                    switchActiveTab("youtube");
                } else if (val.includes("twitter.com") || val.includes("x.com")) {
                    switchActiveTab("twitter");
                }

                // Check Auto Extract setting
                const autoExtract = localStorage.getItem("setting_auto_extract") !== "false";
                if (autoExtract) {
                    form.dispatchEvent(new Event("submit"));
                }
            }
        } catch (err) {
            inputUrl.focus();
            showToast("Vui lòng nhấn Ctrl+V để dán liên kết.", "info", 2500);
        }
    });

    // Safe JSON parser to prevent "Unexpected token <"
    async function safeJson(resp) {
        const text = await resp.text();
        try {
            return JSON.parse(text);
        } catch (e) {
            if (resp.status >= 500) {
                throw new Error("Máy chủ đang khởi động hoặc xử lý quá tải. Vui lòng thử lại sau giây lát!");
            } else if (resp.status === 404) {
                throw new Error("Không tìm thấy đường dẫn xử lý trên máy chủ.");
            }
            throw new Error("Không thể xử lý phản hồi từ máy chủ. Vui lòng thử lại!");
        }
    }

    // Form Submit Handler
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const url = inputUrl.value.trim();
        if (!url) {
            showToast("Vui lòng nhập đường link bài viết X hoặc video YouTube!", "error");
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
            const res = await safeJson(resp);

            if (!res.success) {
                throw new Error(res.error || "Không thể trích xuất dữ liệu từ liên kết này.");
            }

            currentMediaData = res.data;
            if (res.data.platform === "youtube") {
                renderYouTubeResult(res.data);
            } else {
                renderTwitterResult(res.data);
            }
            showToast("Trích xuất thông tin thành công!", "success");
        } catch (err) {
            showToast(err.message, "error", 5000);
        } finally {
            btnSubmit.disabled = false;
            btnText.classList.remove("hidden");
            btnLoader.classList.add("hidden");
            skeleton.classList.add("hidden");
        }
    });


    // Render YouTube Result
    function renderYouTubeResult(data) {
        selectedYtMode = "mp3";
        const savedDefaultMp3 = localStorage.getItem("setting_default_mp3") || "320";

        resultContainer.innerHTML = `
            <div class="result-card glass-panel luxury-border">
                <!-- Channel Info Header -->
                <div class="tweet-author-header">
                    <div class="author-profile">
                        <div class="channel-avatar-icon">
                            <i class="fa-brands fa-youtube"></i>
                        </div>
                        <div class="author-meta">
                            <h4>${escapeHtml(data.uploader)} <i class="fa-solid fa-circle-check verified-icon"></i></h4>
                            <span class="author-handle"><i class="fa-solid fa-eye"></i> ${data.view_count} lượt xem</span>
                        </div>
                    </div>
                    <a href="${data.url}" target="_blank" class="btn btn-sm btn-secondary" title="Xem trên YouTube">
                        <i class="fa-brands fa-youtube"></i> Mở YouTube
                    </a>
                </div>

                <!-- Video Title -->
                <p class="tweet-text" style="font-weight: 700; font-size: 16px;">${escapeHtml(data.title)}</p>

                <!-- Media Preview -->
                <div class="yt-media-preview">
                    <img class="yt-thumbnail-img" src="${data.thumbnail}" alt="Thumbnail">
                    <span class="yt-duration-badge"><i class="fa-solid fa-clock"></i> ${data.duration_str}</span>
                </div>

                <!-- Download & Conversion Actions Card -->
                <div class="download-actions-card">
                    <!-- Format Switcher -->
                    <div class="format-switch-container">
                        <button type="button" class="format-tab-btn active" data-mode="mp3">
                            <i class="fa-solid fa-music"></i> Chuyển qua Âm Thanh MP3
                        </button>
                        <button type="button" class="format-tab-btn" data-mode="video">
                            <i class="fa-solid fa-film"></i> Tải Video MP4
                        </button>
                    </div>

                    <!-- Quality Selectors -->
                    <div class="actions-top">
                        <div class="quality-select-wrapper" id="yt-quality-box">
                            <label for="select-yt-quality" id="yt-quality-label"><i class="fa-solid fa-sliders"></i> Chất lượng MP3:</label>
                            <select id="select-yt-quality" class="select-quality">
                                ${data.audio_qualities.map(a => `<option value="${a.id}" ${a.id === savedDefaultMp3 ? 'selected' : ''}>${a.label}</option>`).join("")}
                            </select>
                        </div>
                        <div class="badge-info">
                            <span id="yt-badge-display" class="tweet-badge mp3-badge"><i class="fa-solid fa-bolt"></i> Âm Thanh Chuẩn 320kbps</span>
                        </div>
                    </div>

                    <!-- Action Buttons -->
                    <div class="actions-buttons">
                        <button id="btn-yt-download-server" class="btn btn-music">
                            <i class="fa-solid fa-cloud-arrow-down"></i> <span id="txt-yt-server-btn">Lưu MP3 vào máy tính</span>
                        </button>
                        <a id="btn-yt-download-browser" href="/api/stream-youtube?url=${encodeURIComponent(data.url)}&type=mp3&quality=${savedDefaultMp3}&title=${encodeURIComponent(data.title)}" class="btn btn-secondary" target="_blank">
                            <i class="fa-solid fa-globe"></i> <span id="txt-yt-browser-btn">Tải MP3 qua trình duyệt</span>
                        </a>
                    </div>
                </div>
            </div>
        `;

        resultContainer.classList.remove("hidden");
        attachYouTubeEvents(data);
    }

    function attachYouTubeEvents(data) {
        const formatTabs = resultContainer.querySelectorAll(".format-tab-btn");
        const selectQuality = document.getElementById("select-yt-quality");
        const qualityLabel = document.getElementById("yt-quality-label");
        const badgeDisplay = document.getElementById("yt-badge-display");
        const btnServer = document.getElementById("btn-yt-download-server");
        const btnBrowser = document.getElementById("btn-yt-download-browser");
        const txtServerBtn = document.getElementById("txt-yt-server-btn");
        const txtBrowserBtn = document.getElementById("txt-yt-browser-btn");

        formatTabs.forEach(tab => {
            tab.addEventListener("click", () => {
                formatTabs.forEach(t => t.classList.remove("active"));
                tab.classList.add("active");
                selectedYtMode = tab.dataset.mode;

                if (selectedYtMode === "mp3") {
                    const savedDefaultMp3 = localStorage.getItem("setting_default_mp3") || "320";
                    qualityLabel.innerHTML = `<i class="fa-solid fa-sliders"></i> Chất lượng MP3:`;
                    selectQuality.innerHTML = data.audio_qualities.map(a => `<option value="${a.id}" ${a.id === savedDefaultMp3 ? 'selected' : ''}>${a.label}</option>`).join("");
                    badgeDisplay.className = "tweet-badge mp3-badge";
                    badgeDisplay.innerHTML = `<i class="fa-solid fa-music"></i> Âm Thanh Chuẩn 320kbps`;
                    btnServer.className = "btn btn-music";
                    txtServerBtn.innerText = "Lưu MP3 vào máy tính";
                    txtBrowserBtn.innerText = "Tải MP3 qua trình duyệt";
                } else {
                    const savedDefaultVid = localStorage.getItem("setting_default_video") || "best";
                    qualityLabel.innerHTML = `<i class="fa-solid fa-sliders"></i> Độ phân giải Video:`;
                    selectQuality.innerHTML = data.video_qualities.map(v => `<option value="${v.id}" ${v.format_id === savedDefaultVid ? 'selected' : ''}>${v.label}</option>`).join("");
                    badgeDisplay.className = "tweet-badge yt-badge";
                    badgeDisplay.innerHTML = `<i class="fa-solid fa-film"></i> Video MP4 Full HD`;
                    btnServer.className = "btn btn-youtube";
                    txtServerBtn.innerText = "Lưu Video vào máy tính";
                    txtBrowserBtn.innerText = "Tải Video qua trình duyệt";
                }
                updateBrowserLink();
            });
        });

        selectQuality.addEventListener("change", updateBrowserLink);

        function updateBrowserLink() {
            const q = selectQuality.value;
            btnBrowser.href = `/api/stream-youtube?url=${encodeURIComponent(data.url)}&type=${selectedYtMode}&quality=${encodeURIComponent(q)}&title=${encodeURIComponent(data.title)}`;
        }

        // Real-time Progress Tracking Elements
        const downloadProgressModal = document.getElementById("download-progress-modal");
        const progressFileTitle = document.getElementById("progress-file-title");
        const progressStatusDesc = document.getElementById("progress-status-desc");
        const progressPercentBadge = document.getElementById("progress-percent-badge");
        const progressBarFill = document.getElementById("progress-bar-fill");
        const progressSizeStats = document.getElementById("progress-size-stats");
        const progressSpeedStats = document.getElementById("progress-speed-stats");
        const pstep1 = document.getElementById("pstep-1");
        const pstep2 = document.getElementById("pstep-2");
        const pstep3 = document.getElementById("pstep-3");
        const btnCloseProgress = document.getElementById("btn-close-progress");

        let progressInterval = null;
        let isDownloading = false;

        if (btnCloseProgress) {
            btnCloseProgress.addEventListener("click", () => {
                if (isDownloading) return; // Khoá khi đang tải
                if (progressInterval) clearInterval(progressInterval);
                downloadProgressModal.classList.add("hidden");
            });
        }
        if (downloadProgressModal) {
            downloadProgressModal.addEventListener("click", (e) => {
                if (e.target === downloadProgressModal) {
                    if (isDownloading) return; // Khoá khi đang tải
                    if (progressInterval) clearInterval(progressInterval);
                    downloadProgressModal.classList.add("hidden");
                }
            });
        }

        btnServer.addEventListener("click", async () => {
            const q = selectQuality.value;
            const taskId = `dl_${Date.now()}`;

            // Reset Progress State
            if (progressFileTitle) progressFileTitle.innerText = data.title;
            if (progressStatusDesc) progressStatusDesc.innerText = `Đang kết nối đến YouTube...`;
            if (progressPercentBadge) progressPercentBadge.innerText = `0%`;
            if (progressBarFill) progressBarFill.style.width = `0%`;
            if (progressSizeStats) progressSizeStats.innerHTML = `<i class="fa-solid fa-database"></i> Đang phân tích...`;
            if (progressSpeedStats) progressSpeedStats.innerHTML = `<i class="fa-solid fa-gauge-high"></i> Đang kết nối...`;

            if (pstep1) pstep1.classList.add("active");
            if (pstep2) pstep2.classList.remove("active");
            if (pstep3) pstep3.classList.remove("active");
            if (downloadProgressModal) downloadProgressModal.classList.remove("hidden");

            // Khoá nút đóng khi đang tải
            isDownloading = true;
            if (btnCloseProgress) {
                btnCloseProgress.style.opacity = "0.3";
                btnCloseProgress.style.cursor = "not-allowed";
                btnCloseProgress.title = "Đang tải... Vui lòng đợi.";
            }

            // ── Phase 1: Khởi động background download ─────────────────────────
            const startUrl = `/api/start-download?url=${encodeURIComponent(data.url)}&type=${selectedYtMode}&quality=${encodeURIComponent(q)}&title=${encodeURIComponent(data.title)}&task_id=${taskId}`;
            try {
                const startResp = await fetch(startUrl);
                const startJson = await safeJson(startResp);
                if (!startJson.success) {
                    if (progressStatusDesc) progressStatusDesc.innerText = `Lỗi: ${startJson.error}`;
                    return;
                }
            } catch (e) {
                if (progressStatusDesc) progressStatusDesc.innerText = `Không thể kết nối đến máy chủ.`;
                return;
            }

            // ── Phase 2: Poll tiến trình + smooth animation fallback ────────────
            if (progressInterval) clearInterval(progressInterval);
            const estimatedMs = selectedYtMode === "mp3" ? 18000 : 45000;
            const startTime = Date.now();
            let gotRealProgress = false;
            let downloadTriggered = false;

            const setUI = (pct, statusText, speed, size) => {
                const rounded = Math.min(Math.round(pct), 99);
                if (progressPercentBadge) progressPercentBadge.innerText = `${rounded}%`;
                if (progressBarFill) progressBarFill.style.width = `${rounded}%`;
                if (progressStatusDesc && statusText) progressStatusDesc.innerText = statusText;
                if (progressSpeedStats && speed) progressSpeedStats.innerHTML = speed;
                if (progressSizeStats && size) progressSizeStats.innerHTML = size;
            };

            const unlockClose = () => {
                isDownloading = false;
                if (btnCloseProgress) {
                    btnCloseProgress.style.opacity = "";
                    btnCloseProgress.style.cursor = "";
                    btnCloseProgress.title = "Đóng";
                }
            };

            const triggerFileDownload = () => {
                if (downloadTriggered) return;
                downloadTriggered = true;
                clearInterval(progressInterval);

                if (progressPercentBadge) progressPercentBadge.innerText = `100%`;
                if (progressBarFill) progressBarFill.style.width = `100%`;
                if (progressStatusDesc) progressStatusDesc.innerText = `Hoàn tất! Đang gửi tệp về máy...`;
                if (progressSpeedStats) progressSpeedStats.innerHTML = `<i class="fa-solid fa-circle-check"></i> Hoàn tất`;
                if (pstep1) pstep1.classList.add("active");
                if (pstep2) pstep2.classList.add("active");
                if (pstep3) pstep3.classList.add("active");

                // Trigger browser download
                const ext = selectedYtMode === "mp3" ? "mp3" : "mp4";
                const dlUrl = `/api/stream-youtube?task_id=${taskId}`;
                const a = document.createElement("a");
                a.href = dlUrl;
                a.download = `${data.title}.${ext}`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);

                // Mở khóa nút đóng sau 3s (đủ để browser nhận file)
                setTimeout(() => {
                    unlockClose();
                    if (progressStatusDesc) progressStatusDesc.innerText = `✅ Đã lưu vào thư mục Downloads!`;
                }, 3000);
            };

            progressInterval = setInterval(async () => {
                // Real poll
                try {
                    const ctrl = new AbortController();
                    const t = setTimeout(() => ctrl.abort(), 2500);
                    const resp = await fetch(`/api/progress/${taskId}`, { signal: ctrl.signal });
                    clearTimeout(t);
                    const info = await safeJson(resp);

                    if (info && info.status === "downloading" && info.percent > 10) {
                        gotRealProgress = true;
                        const pct = info.percent;
                        setUI(pct,
                            `Đang tải: ${pct}% • Còn ~${info.eta || 'vài giây'}`,
                            `<i class="fa-solid fa-gauge-high"></i> ${info.speed || 'N/A'}`,
                            `<i class="fa-solid fa-database"></i> ${info.downloaded || '0 MB'} / ${info.total || '...'}`
                        );
                        if (pstep2) pstep2.classList.remove("active");
                    } else if (info && info.status === "converting") {
                        gotRealProgress = true;
                        setUI(97, `Đang đóng gói ${selectedYtMode.toUpperCase()}...`,
                            `<i class="fa-solid fa-gears fa-spin"></i> Đang nén`,
                            `<i class="fa-solid fa-database"></i> Gần xong...`
                        );
                        if (pstep2) pstep2.classList.add("active");
                    } else if (info && info.status === "completed") {
                        triggerFileDownload();
                        return;
                    } else if (info && info.status === "error") {
                        clearInterval(progressInterval);
                        unlockClose();
                        if (progressStatusDesc) progressStatusDesc.innerText = `❌ Lỗi: ${info.eta || 'Không thể tải. Vui lòng thử lại!'}`;
                        return;
                    }
                } catch (_) {}

                // Smooth animation fallback
                if (!gotRealProgress && !downloadTriggered) {
                    const elapsed = Date.now() - startTime;
                    const rawRatio = Math.min(elapsed / estimatedMs, 0.95);
                    let fakePct = rawRatio < 0.5
                        ? 3 + rawRatio * 2 * 72
                        : 75 + (rawRatio - 0.5) * 2 * 15;
                    fakePct = Math.min(fakePct, 90);
                    const remainSec = Math.max(0, Math.round((estimatedMs - elapsed) / 1000));

                    let stepText = `Đang xử lý... (~${remainSec}s còn lại)`;
                    let speedHtml = `<i class="fa-solid fa-spinner fa-spin"></i> Đang tải dữ liệu`;
                    let sizeHtml = `<i class="fa-solid fa-database"></i> Đang chuẩn bị...`;

                    if (fakePct >= 15 && fakePct < 60) {
                        stepText = `Đang tải âm thanh/video từ YouTube...`;
                        speedHtml = `<i class="fa-solid fa-gauge-high"></i> Đang tải`;
                    } else if (fakePct >= 60 && fakePct < 85) {
                        stepText = `Đang chuyển đổi sang ${selectedYtMode.toUpperCase()}...`;
                        speedHtml = `<i class="fa-solid fa-gears fa-spin"></i> Đang nén`;
                        if (pstep2) pstep2.classList.add("active");
                    } else if (fakePct >= 85) {
                        stepText = `Sắp xong! Đang đóng gói tệp...`;
                        speedHtml = `<i class="fa-solid fa-gears fa-spin"></i> Hoàn tất nén`;
                        if (pstep2) pstep2.classList.add("active");
                    }

                    setUI(fakePct, stepText, speedHtml, sizeHtml);
                }
            }, 600);

            // Safety timeout: sau estimatedMs + 10s, cố trigger download dù poll ra sao
            setTimeout(triggerFileDownload, estimatedMs + 10000);
        });



    }

    // Render Twitter Result
    function renderTwitterResult(data) {
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
            <div class="result-card glass-panel luxury-border">
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
        attachTwitterEvents(data);
    }

    function attachTwitterEvents(data) {
        const mediaItems = resultContainer.querySelectorAll(".media-item");
        mediaItems.forEach(item => {
            item.addEventListener("click", () => {
                const origUrl = item.getAttribute("data-orig");
                lightboxImg.src = origUrl;
                lightboxDownloadBtn.href = `/api/stream-file?url=${encodeURIComponent(origUrl)}&name=X_${data.author_username}_orig&ext=jpg`;
                lightboxModal.classList.remove("hidden");
            });
        });

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

        const btnDlVideoServer = document.getElementById("btn-dl-video-server");
        if (btnDlVideoServer) {
            btnDlVideoServer.addEventListener("click", () => {
                const targetUrl = selectQuality ? selectQuality.value : data.videos[0].download_url;
                const fname = `X_${data.author_username}_${data.tweet_id}`;
                const a = document.createElement("a");
                a.href = `/api/stream-file?url=${encodeURIComponent(targetUrl)}&name=${encodeURIComponent(fname)}&ext=mp4`;
                a.download = `${fname}.mp4`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                showToast("Đang tải video về máy...", "info");
            });
        }

        const btnDlPhotosServer = document.getElementById("btn-dl-photos-server");
        if (btnDlPhotosServer) {
            btnDlPhotosServer.addEventListener("click", async () => {
                const photos = data.photos;
                showToast(`Đang tải ${photos.length} ảnh về máy...`, "info");
                btnDlPhotosServer.disabled = true;
                btnDlPhotosServer.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Đang tải...`;

                // Tải từng ảnh lần lượt với delay nhỏ
                for (let i = 0; i < photos.length; i++) {
                    const p = photos[i];
                    const ext = p.download_url.includes('.png') ? 'png' : 'jpg';
                    const fname = `X_${data.author_username}_${data.tweet_id}_${i+1}`;
                    const a = document.createElement("a");
                    a.href = `/api/stream-file?url=${encodeURIComponent(p.download_url)}&name=${encodeURIComponent(fname)}&ext=${ext}`;
                    a.download = `${fname}.${ext}`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    if (i < photos.length - 1) await new Promise(r => setTimeout(r, 800));
                }

                setTimeout(() => {
                    btnDlPhotosServer.disabled = false;
                    btnDlPhotosServer.innerHTML = `<i class="fa-solid fa-cloud-arrow-down"></i> Tải tất cả (${photos.length} ảnh) vào máy`;
                    showToast(`Đã gửi ${photos.length} ảnh gốc! Kiểm tra mục Downloads.`, "success");
                }, photos.length * 800 + 500);
            });
        }
    }

    // Open Downloads Folder
    btnOpenFolder.addEventListener("click", async () => {
        try {
            const resp = await fetch("/api/open-folder", { method: "POST" });
            const res = await safeJson(resp);
            if (res.success) {
                showToast("Đang mở thư mục lưu trữ...", "info");
            } else {
                showToast(res.error || "Không thể mở thư mục.", "error");
            }
        } catch (err) {
            showToast("Lỗi mở thư mục: " + err.message, "error");
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
            const res = await safeJson(resp);
            const history = res.history || [];
            
            if (history.length === 0) {
                historyList.innerHTML = `<div class="text-center text-muted p-4">Chưa có lịch sử tải xuống nào.</div>`;
                return;
            }

            historyList.innerHTML = history.map(item => `
                <div class="history-item">
                    <div class="history-meta">
                        <h5>${escapeHtml(item.title || item.author || 'Tệp')} (${(item.platform || 'Media').toUpperCase()})</h5>
                        <p>${item.type ? item.type.toUpperCase() : item.count + ' tệp'} • ${item.downloaded_at}</p>
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
        escaped = escaped.replace(/(#[a-zA-Z0-9_\u00c0-\u1ef9]+)/g, '<span style="color: #60a5fa;">$1</span>');
        escaped = escaped.replace(/(@[a-zA-Z0-9_]+)/g, '<span style="color: #a78bfa;">$1</span>');
        escaped = escaped.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" style="color: #38bdf8; text-decoration: underline;">$1</a>');
        return escaped;
    }
});
