document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const form = document.getElementById("extract-form");
    const inputUrl = document.getElementById("tweet-url-input");
    const inputWrapper = document.getElementById("main-input-wrapper");
    const inputPlatformIcon = document.getElementById("input-platform-icon");
    const formatDetectedBadge = document.getElementById("format-detected-badge");
    const detectedText = document.getElementById("detected-text");
    const formatWarningBox = document.getElementById("format-warning-box");

    const btnPaste = document.getElementById("btn-paste");
    const btnClear = document.getElementById("btn-clear");
    const btnSubmit = document.getElementById("btn-submit");
    const btnText = btnSubmit.querySelector(".btn-text");
    const btnLoader = btnSubmit.querySelector(".btn-loader");
    
    const skeleton = document.getElementById("skeleton-loading");
    const resultContainer = document.getElementById("result-container");
    const toastContainer = document.getElementById("toast-container");
    const navTabs = document.querySelectorAll(".nav-tab");

    // Settings Modal Elements
    const btnToggleSettings = document.getElementById("btn-toggle-settings");
    const settingsModal = document.getElementById("settings-modal");
    const btnCloseSettings = document.getElementById("btn-close-settings");
    const settingDefaultMp3 = document.getElementById("setting-default-mp3");
    const settingDefaultVideo = document.getElementById("setting-default-video");
    const settingAutoExtract = document.getElementById("setting-auto-extract");
    const settingCookiesInput = document.getElementById("setting-cookies-input");
    const btnSaveCookies = document.getElementById("btn-save-cookies");

    // Lightbox Elements
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
            showToast(settingAutoExtract.checked ? "Đã bật tự động phân tích khi dán!" : "Đã tắt tự động phân tích!", "info", 2000);
        });
    }

    // Save Cookies
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
                    showToast(res.message || "Đã lưu Cookies thành công!", "success");
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

    // Modal Events
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
        toast.className = `toast-item toast-${type}`;
        
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
            toast.style.transform = "translateY(12px) scale(0.95)";
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }

    // Auto-reset input sau khi tải để sẵn sàng cho link tiếp theo mà không làm mất card preview
    function autoReset(delayMs = 1500) {
        setTimeout(() => {
            inputUrl.value = "";
            btnClear.classList.add("hidden");
            validateUrlInput("");
        }, delayMs);
    }

    // ==================== REAL-TIME LINK VALIDATION & PLATFORM DETECTION ====================

    function checkPlatformFromUrl(raw) {
        if (!raw) return { platform: "empty" };
        const val = raw.toLowerCase();

        // 1. Twitter / X
        if (val.includes("twitter.com") || val.includes("x.com") || val.includes("vxtwitter.com") || val.includes("fxtwitter.com") || val.includes("fixupx.com")) {
            return {
                platform: "twitter",
                name: "Twitter (X)",
                desc: "Ảnh gốc :orig / Video 4K",
                icon: "fa-brands fa-x-twitter",
                containerClass: "is-valid-twitter"
            };
        }

        // 2. YouTube
        if (val.includes("youtube.com") || val.includes("youtu.be") || val.includes("music.youtube.com")) {
            return {
                platform: "youtube",
                name: "YouTube",
                desc: "Video MP4 / MP3 320k",
                icon: "fa-brands fa-youtube",
                containerClass: "is-valid-youtube"
            };
        }

        // 3. TikTok
        if (val.includes("tiktok.com") || val.includes("vt.tiktok.com") || val.includes("vm.tiktok.com")) {
            return {
                platform: "tiktok",
                name: "TikTok",
                desc: "Video Không Logo / MP3 / Album Ảnh",
                icon: "fa-brands fa-tiktok",
                containerClass: "is-valid-tiktok"
            };
        }

        // 4. Douyin
        if (val.includes("douyin.com") || val.includes("iesdouyin.com") || val.includes("v.douyin.com")) {
            return {
                platform: "douyin",
                name: "Douyin (抖音)",
                desc: "Video Không Logo / MP3 / Album Ảnh",
                icon: "fa-solid fa-compact-disc",
                containerClass: "is-valid-douyin"
            };
        }

        // 5. Facebook
        if (val.includes("facebook.com") || val.includes("fb.watch") || val.includes("fb.com")) {
            return {
                platform: "facebook",
                name: "Facebook",
                desc: "Video HD & Reels",
                icon: "fa-brands fa-facebook",
                containerClass: "is-valid-facebook"
            };
        }

        // 6. Instagram
        if (val.includes("instagram.com") || val.includes("instagr.am") || val.includes("ig.me")) {
            return {
                platform: "instagram",
                name: "Instagram",
                desc: "Ảnh HD, Reels & Album",
                icon: "fa-brands fa-instagram",
                containerClass: "is-valid-instagram"
            };
        }

        // 7. Check if it's an unsupported URL or invalid link
        if (val.startsWith("http://") || val.startsWith("https://") || val.includes(".com") || val.includes(".net") || val.includes(".org") || val.includes(".vn") || val.length > 8) {
            return { platform: "invalid" };
        }

        return { platform: "typing" };
    }

    function validateUrlInput(val) {
        const text = val.trim();
        const result = checkPlatformFromUrl(text);

        // Reset all classes
        inputWrapper.className = "input-container";
        formatDetectedBadge.classList.add("hidden");
        formatWarningBox.classList.add("hidden");

        if (result.platform === "empty") {
            inputPlatformIcon.className = "fa-solid fa-link";
            btnClear.classList.add("hidden");
            return;
        }

        btnClear.classList.remove("hidden");

        if (result.platform === "invalid") {
            inputWrapper.classList.add("is-invalid");
            inputPlatformIcon.className = "fa-solid fa-triangle-exclamation";
            formatWarningBox.classList.remove("hidden");
            switchActiveTab("all");
            return;
        }

        if (result.platform === "typing") {
            inputPlatformIcon.className = "fa-solid fa-link";
            return;
        }

        // Valid platform recognized!
        inputWrapper.classList.add(result.containerClass);
        inputPlatformIcon.className = result.icon;
        
        // Show detection badge
        detectedText.innerHTML = `<strong>${result.name}</strong> • ${result.desc}`;
        formatDetectedBadge.classList.remove("hidden");

        // Switch active tab
        switchActiveTab(result.platform);
    }

    inputUrl.addEventListener("input", () => {
        validateUrlInput(inputUrl.value);
    });

    // Tab Switching
    navTabs.forEach(btn => {
        btn.addEventListener("click", () => {
            navTabs.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            const platform = btn.dataset.platform;
            if (platform === "youtube") {
                inputUrl.placeholder = "Dán link YouTube / Shorts vào đây... vd: https://youtu.be/...";
            } else if (platform === "twitter") {
                inputUrl.placeholder = "Dán link X (Twitter) vào đây... vd: https://x.com/user/status/...";
            } else if (platform === "tiktok") {
                inputUrl.placeholder = "Dán link TikTok vào đây... vd: https://www.tiktok.com/@user/video/...";
            } else if (platform === "douyin") {
                inputUrl.placeholder = "Dán link Douyin (抖音) vào đây... vd: https://v.douyin.com/...";
            } else if (platform === "facebook") {
                inputUrl.placeholder = "Dán link Facebook Video hoặc Reels vào đây... vd: https://fb.watch/...";
            } else if (platform === "instagram") {
                inputUrl.placeholder = "Dán link Instagram Post, Reels hoặc Story... vd: https://instagram.com/reel/...";
            } else {
                inputUrl.placeholder = "Dán link X, YouTube, TikTok, Douyin, Facebook hoặc Instagram...";
            }
            inputUrl.focus();
        });
    });

    function switchActiveTab(platform) {
        navTabs.forEach(btn => {
            if (btn.dataset.platform === platform) {
                btn.classList.add("active");
            } else if (platform === "all" && btn.dataset.platform === "all") {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
        });
    }

    btnClear.addEventListener("click", () => {
        inputUrl.value = "";
        validateUrlInput("");
        inputUrl.focus();
    });

    btnPaste.addEventListener("click", async () => {
        try {
            const text = await navigator.clipboard.readText();
            if (text) {
                inputUrl.value = text.trim();
                validateUrlInput(inputUrl.value);
                showToast("Đã dán liên kết!", "info", 1800);

                const autoExtract = localStorage.getItem("setting_auto_extract") !== "false";
                const check = checkPlatformFromUrl(inputUrl.value);
                if (autoExtract && check.platform !== "invalid" && check.platform !== "empty") {
                    form.dispatchEvent(new Event("submit"));
                }
            }
        } catch (err) {
            inputUrl.focus();
            showToast("Vui lòng nhấn Ctrl+V để dán liên kết.", "info", 2500);
        }
    });

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
            showToast("Vui lòng nhập đường link bài viết!", "error");
            return;
        }

        const check = checkPlatformFromUrl(url);
        if (check.platform === "invalid") {
            showToast("Định dạng link không được hỗ trợ! Vui lòng kiểm tra lại liên kết.", "error", 4500);
            formatWarningBox.classList.remove("hidden");
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
            } else if (res.data.platform === "tiktok" || res.data.platform === "douyin") {
                renderTikTokDouyinResult(res.data);
            } else if (res.data.platform === "facebook") {
                renderFacebookResult(res.data);
            } else if (res.data.platform === "instagram") {
                renderInstagramResult(res.data);
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


    // ==================== RENDER FACEBOOK RESULT ====================

    function renderFacebookResult(data) {
        const qualities = data.qualities || [];
        let qualityOptionsHtml = qualities.map((q, idx) =>
            `<option value="${q.url}">${q.resolution || `Bản ${idx+1}`}</option>`
        ).join("");

        resultContainer.innerHTML = `
            <div class="result-card">
                <!-- Author Header -->
                <div class="card-author-bar">
                    <div class="author-profile-group">
                        <div class="avatar-icon-brand fb-icon">
                            <i class="fa-brands fa-facebook"></i>
                        </div>
                        <div class="author-meta-text">
                            <h4>${escapeHtml(data.author_name)} <i class="fa-solid fa-circle-check verified-icon"></i></h4>
                            <span class="author-handle-text">Facebook Video • ${data.duration_str}</span>
                        </div>
                    </div>
                    <a href="${data.url}" target="_blank" class="btn-open-origin" title="Xem trên Facebook">
                        <i class="fa-brands fa-facebook"></i> Mở Facebook
                    </a>
                </div>

                <!-- Video Title -->
                ${data.title ? `<p class="card-caption-text">${formatTweetText(data.title)}</p>` : ''}

                <!-- Video Player -->
                <div class="media-box-wrapper video-container">
                    <video id="player-video" controls poster="${data.cover || ''}" playsinline>
                        <source src="${data.video_url}" type="video/mp4">
                    </video>
                </div>

                <!-- Download Actions -->
                <div class="download-action-card">
                    <div class="meta-tags-bar">
                        <span class="status-chip chip-facebook"><i class="fa-solid fa-film"></i> Facebook Video Full HD / SD</span>
                        ${qualities.length > 1 ? `
                        <div class="quality-dropdown-wrap">
                            <i class="fa-solid fa-sliders"></i>
                            <select id="select-fb-quality" class="quality-select-native">${qualityOptionsHtml}</select>
                        </div>` : `<input type="hidden" id="select-fb-quality" value="${data.video_url}">`}
                    </div>
                    <div class="action-buttons-stack">
                        <button id="btn-dl-fb-video" class="btn-cta btn-cta-facebook">
                            <i class="fa-solid fa-download"></i>
                            <span>Tải Video Facebook</span>
                            <span class="cta-badge-tag">MP4</span>
                        </button>
                        ${data.has_music ? `
                        <a href="/api/stream-file?url=${encodeURIComponent(data.video_url)}&name=${encodeURIComponent('FB_Audio_' + data.id)}&ext=mp3" class="btn-cta btn-cta-music" download target="_blank">
                            <i class="fa-solid fa-music"></i>
                            <span>Tải Âm Thanh MP3</span>
                        </a>` : ''}
                    </div>
                </div>
            </div>
        `;

        resultContainer.classList.remove("hidden");
        attachFacebookEvents(data);
    }

    function attachFacebookEvents(data) {
        const selectQuality = document.getElementById("select-fb-quality");
        const videoPlayer = document.getElementById("player-video");
        if (selectQuality && videoPlayer) {
            selectQuality.addEventListener("change", (e) => {
                const newUrl = e.target.value;
                const currentTime = videoPlayer.currentTime;
                const isPaused = videoPlayer.paused;
                videoPlayer.src = newUrl;
                videoPlayer.currentTime = currentTime;
                if (!isPaused) videoPlayer.play();
            });
        }

        const btnDlFbVideo = document.getElementById("btn-dl-fb-video");
        if (btnDlFbVideo) {
            btnDlFbVideo.addEventListener("click", () => {
                const targetUrl = selectQuality ? selectQuality.value : data.video_url;
                const fname = `FB_${data.author_name}_${data.id}`;
                const a = document.createElement("a");
                a.href = `/api/stream-file?url=${encodeURIComponent(targetUrl)}&name=${encodeURIComponent(fname)}&ext=mp4`;
                a.download = `${fname}.mp4`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                showToast("Đang tải video Facebook về máy...", "info");
                autoReset(3000);
            });
        }
    }


    // ==================== RENDER INSTAGRAM RESULT ====================

    function renderInstagramResult(data) {
        let mediaHtml = "";
        let actionsHtml = "";

        if (data.has_images && data.photos && data.photos.length > 0) {
            const count = data.photos.length;
            const gridClass = count === 1 ? "grid-1" : (count === 2 ? "grid-2" : (count === 3 ? "grid-3" : "grid-more"));

            const photoItems = data.photos.map((p, idx) => `
                <div class="gallery-photo-item" data-orig="${p.download_url}">
                    <span class="photo-index-tag"><i class="fa-solid fa-image"></i> ${idx + 1}/${count}</span>
                    <img src="${p.preview_url}" alt="Instagram Photo ${idx + 1}" loading="lazy">
                    <div class="photo-hover-overlay">
                        <div class="zoom-icon-circle"><i class="fa-solid fa-magnifying-glass-plus"></i></div>
                    </div>
                </div>
            `).join("");

            mediaHtml = `
                <div class="image-gallery-grid ${gridClass}">
                    ${photoItems}
                </div>
            `;

            actionsHtml = `
                <div class="download-action-card">
                    <div class="meta-tags-bar">
                        <span class="status-chip chip-instagram"><i class="fa-solid fa-images"></i> Instagram ${count} ảnh gốc HD</span>
                        <span class="status-chip chip-success"><i class="fa-solid fa-bolt"></i> Chất lượng gốc</span>
                    </div>
                    <div class="action-buttons-stack">
                        <button id="btn-dl-ig-all-photos" class="btn-cta btn-cta-instagram">
                            <i class="fa-solid fa-cloud-arrow-down"></i>
                            <span>Tải tất cả ${count} ảnh · 1 Phát</span>
                            <span class="cta-badge-tag">PNG</span>
                        </button>
                    </div>
                </div>
            `;
        } else if (data.has_video && data.video_url) {
            mediaHtml = `
                <div class="media-box-wrapper video-container">
                    <video id="player-video" controls poster="${data.cover || ''}" playsinline>
                        <source src="${data.video_url}" type="video/mp4">
                    </video>
                </div>
            `;

            actionsHtml = `
                <div class="download-action-card">
                    <div class="meta-tags-bar">
                        <span class="status-chip chip-instagram"><i class="fa-solid fa-film"></i> Instagram Video / Reels HD</span>
                        <span class="status-chip chip-success"><i class="fa-solid fa-bolt"></i> Bản gốc</span>
                    </div>
                    <div class="action-buttons-stack">
                        <button id="btn-dl-ig-video" class="btn-cta btn-cta-instagram">
                            <i class="fa-solid fa-download"></i>
                            <span>Tải Reels / Video về máy</span>
                            <span class="cta-badge-tag">MP4</span>
                        </button>
                        ${data.has_music ? `
                        <a href="/api/stream-file?url=${encodeURIComponent(data.video_url)}&name=${encodeURIComponent('IG_Audio_' + data.id)}&ext=mp3" class="btn-cta btn-cta-music" download target="_blank">
                            <i class="fa-solid fa-music"></i>
                            <span>Tải Âm Thanh MP3</span>
                        </a>` : ''}
                    </div>
                </div>
            `;
        }

        resultContainer.innerHTML = `
            <div class="result-card">
                <!-- Author Header -->
                <div class="card-author-bar">
                    <div class="author-profile-group">
                        <div class="avatar-icon-brand ig-icon">
                            <i class="fa-brands fa-instagram"></i>
                        </div>
                        <div class="author-meta-text">
                            <h4>${escapeHtml(data.author_name)} <i class="fa-solid fa-circle-check verified-icon"></i></h4>
                            <span class="author-handle-text">@${escapeHtml(data.author_username)}</span>
                        </div>
                    </div>
                    <a href="${data.url}" target="_blank" class="btn-open-origin" title="Xem trên Instagram">
                        <i class="fa-brands fa-instagram"></i> Mở Instagram
                    </a>
                </div>

                <!-- Title / Caption -->
                ${data.title ? `<p class="card-caption-text">${formatTweetText(data.title)}</p>` : ''}

                <!-- Media Preview -->
                ${mediaHtml}

                <!-- Download Actions -->
                ${actionsHtml}
            </div>
        `;

        resultContainer.classList.remove("hidden");
        attachInstagramEvents(data);
    }

    function attachInstagramEvents(data) {
        const mediaItems = resultContainer.querySelectorAll(".gallery-photo-item");
        mediaItems.forEach(item => {
            item.addEventListener("click", () => {
                const origUrl = item.getAttribute("data-orig");
                lightboxImg.src = origUrl;
                lightboxDownloadBtn.href = `/api/stream-file?url=${encodeURIComponent(origUrl)}&name=${encodeURIComponent('IG_' + data.author_username + '_' + data.id)}&ext=png`;
                lightboxModal.classList.remove("hidden");
            });
        });

        const btnDlAllPhotos = document.getElementById("btn-dl-ig-all-photos");
        if (btnDlAllPhotos && data.photos) {
            btnDlAllPhotos.addEventListener("click", async () => {
                const photos = data.photos;
                btnDlAllPhotos.disabled = true;
                btnDlAllPhotos.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Đang tải ${photos.length} ảnh...`;

                for (let i = 0; i < photos.length; i++) {
                    const p = photos[i];
                    const fname = `IG_${data.author_username}_${data.id}_${i+1}`;
                    const a = document.createElement("a");
                    a.href = `/api/stream-file?url=${encodeURIComponent(p.download_url)}&name=${encodeURIComponent(fname)}&ext=png`;
                    a.download = `${fname}.png`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    if (i < photos.length - 1) await new Promise(r => setTimeout(r, 150));
                }

                showToast(`✅ Đã tải ${photos.length} ảnh Instagram về máy!`, "success");
                btnDlAllPhotos.disabled = false;
                btnDlAllPhotos.innerHTML = `<i class="fa-solid fa-cloud-arrow-down"></i> Tải tất cả (${photos.length} ảnh)`;
                autoReset();
            });
        }

        const btnDlVideo = document.getElementById("btn-dl-ig-video");
        if (btnDlVideo && data.video_url) {
            btnDlVideo.addEventListener("click", () => {
                const fname = `IG_${data.author_username}_${data.id}`;
                const a = document.createElement("a");
                a.href = `/api/stream-file?url=${encodeURIComponent(data.video_url)}&name=${encodeURIComponent(fname)}&ext=mp4`;
                a.download = `${fname}.mp4`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                showToast("Đang tải video Instagram về máy...", "info");
                autoReset(3000);
            });
        }
    }


    // ==================== RENDER TIKTOK & DOUYIN RESULT ====================

    function renderTikTokDouyinResult(data) {
        const isDouyin = data.platform === "douyin";
        const platformName = isDouyin ? "Douyin (抖音)" : "TikTok";
        const platformChipClass = isDouyin ? "chip-douyin" : "chip-tiktok";
        const platformBtnClass = isDouyin ? "btn-cta-tiktok" : "btn-cta-tiktok";
        const platformIcon = isDouyin ? "fa-compact-disc" : "fa-tiktok";

        let mediaContentHtml = "";
        let actionsHtml = "";

        if (data.has_images && data.photos && data.photos.length > 0) {
            const count = data.photos.length;
            const gridClass = count === 1 ? "grid-1" : (count === 2 ? "grid-2" : (count === 3 ? "grid-3" : "grid-more"));

            const photoItems = data.photos.map((p, idx) => `
                <div class="gallery-photo-item" data-orig="${p.download_url}">
                    <span class="photo-index-tag"><i class="fa-solid fa-image"></i> ${idx + 1}/${count}</span>
                    <img src="${p.preview_url}" alt="Photo ${idx + 1}" loading="lazy">
                    <div class="photo-hover-overlay">
                        <div class="zoom-icon-circle"><i class="fa-solid fa-magnifying-glass-plus"></i></div>
                    </div>
                </div>
            `).join("");

            mediaContentHtml = `
                <div class="image-gallery-grid ${gridClass}">
                    ${photoItems}
                </div>
            `;

            actionsHtml = `
                <div class="download-action-card">
                    <div class="meta-tags-bar">
                        <span class="status-chip ${platformChipClass}"><i class="fa-solid fa-images"></i> Album ${count} ảnh gốc chất lượng cao</span>
                        <span class="status-chip chip-success"><i class="fa-solid fa-bolt"></i> Không Watermark</span>
                    </div>
                    <div class="action-buttons-stack">
                        <button id="btn-dl-tt-all-photos" class="btn-cta btn-cta-primary">
                            <i class="fa-solid fa-cloud-arrow-down"></i>
                            <span>Tải toàn bộ ${count} ảnh · 1 Phát</span>
                            <span class="cta-badge-tag">PNG</span>
                        </button>
                        ${data.has_music ? `
                        <a href="/api/stream-file?url=${encodeURIComponent(data.music_url)}&name=${encodeURIComponent(platformName + '_Music_' + data.id)}&ext=mp3" class="btn-cta btn-cta-music" download target="_blank">
                            <i class="fa-solid fa-music"></i>
                            <span>Tải Nhạc Nền MP3</span>
                        </a>` : ''}
                    </div>
                </div>
            `;
        } else if (data.has_video && data.video_url) {
            mediaContentHtml = `
                <div class="media-box-wrapper video-container">
                    <video id="player-video" controls poster="${data.cover || ''}" playsinline>
                        <source src="${data.video_url}" type="video/mp4">
                    </video>
                </div>
            `;

            actionsHtml = `
                <div class="download-action-card">
                    <div class="meta-tags-bar">
                        <span class="status-chip ${platformChipClass}"><i class="fa-solid fa-bolt"></i> Video HD Không Logo (No-Watermark)</span>
                        <span class="status-chip chip-success"><i class="fa-solid fa-clock"></i> ${data.duration_str}</span>
                    </div>
                    <div class="action-buttons-stack">
                        <button id="btn-dl-tt-video" class="btn-cta ${platformBtnClass}">
                            <i class="fa-solid fa-download"></i>
                            <span>Tải Video Không Logo</span>
                            <span class="cta-badge-tag">MP4</span>
                        </button>
                        ${data.has_music ? `
                        <a href="/api/stream-file?url=${encodeURIComponent(data.music_url)}&name=${encodeURIComponent(platformName + '_Music_' + data.id)}&ext=mp3" class="btn-cta btn-cta-music" download target="_blank">
                            <i class="fa-solid fa-music"></i>
                            <span>Tải Âm Thanh MP3</span>
                        </a>` : ''}
                    </div>
                </div>
            `;
        } else {
            mediaContentHtml = `<div class="p-4 text-center text-muted">Không tìm thấy nội dung để tải về từ bài viết này.</div>`;
        }

        resultContainer.innerHTML = `
            <div class="result-card">
                <!-- Author Header -->
                <div class="card-author-bar">
                    <div class="author-profile-group">
                        <img class="avatar-circle" src="${data.author_avatar || 'https://p16-sign-sg.tiktokcdn.com/tos-alisg-avt-0068/default.jpeg'}" alt="Avatar">
                        <div class="author-meta-text">
                            <h4>${escapeHtml(data.author_name)} <i class="fa-solid fa-circle-check verified-icon"></i></h4>
                            <span class="author-handle-text">@${escapeHtml(data.author_username)}</span>
                        </div>
                    </div>
                    <a href="${data.url}" target="_blank" class="btn-open-origin" title="Xem bài viết gốc">
                        <i class="fa-solid ${platformIcon}"></i> Mở ${platformName}
                    </a>
                </div>

                <!-- Video / Slide Title -->
                ${data.title ? `<p class="card-caption-text">${formatTweetText(data.title)}</p>` : ''}

                <!-- Media Preview -->
                ${mediaContentHtml}

                <!-- Download Actions -->
                ${actionsHtml}
            </div>
        `;

        resultContainer.classList.remove("hidden");
        attachTikTokDouyinEvents(data);
    }

    function attachTikTokDouyinEvents(data) {
        const mediaItems = resultContainer.querySelectorAll(".gallery-photo-item");
        mediaItems.forEach(item => {
            item.addEventListener("click", () => {
                const origUrl = item.getAttribute("data-orig");
                lightboxImg.src = origUrl;
                lightboxDownloadBtn.href = `/api/stream-file?url=${encodeURIComponent(origUrl)}&name=${encodeURIComponent(data.platform + '_' + data.id)}&ext=png`;
                lightboxModal.classList.remove("hidden");
            });
        });

        const btnDlAllPhotos = document.getElementById("btn-dl-tt-all-photos");
        if (btnDlAllPhotos && data.photos) {
            btnDlAllPhotos.addEventListener("click", async () => {
                const photos = data.photos;
                btnDlAllPhotos.disabled = true;
                btnDlAllPhotos.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Đang tải ${photos.length} ảnh...`;

                for (let i = 0; i < photos.length; i++) {
                    const p = photos[i];
                    const fname = `${data.platform.toUpperCase()}_${data.author_username}_${data.id}_${i+1}`;
                    const a = document.createElement("a");
                    a.href = `/api/stream-file?url=${encodeURIComponent(p.download_url)}&name=${encodeURIComponent(fname)}&ext=png`;
                    a.download = `${fname}.png`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    if (i < photos.length - 1) await new Promise(r => setTimeout(r, 150));
                }

                showToast(`✅ Đã tải ${photos.length} ảnh chất lượng cao về máy!`, "success");
                btnDlAllPhotos.disabled = false;
                btnDlAllPhotos.innerHTML = `<i class="fa-solid fa-cloud-arrow-down"></i> Tải toàn bộ (${photos.length} ảnh)`;
                autoReset();
            });
        }

        const btnDlVideo = document.getElementById("btn-dl-tt-video");
        if (btnDlVideo && data.video_url) {
            btnDlVideo.addEventListener("click", () => {
                const fname = `${data.platform.toUpperCase()}_${data.author_username}_${data.id}`;
                const a = document.createElement("a");
                a.href = `/api/stream-file?url=${encodeURIComponent(data.video_url)}&name=${encodeURIComponent(fname)}&ext=mp4`;
                a.download = `${fname}.mp4`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                showToast("Đang tải video Không Logo về máy...", "info");
                autoReset(3000);
            });
        }
    }


    // ==================== RENDER YOUTUBE RESULT ====================

    function renderYouTubeResult(data) {
        selectedYtMode = "mp3";
        const savedDefaultMp3 = localStorage.getItem("setting_default_mp3") || "320";

        resultContainer.innerHTML = `
            <div class="result-card">
                <!-- Channel Info Header -->
                <div class="card-author-bar">
                    <div class="author-profile-group">
                        <div class="avatar-icon-brand yt-icon">
                            <i class="fa-brands fa-youtube"></i>
                        </div>
                        <div class="author-meta-text">
                            <h4>${escapeHtml(data.uploader)} <i class="fa-solid fa-circle-check verified-icon"></i></h4>
                            <span class="author-handle-text"><i class="fa-solid fa-eye"></i> ${data.view_count} lượt xem</span>
                        </div>
                    </div>
                    <a href="${data.url}" target="_blank" class="btn-open-origin" title="Xem trên YouTube">
                        <i class="fa-brands fa-youtube"></i> Mở YouTube
                    </a>
                </div>

                <!-- Video Title -->
                <p class="card-caption-text" style="font-weight: 700; font-size: 0.95rem;">${escapeHtml(data.title)}</p>

                <!-- Media Preview -->
                <div class="media-box-wrapper" style="position: relative;">
                    <img src="${data.thumbnail}" alt="Thumbnail" style="width: 100%; max-height: 400px; object-fit: cover; display: block;">
                    <span class="photo-index-tag" style="top: auto; bottom: 8px; right: 8px; left: auto;"><i class="fa-solid fa-clock"></i> ${data.duration_str}</span>
                </div>

                <!-- Download Actions Card -->
                <div class="download-action-card">
                    <!-- Format Switcher -->
                    <div class="platform-nav-tabs" style="width: 100%; justify-content: center; margin-bottom: 4px;">
                        <button type="button" class="nav-tab active yt-mode-btn" data-mode="mp3" style="flex: 1; justify-content: center;">
                            <i class="fa-solid fa-music"></i> Âm Thanh MP3
                        </button>
                        <button type="button" class="nav-tab yt-mode-btn" data-mode="video" style="flex: 1; justify-content: center;">
                            <i class="fa-solid fa-film"></i> Video MP4
                        </button>
                    </div>

                    <!-- Quality Selectors -->
                    <div class="meta-tags-bar">
                        <div class="quality-dropdown-wrap" id="yt-quality-box">
                            <i class="fa-solid fa-sliders"></i>
                            <select id="select-yt-quality" class="quality-select-native">
                                ${data.audio_qualities.map(a => `<option value="${a.id}" ${a.id === savedDefaultMp3 ? 'selected' : ''}>${a.label}</option>`).join("")}
                            </select>
                        </div>
                        <span id="yt-badge-display" class="status-chip chip-youtube"><i class="fa-solid fa-bolt"></i> Chuẩn 320kbps</span>
                    </div>

                    <!-- Action Buttons -->
                    <div class="action-buttons-stack">
                        <button id="btn-yt-download-server" class="btn-cta btn-cta-youtube">
                            <i class="fa-solid fa-cloud-arrow-down"></i> <span id="txt-yt-server-btn">Tải MP3 về máy</span>
                        </button>
                        <a id="btn-yt-download-browser" href="/api/stream-youtube?url=${encodeURIComponent(data.url)}&type=mp3&quality=${savedDefaultMp3}&title=${encodeURIComponent(data.title)}" class="btn-cta btn-cta-secondary" target="_blank">
                            <i class="fa-solid fa-globe"></i> <span id="txt-yt-browser-btn">Tải qua trình duyệt</span>
                        </a>
                    </div>
                </div>
            </div>
        `;

        resultContainer.classList.remove("hidden");
        attachYouTubeEvents(data);
    }

    function attachYouTubeEvents(data) {
        const formatTabs = resultContainer.querySelectorAll(".yt-mode-btn");
        const selectQuality = document.getElementById("select-yt-quality");
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
                    selectQuality.innerHTML = data.audio_qualities.map(a => `<option value="${a.id}" ${a.id === savedDefaultMp3 ? 'selected' : ''}>${a.label}</option>`).join("");
                    badgeDisplay.className = "status-chip chip-youtube";
                    badgeDisplay.innerHTML = `<i class="fa-solid fa-music"></i> Chuẩn 320kbps`;
                    txtServerBtn.innerText = "Tải MP3 về máy";
                    txtBrowserBtn.innerText = "Tải qua trình duyệt";
                } else {
                    const savedDefaultVid = localStorage.getItem("setting_default_video") || "best";
                    selectQuality.innerHTML = data.video_qualities.map(v => `<option value="${v.id}" ${v.format_id === savedDefaultVid ? 'selected' : ''}>${v.label}</option>`).join("");
                    badgeDisplay.className = "status-chip chip-youtube";
                    badgeDisplay.innerHTML = `<i class="fa-solid fa-film"></i> Video MP4 Full HD`;
                    txtServerBtn.innerText = "Tải Video về máy";
                    txtBrowserBtn.innerText = "Tải qua trình duyệt";
                }
                updateBrowserLink();
            });
        });

        selectQuality.addEventListener("change", updateBrowserLink);

        function updateBrowserLink() {
            const q = selectQuality.value;
            btnBrowser.href = `/api/stream-youtube?url=${encodeURIComponent(data.url)}&type=${selectedYtMode}&quality=${encodeURIComponent(q)}&title=${encodeURIComponent(data.title)}`;
        }

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
                if (isDownloading) return;
                if (progressInterval) clearInterval(progressInterval);
                downloadProgressModal.classList.add("hidden");
            });
        }
        if (downloadProgressModal) {
            downloadProgressModal.addEventListener("click", (e) => {
                if (e.target === downloadProgressModal) {
                    if (isDownloading) return;
                    if (progressInterval) clearInterval(progressInterval);
                    downloadProgressModal.classList.add("hidden");
                }
            });
        }

        btnServer.addEventListener("click", async () => {
            const q = selectQuality.value;
            const taskId = `dl_${Date.now()}`;

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

            isDownloading = true;
            if (btnCloseProgress) {
                btnCloseProgress.style.opacity = "0.3";
                btnCloseProgress.style.cursor = "not-allowed";
                btnCloseProgress.title = "Đang tải... Vui lòng đợi.";
            }

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

                const ext = selectedYtMode === "mp3" ? "mp3" : "mp4";
                const dlUrl = `/api/stream-youtube?task_id=${taskId}`;
                const a = document.createElement("a");
                a.href = dlUrl;
                a.download = `${data.title}.${ext}`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);

                setTimeout(() => {
                    unlockClose();
                    if (progressStatusDesc) progressStatusDesc.innerText = `✅ Đã lưu vào thư mục Downloads!`;
                    autoReset(3000);
                }, 3000);
            };

            progressInterval = setInterval(async () => {
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

            setTimeout(triggerFileDownload, estimatedMs + 10000);
        });
    }


    // ==================== RENDER TWITTER RESULT ====================

    function renderTwitterResult(data) {
        const hasPhotos = data.photos && data.photos.length > 0;
        const hasVideos = data.videos && data.videos.length > 0;

        let mediaHtml = "";

        if (hasVideos) {
            const video = data.videos[0];
            const qualities = video.qualities || [];
            
            let qualityOptionsHtml = qualities.map((q, idx) =>
                `<option value="${q.url}">${q.resolution || `Chất lượng ${idx+1}`}</option>`
            ).join("");

            mediaHtml = `
                <div class="media-box-wrapper video-container">
                    <video id="player-video" controls poster="${video.preview_url || ''}">
                        <source src="${video.download_url}" type="video/mp4">
                    </video>
                </div>

                <div class="download-action-card">
                    <div class="meta-tags-bar">
                        <span class="status-chip chip-twitter"><i class="fa-solid fa-film"></i> Video MP4 gốc · Không nén</span>
                        ${qualities.length > 1 ? `
                        <div class="quality-dropdown-wrap">
                            <i class="fa-solid fa-sliders"></i>
                            <select id="select-video-quality" class="quality-select-native">${qualityOptionsHtml}</select>
                        </div>` : `<input type="hidden" id="select-video-quality" value="${video.download_url}">`}
                    </div>
                    <div class="action-buttons-stack">
                        <button id="btn-dl-video-server" class="btn-cta btn-cta-twitter">
                            <i class="fa-solid fa-download"></i>
                            <span>Tải Video về máy</span>
                            <span class="cta-badge-tag">MP4</span>
                        </button>
                    </div>
                </div>
            `;
        } else if (hasPhotos) {
            const count = data.photos.length;
            const gridClass = count === 1 ? "grid-1" : (count === 2 ? "grid-2" : (count === 3 ? "grid-3" : "grid-more"));

            let photoItems = data.photos.map((p, idx) => `
                <div class="gallery-photo-item" data-orig="${p.download_url}" data-preview="${p.preview_url}">
                    <span class="photo-index-tag"><i class="fa-solid fa-expand"></i> :orig</span>
                    <img src="${p.preview_url}" alt="Photo ${idx+1}" loading="lazy">
                    <div class="photo-hover-overlay">
                        <div class="zoom-icon-circle"><i class="fa-solid fa-magnifying-glass-plus"></i></div>
                    </div>
                </div>
            `).join("");

            mediaHtml = `
                <div class="image-gallery-grid ${gridClass}">
                    ${photoItems}
                </div>

                <div class="download-action-card">
                    <div class="meta-tags-bar">
                        <span class="status-chip chip-twitter"><i class="fa-solid fa-images"></i> ${count} ảnh gốc chất lượng cao</span>
                        <span class="status-chip chip-success"><i class="fa-solid fa-download"></i> Tải ảnh PNG gốc</span>
                    </div>
                    <div class="action-buttons-stack">
                        <button id="btn-dl-photos-server" class="btn-cta btn-cta-twitter">
                            <i class="fa-solid fa-cloud-arrow-down"></i>
                            <span>Tải tất cả ${count} ảnh · 1 phát</span>
                            <span class="cta-badge-tag">PNG</span>
                        </button>
                    </div>
                </div>
            `;
        } else {
            mediaHtml = `<div class="p-4 text-center text-muted">Không tìm thấy ảnh hoặc video trong bài viết này.</div>`;
        }

        resultContainer.innerHTML = `
            <div class="result-card">
                <!-- Tweet Author Header -->
                <div class="card-author-bar">
                    <div class="author-profile-group">
                        <img class="avatar-circle" src="${data.author_avatar || 'https://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png'}" alt="Avatar">
                        <div class="author-meta-text">
                            <h4>${escapeHtml(data.author_name)} <i class="fa-solid fa-circle-check verified-icon"></i></h4>
                            <span class="author-handle-text">@${escapeHtml(data.author_username || 'user')}</span>
                        </div>
                    </div>
                    <a href="https://x.com/i/status/${data.tweet_id}" target="_blank" class="btn-open-origin" title="Xem trên X">
                        <i class="fa-brands fa-x-twitter"></i> Xem bài viết
                    </a>
                </div>

                <!-- Tweet Text Content -->
                ${data.text ? `<p class="card-caption-text">${formatTweetText(data.text)}</p>` : ''}

                <!-- Media Section -->
                ${mediaHtml}
            </div>
        `;

        resultContainer.classList.remove("hidden");
        attachTwitterEvents(data);
    }

    function attachTwitterEvents(data) {
        const mediaItems = resultContainer.querySelectorAll(".gallery-photo-item");
        mediaItems.forEach(item => {
            item.addEventListener("click", () => {
                const origUrl = item.getAttribute("data-orig");
                lightboxImg.src = origUrl;
                lightboxDownloadBtn.href = `/api/stream-file?url=${encodeURIComponent(origUrl)}&name=X_${data.author_username}_orig&ext=png`;
                lightboxModal.classList.remove("hidden");
            });
        });

        const selectQuality = document.getElementById("select-video-quality");
        const videoPlayer = document.getElementById("player-video");
        if (selectQuality && videoPlayer) {
            selectQuality.addEventListener("change", (e) => {
                const newUrl = e.target.value;
                const currentTime = videoPlayer.currentTime;
                const isPaused = videoPlayer.paused;
                videoPlayer.src = newUrl;
                videoPlayer.currentTime = currentTime;
                if (!isPaused) videoPlayer.play();
            });
        }

        const btnDlVideoServer = document.getElementById("btn-dl-video-server");
        if (btnDlVideoServer) {
            btnDlVideoServer.addEventListener("click", () => {
                const targetUrl = selectQuality ? selectQuality.value : (data.videos[0].download_url);
                const fname = `X_${data.author_username}_${data.tweet_id}`;
                const a = document.createElement("a");
                a.href = `/api/stream-file?url=${encodeURIComponent(targetUrl)}&name=${encodeURIComponent(fname)}&ext=mp4`;
                a.download = `${fname}.mp4`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                showToast("Đang tải video về máy...", "info");
                autoReset(3000);
            });
        }

        const btnDlPhotosServer = document.getElementById("btn-dl-photos-server");
        if (btnDlPhotosServer) {
            btnDlPhotosServer.addEventListener("click", async () => {
                const photos = data.photos;
                btnDlPhotosServer.disabled = true;
                btnDlPhotosServer.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Đang tải ${photos.length} ảnh...`;

                for (let i = 0; i < photos.length; i++) {
                    const p = photos[i];
                    const fname = `X_${data.author_username}_${data.tweet_id}_${i+1}`;
                    const a = document.createElement("a");
                    a.href = `/api/stream-file?url=${encodeURIComponent(p.download_url)}&name=${encodeURIComponent(fname)}&ext=png`;
                    a.download = `${fname}.png`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    if (i < photos.length - 1) await new Promise(r => setTimeout(r, 150));
                }

                showToast(`✅ Đã tải ${photos.length} ảnh PNG gốc về máy!`, "success");
                btnDlPhotosServer.disabled = false;
                btnDlPhotosServer.innerHTML = `<i class="fa-solid fa-cloud-arrow-down"></i> Tải tất cả (${photos.length} ảnh) vào máy`;
                autoReset();
            });
        }
    }

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
