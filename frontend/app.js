const categories = [
  { id: "all", name: "Tất cả", logo: "/static/assets/logo-all.svg" },
  { id: "zalo", name: "Zalo", logo: "/static/assets/logo-zalo.png" },
  { id: "facebook", name: "Facebook", logo: "/static/assets/logo-facebook.svg" },
  { id: "tiktok", name: "TikTok", logo: "/static/assets/logo-tiktok.svg" },
  { id: "shopee", name: "Shopee", logo: "/static/assets/logo-shopee.svg" },
  { id: "video-ai", name: "Video AI", logo: "/static/assets/logo-ai.svg" },
];

const tools = [
  {
    id: "zalo-friend-message",
    name: "Tool Zalo kết bạn và tự động gửi tin nhắn",
    description: "Nhập Excel, kết bạn theo danh sách và gửi tin nhắn tự động qua Zalo Web.",
    category: "zalo",
    logo: "/static/assets/logo-zalo.png",
    route: "/tools/zalo/send-message",
    enabled: true,
  },
];

const labels = {
  CONNECTED: "Đã kết nối",
  DISCONNECTED: "Mất kết nối",
  BROWSER_DISCONNECTED: "Mất kết nối",
  UNKNOWN: "Không rõ",
  ERROR: "Lỗi",
  LOGGED_IN: "Đã đăng nhập",
  LOGIN_REQUIRED: "Cần đăng nhập",
  USER_ACTION_REQUIRED: "Cần thao tác thủ công",
  VALID: "Hợp lệ",
  INVALID: "Không hợp lệ",
  DUPLICATE: "Trùng lặp",
  PENDING: "Đang chờ",
  RUNNING: "Đang chạy",
  PAUSED: "Đã tạm dừng",
  STOPPED: "Đã dừng",
  COMPLETED: "Hoàn tất",
  FAILED: "Thất bại",
  INTERRUPTED: "Bị gián đoạn",
  NOT_FOUND: "Thất bại",
  SENT: "Đã gửi",
  SEARCHING: "Đang tìm",
  OPENING_CHAT: "Đang mở chat",
  SENDING: "Đang gửi",
  SKIPPED: "Đã bỏ qua",
};

const state = {
  activeCategory: "all",
  search: "",
  favorites: new Set(JSON.parse(localStorage.getItem("toolsuite:favorites") || "[]")),
  previewRows: [],
  previewColumns: [],
  previewFilter: "ALL",
  bulkImages: [],
  currentJobId: null,
  pollTimer: null,
};

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function translateMessage(message) {
  if (!message) return "";
  const exact = {
    "Automation is busy": "Automation đang bận",
    "Another job is already active": "Đang có phiên gửi khác hoạt động",
    "Message cannot be empty": "Tin nhắn không được để trống",
    "Message is too long": "Tin nhắn quá dài",
    "No valid recipients": "Không có người nhận hợp lệ",
    "Job not found": "Không tìm thấy phiên gửi",
    "Only .xlsx files are supported": "Chỉ hỗ trợ file .xlsx",
    "Cannot read Excel file. Ensure it is a valid .xlsx workbook.": "Không đọc được file Excel. Hãy kiểm tra file .xlsx.",
    "Internal server error": "Lỗi máy chủ nội bộ",
  };
  if (exact[message]) return exact[message];
  if (message.includes("Invalid Vietnamese mobile phone number")) return "Số điện thoại Việt Nam không hợp lệ";
  if (message.includes("Invalid phone")) return message.replace("Invalid phone", "Số điện thoại không hợp lệ");
  if (message.includes("File exceeds")) return message.replace("File exceeds", "File vượt quá");
  if (message.includes("Target page, context or browser has been closed")) {
    return "Trình duyệt automation đã bị đóng trong lúc mở Zalo. Bấm Mở Zalo để thử lại.";
  }
  if (message.includes("Automation is busy. Wait for the current action to finish.")) {
    return "Automation đang bận. Vui lòng chờ thao tác hiện tại hoàn tất.";
  }
  return message;
}

function translateLog(message) {
  if (!message) return "";
  return message
    .replace(/^Job created with (\d+) recipients$/, "Đã tạo phiên gửi với $1 người nhận")
    .replace(/^Job started$/, "Phiên gửi đã bắt đầu")
    .replace(/^Job completed$/, "Phiên gửi đã hoàn tất")
    .replace(/^Job stopped by user$/, "Phiên gửi đã dừng theo yêu cầu")
    .replace(/^Stop requested$/, "Đã yêu cầu dừng")
    .replace(/ sending attempt /g, " đang gửi, lần thử ")
    .replace(/ sent$/g, " đã gửi")
    .replace(/ temporary error, retry queued: /g, " lỗi tạm thời, đã đưa vào hàng chờ thử lại: ")
    .replace(/ requires manual action: /g, " cần thao tác thủ công: ");
}

async function api(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeout || 30000);
  try {
    const response = await fetch(path, { ...options, signal: controller.signal });
    const contentType = response.headers.get("content-type") || "";
    const body = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      const detail = typeof body === "object" ? body.detail || body.message : "";
      if (response.status === 401 && detail === "Authentication required" && window.location.pathname !== "/login") {
        window.location.href = "/login";
        throw new Error("Vui lòng đăng nhập lại");
      }
      throw new Error(translateMessage(detail || `HTTP ${response.status}`));
    }
    return body;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("Yêu cầu quá thời gian chờ. Vui lòng thử lại.");
    }
    if (error instanceof TypeError && error.message === "Failed to fetch") {
      throw new Error("Mất kết nối tới server. Kiểm tra server Python hoặc Cloudflare Tunnel rồi thử lại.");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

function badge(value) {
  return `<span class="badge ${escapeHtml(value)}">${escapeHtml(labels[value] || value)}</span>`;
}

function setResult(id, text, ok = true) {
  const el = $(id);
  if (!el) return;
  el.textContent = text;
  el.style.color = ok ? "var(--green)" : "var(--red)";
}

function saveFavorites() {
  localStorage.setItem("toolsuite:favorites", JSON.stringify([...state.favorites]));
}

function navigate(path) {
  if (window.location.pathname !== path) {
    history.pushState({}, "", path);
  }
  render();
}

function routeForCategory(categoryId) {
  state.activeCategory = categoryId;
  if (categoryId === "all") {
    navigate("/");
  } else if (categoryId === "zalo") {
    navigate("/tools/zalo");
  } else {
    navigate(`/tools/${categoryId}`);
  }
}

function filteredTools() {
  const keyword = state.search.trim().toLowerCase();
  return tools.filter((tool) => {
    const matchCategory = state.activeCategory === "all" || tool.category === state.activeCategory;
    const matchSearch = !keyword || `${tool.name} ${tool.description}`.toLowerCase().includes(keyword);
    return matchCategory && matchSearch;
  });
}

function renderCategoryNav() {
  const nav = $("categoryNav");
  if (!nav) return;
  nav.innerHTML = categories
    .map(
      (category) => `
        <button class="sidebar-item ${state.activeCategory === category.id ? "active" : ""}" type="button" data-category="${category.id}">
          <span class="nav-icon logo-tile"><img src="${category.logo}" alt="" /></span>
          <span>${category.name}</span>
        </button>
      `,
    )
    .join("");
  nav.querySelectorAll("[data-category]").forEach((button) => {
    button.addEventListener("click", () => routeForCategory(button.dataset.category));
  });
}

function renderHome() {
  renderCategoryNav();
  const app = $("app");
  const visibleTools = filteredTools();
  app.innerHTML = `
    <section class="hero">
      <div class="hero-copy">
        <h1>Nền tảng <span class="gradient-text">công cụ số</span><br />toàn diện cho mọi nhu cầu</h1>
        <p>Tối ưu công việc trên Zalo, Facebook, TikTok, Shopee và sáng tạo video AI chuyên nghiệp.</p>
        <div class="hero-actions">
          <button id="exploreToolsBtn" class="btn btn-primary hero-btn" type="button">
            <span>Khám phá công cụ</span>
            <span class="btn-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false">
                <path class="icon-stroke" d="M12 3.75a8.25 8.25 0 1 0 0 16.5 8.25 8.25 0 0 0 0-16.5Z"/>
                <path class="icon-fill" d="m15.65 8.35-1.88 5.42-5.42 1.88 1.88-5.42 5.42-1.88Z"/>
              </svg>
            </span>
          </button>
          <button id="guideBtn" class="btn btn-outline hero-btn" type="button">
            <span>Xem hướng dẫn</span>
            <span class="btn-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false">
                <circle class="icon-stroke" cx="12" cy="12" r="8.25"/>
                <path class="icon-fill" d="M10.25 8.65v6.7L15.7 12l-5.45-3.35Z"/>
              </svg>
            </span>
          </button>
        </div>
      </div>
    </section>

    <section class="tool-category-page all-tools-page">
      <div class="section-header">
        <div>
          <div class="section-kicker"><span class="fire">♦</span><h2>Tất cả công cụ</h2></div>
          <p>${state.search ? `Kết quả phù hợp với “${escapeHtml(state.search)}”.` : "Toàn bộ tool đang có trong hệ thống."}</p>
        </div>
      </div>
      ${visibleTools.length ? `<div class="tool-grid">${visibleTools.map(renderToolCard).join("")}</div>` : renderEmptyState()}
    </section>
  `;
  bindHomeEvents();
  bindToolCardEvents("home");
}

function renderZaloCategoryPage() {
  renderCategoryNav();
  $("app").innerHTML = `
    <section class="tool-category-page">
      <div class="section-header">
        <div>
          <div class="section-kicker"><span class="fire">♦</span><h2>Zalo</h2></div>
          <p>Công cụ Zalo đang phát triển trong hệ thống.</p>
        </div>
      </div>
      <div class="tool-grid">${tools.map(renderToolCard).join("")}</div>
    </section>
  `;
  bindToolCardEvents();
}

function renderToolCard(tool) {
  const favorite = state.favorites.has(tool.id);
  return `
    <article class="tool-card ${tool.enabled ? "" : "disabled"}" data-tool-id="${tool.id}">
      <span class="tool-icon logo-tile" aria-hidden="true"><img src="${tool.logo}" alt="" /></span>
      <div>
        <h3>${escapeHtml(tool.name)}</h3>
        <p>${escapeHtml(tool.description)}</p>
      </div>
      <button class="favorite-btn ${favorite ? "active" : ""}" type="button" data-favorite="${tool.id}" aria-label="Yêu thích ${escapeHtml(tool.name)}">☆</button>
      <button class="tool-action" type="button" data-open-tool="${tool.id}">${tool.enabled ? "Sử dụng" : "Sắp ra mắt"} <span>›</span></button>
    </article>
  `;
}

function renderEmptyState() {
  return `<div class="empty-state"><div>Không tìm thấy công cụ phù hợp.</div></div>`;
}

function bindHomeEvents() {
  $("exploreToolsBtn")?.addEventListener("click", () => navigate("/tools/zalo"));
  $("guideBtn")?.addEventListener("click", () => navigate("/tools/zalo"));
}

function bindToolCardEvents() {
  document.querySelectorAll("[data-open-tool]").forEach((button) => {
    button.addEventListener("click", () => {
      const tool = tools.find((item) => item.id === button.dataset.openTool);
      if (!tool || !tool.enabled) return;
      navigate(tool.route);
    });
  });
  document.querySelectorAll("[data-favorite]").forEach((button) => {
    button.addEventListener("click", () => {
      const id = button.dataset.favorite;
      if (state.favorites.has(id)) state.favorites.delete(id);
      else state.favorites.add(id);
      saveFavorites();
      if (window.location.pathname === "/tools/zalo") renderZaloCategoryPage();
      else renderHome();
    });
  });
}

function renderZaloPage() {
  $("app").innerHTML = `
    <section class="zalo-page">
      <div class="zalo-command-bar">
        <div class="zalo-command-title">
          <div class="brand-logo-lockup">
            <img src="/static/assets/logo-hoi-doanh-nhan-mark.png?v=20260826-1" alt="Hội Doanh Nhân Họ Hoàng - Huỳnh Việt Nam" />
          </div>
          <div>
            <div class="brand-copy">
              <strong>Hội Doanh Nhân</strong>
              <span>Họ Hoàng - Huỳnh Việt Nam</span>
            </div>
            <h1>Tool Zalo kết bạn và tự động gửi tin nhắn</h1>
            <p>Quản lý danh sách, kết nối Zalo Web và theo dõi phiên gửi trong một màn hình.</p>
          </div>
        </div>
        <div class="zalo-actions">
          <button id="openZaloBtn" class="btn btn-primary" type="button">Mở Zalo</button>
          <button id="refreshStatusBtn" class="btn btn-secondary" type="button">Làm mới</button>
          <button id="logoutBtn" class="btn btn-secondary" type="button">Đăng xuất</button>
        </div>
      </div>

      <section class="zalo-status-strip">
        <div class="status-tile status-tile-compact"><span>Trình duyệt</span><strong id="browserStatus">Đang kiểm tra</strong></div>
        <div class="status-tile status-tile-compact"><span>Zalo</span><strong id="zaloStatus">Đang kiểm tra</strong></div>
        <div class="status-tile status-tile-compact"><span>Chế độ</span><strong id="modeStatus">Cục bộ</strong></div>
        <div id="zaloProfileCard" class="zalo-profile-card">
          <div id="zaloProfileAvatar" class="zalo-profile-avatar">Z</div>
          <div>
            <span>Tài khoản Zalo</span>
            <strong id="zaloProfileName">Chưa liên kết</strong>
          </div>
        </div>
      </section>

      <div class="zalo-workflow-grid">
        <section class="panel workflow-panel recipients-panel">
          <div class="panel-title">
            <div>
              <h2>Danh sách người nhận</h2>
              <span id="recipientCounter" class="counter-line">Đã chọn 0 người nhận</span>
            </div>
            <div class="inline-actions">
              <button id="selectAllBtn" class="btn btn-secondary" type="button">Chọn tất cả</button>
              <button id="unselectAllBtn" class="btn btn-secondary" type="button">Bỏ chọn</button>
            </div>
          </div>

          <div class="excel-import-box" id="excelDropZone">
            <input id="excelFile" class="file-input-hidden" type="file" accept=".xlsx" />
            <label for="excelFile" class="excel-drop-target">
              <span class="drop-icon">XLSX</span>
              <strong>Kéo thả file Excel</strong>
              <span id="fileNameLabel">hoặc bấm để chọn file .xlsx</span>
            </label>
            <div class="drive-import">
              <label class="field">
                Link Google Drive
                <input id="driveLink" type="url" placeholder="Dán link file Excel từ Google Drive" />
              </label>
              <button id="uploadBtn" class="btn btn-secondary" type="button">Tải lên và xem trước</button>
            </div>
          </div>

          <div class="preview-toolbar">
            <div id="excelStats" class="stats-line"></div>
            <div class="preview-filter-bar">
              <span>Bộ lọc</span>
              <button class="filter-chip active" type="button" data-preview-filter="ALL">Tất cả</button>
              <button class="filter-chip" type="button" data-preview-filter="VALID">Hợp lệ</button>
              <button class="filter-chip" type="button" data-preview-filter="DUPLICATE">Trùng số</button>
              <button class="filter-chip" type="button" data-preview-filter="INVALID">Lỗi</button>
            </div>
          </div>

          <div class="table-wrap preview-table-wrap">
            <table>
              <thead id="previewHead"></thead>
              <tbody id="previewRows"></tbody>
            </table>
          </div>
        </section>

        <aside class="workflow-side">
          <section class="panel send-panel">
            <div class="panel-title"><h2>Nội dung gửi</h2></div>
            <label class="field wide">
              Tin nhắn hàng loạt
              <textarea id="bulkMessage" rows="7" placeholder="Nhập nội dung gửi hàng loạt"></textarea>
            </label>
            <div class="image-import-box" id="imageDropZone">
              <input id="bulkImages" class="file-input-hidden" type="file" accept="image/*" multiple />
              <label for="bulkImages" class="image-drop-target">
                <span class="image-drop-icon">IMG</span>
                <strong>Gửi kèm hình ảnh</strong>
                <span id="imageFileLabel">Kéo thả ảnh hoặc bấm để chọn nhiều ảnh</span>
              </label>
              <div id="imagePreviewList" class="image-preview-list"></div>
              <button id="clearImagesBtn" class="btn btn-secondary image-clear-btn" type="button" hidden>Xóa ảnh đã chọn</button>
            </div>
            <div class="send-action-row">
              <button id="startJobBtn" class="btn btn-primary" type="button">Bắt đầu gửi</button>
              <button id="resumeJobBtn" class="btn btn-secondary" type="button" hidden>Tiếp tục</button>
              <button id="stopJobBtn" class="btn btn-danger" type="button" disabled>Dừng</button>
            </div>
          </section>

          <section class="panel progress-panel">
            <div class="panel-title">
              <h2>Tiến độ</h2>
              <span id="currentJobLabel">Chưa có phiên gửi đang chạy</span>
            </div>
            <div class="progress"><div id="progressBar"></div></div>
            <div class="progress-metrics">
              <div class="status-tile"><span>Đã xử lý</span><strong id="processedCount">0/0</strong></div>
              <div class="status-tile"><span>Đã gửi</span><strong id="sentCount">0</strong></div>
              <div class="status-tile"><span>Thất bại</span><strong id="failedCount">0</strong></div>
            </div>
            <div class="logs" id="logs"></div>
          </section>
        </aside>

        <section class="panel history-panel">
          <div class="panel-title">
            <h2>Lịch sử gửi</h2>
            <button id="refreshJobsBtn" class="btn btn-secondary" type="button">Tải lại</button>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Mã</th>
                  <th>Trạng thái</th>
                  <th>Tổng</th>
                  <th>Thành công</th>
                  <th>Thất bại</th>
                  <th>Xuất file</th>
                </tr>
              </thead>
              <tbody id="jobRows"></tbody>
            </table>
          </div>
        </section>
      </div>
    </section>
  `;
  bindZaloEvents();
  refreshStatus();
  loadJobs();
}

function renderPlaceholderPage(categoryId) {
  renderCategoryNav();
  const category = categories.find((item) => item.id === categoryId) || { name: "Công cụ" };
  $("app").innerHTML = `
    <section class="placeholder-panel">
      <h1>${escapeHtml(category.name)}</h1>
      <p>Đang cập nhật.</p>
      <button class="btn btn-primary" type="button" data-route="/">Quay lại trang chủ</button>
    </section>
  `;
  $("app").querySelector("[data-route='/']").addEventListener("click", () => navigate("/"));
}

function bindZaloEvents() {
  $("openZaloBtn")?.addEventListener("click", openZalo);
  $("refreshStatusBtn")?.addEventListener("click", refreshStatus);
  $("logoutBtn")?.addEventListener("click", logout);
  $("uploadBtn")?.addEventListener("click", uploadExcel);
  $("excelFile")?.addEventListener("change", () => {
    updateExcelFileLabel($("excelFile").files[0]);
  });
  bindExcelDropZone();
  $("bulkImages")?.addEventListener("change", () => updateBulkImages(Array.from($("bulkImages").files || [])));
  $("clearImagesBtn")?.addEventListener("click", clearBulkImages);
  bindImageDropZone();
  $("startJobBtn")?.addEventListener("click", startJob);
  $("resumeJobBtn")?.addEventListener("click", resumeJob);
  $("stopJobBtn")?.addEventListener("click", stopJob);
  $("refreshJobsBtn")?.addEventListener("click", loadJobs);
  $("selectAllBtn")?.addEventListener("click", () => setAllSelection(true));
  $("unselectAllBtn")?.addEventListener("click", () => setAllSelection(false));
  document.querySelectorAll("[data-preview-filter]").forEach((button) => {
    button.addEventListener("click", () => {
      state.previewFilter = button.dataset.previewFilter || "ALL";
      renderPreview();
    });
  });
}

async function refreshStatus() {
  if (!$("browserStatus") || !$("zaloStatus")) return;
  try {
    const data = await api("/api/zalo/status", { timeout: 10000 });
    $("browserStatus").innerHTML = badge(data.browser ? "CONNECTED" : "DISCONNECTED");
    $("zaloStatus").innerHTML = badge(data.status || "UNKNOWN");
    renderZaloProfile(data);
  } catch {
    $("browserStatus").innerHTML = badge("DISCONNECTED");
    $("zaloStatus").innerHTML = badge("ERROR");
    renderZaloProfile({ zalo_login: false, profile: null });
  }
}

function renderZaloProfile(data) {
  const card = $("zaloProfileCard");
  const avatar = $("zaloProfileAvatar");
  const name = $("zaloProfileName");
  if (!card || !avatar || !name) return;

  const profile = data?.profile || {};
  const connected = Boolean(data?.zalo_login || data?.status === "LOGGED_IN");
  const displayName = connected ? profile.name || "Zalo đã liên kết" : "Chưa liên kết";
  const avatarUrl = connected ? profile.avatar_url : "";

  card.classList.toggle("connected", connected);
  name.textContent = displayName;
  if (avatarUrl) {
    avatar.innerHTML = `<img src="${escapeHtml(avatarUrl)}" alt="" />`;
  } else {
    avatar.textContent = connected ? getInitials(displayName) : "Z";
  }
}

function getInitials(value) {
  const parts = String(value || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!parts.length) return "Z";
  const first = parts[0][0] || "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] || "" : "";
  return `${first}${last}`.toUpperCase();
}

async function openZalo() {
  const button = $("openZaloBtn");
  button.disabled = true;
  try {
    await api("/api/zalo/open", { method: "POST", timeout: 45000 });
    await refreshStatus();
  } catch (error) {
    alert(translateMessage(error.message));
  } finally {
    button.disabled = false;
  }
}

async function logout() {
  await api("/api/auth/logout", { method: "POST", timeout: 10000 });
  window.location.href = "/login";
}

async function uploadExcel() {
  const file = $("excelFile").files[0];
  const driveLink = $("driveLink")?.value.trim();
  if (!file && !driveLink) {
    alert("Kéo thả file Excel hoặc nhập link Google Drive");
    return;
  }
  try {
    let data;
    if (file) {
      const form = new FormData();
      form.append("file", file);
      data = await api("/api/excel/upload", { method: "POST", body: form, timeout: 45000 });
    } else {
      data = await api("/api/excel/import-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: driveLink }),
        timeout: 60000,
      });
    }
    applyExcelPreview(data);
  } catch (error) {
    $("excelStats").textContent = translateMessage(error.message);
    state.previewRows = [];
    state.previewColumns = [];
    renderPreview();
  }
}

function bindExcelDropZone() {
  const zone = $("excelDropZone");
  const input = $("excelFile");
  if (!zone || !input) return;
  ["dragenter", "dragover"].forEach((eventName) => {
    zone.addEventListener(eventName, (event) => {
      event.preventDefault();
      zone.classList.add("drag-over");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    zone.addEventListener(eventName, (event) => {
      event.preventDefault();
      zone.classList.remove("drag-over");
    });
  });
  zone.addEventListener("drop", (event) => {
    const file = [...(event.dataTransfer?.files || [])].find((item) => item.name.toLowerCase().endsWith(".xlsx"));
    if (!file) {
      alert("Chỉ hỗ trợ file .xlsx");
      return;
    }
    const transfer = new DataTransfer();
    transfer.items.add(file);
    input.files = transfer.files;
    if ($("driveLink")) $("driveLink").value = "";
    updateExcelFileLabel(file);
  });
}

function updateExcelFileLabel(file) {
  if ($("fileNameLabel")) {
    $("fileNameLabel").textContent = file?.name || "hoặc bấm để chọn file .xlsx";
  }
  if (file && $("driveLink")) {
    $("driveLink").value = "";
  }
}

function bindImageDropZone() {
  const zone = $("imageDropZone");
  if (!zone) return;
  ["dragenter", "dragover"].forEach((eventName) => {
    zone.addEventListener(eventName, (event) => {
      event.preventDefault();
      zone.classList.add("drag-over");
    });
  });
  ["dragleave", "drop"].forEach((eventName) => {
    zone.addEventListener(eventName, (event) => {
      event.preventDefault();
      zone.classList.remove("drag-over");
    });
  });
  zone.addEventListener("drop", (event) => {
    const files = Array.from(event.dataTransfer?.files || []);
    updateBulkImages(files);
  });
}

function updateBulkImages(files) {
  const images = files.filter((file) => file.type.startsWith("image/"));
  state.bulkImages = images.slice(0, 8);
  renderBulkImages();
}

function clearBulkImages() {
  state.bulkImages = [];
  if ($("bulkImages")) $("bulkImages").value = "";
  renderBulkImages();
}

function renderBulkImages() {
  const label = $("imageFileLabel");
  const list = $("imagePreviewList");
  const clearButton = $("clearImagesBtn");
  const images = state.bulkImages || [];
  if (label) {
    label.textContent = images.length ? `Đã chọn ${images.length} hình ảnh` : "Kéo thả ảnh hoặc bấm để chọn nhiều ảnh";
  }
  if (clearButton) clearButton.hidden = !images.length;
  if (!list) return;
  list.innerHTML = images
    .map(
      (file) => `
        <div class="image-preview-item">
          <span>${escapeHtml(file.name)}</span>
          <small>${formatFileSize(file.size)}</small>
        </div>
      `
    )
    .join("");
}

function formatFileSize(bytes) {
  if (!Number.isFinite(bytes)) return "";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function applyExcelPreview(data) {
  state.previewRows = data.rows || [];
  state.previewColumns = data.columns || [];
  state.previewFilter = "ALL";
  $("excelStats").textContent = `${data.filename} | tổng số điện thoại ${data.total_rows} | hợp lệ ${data.valid} | không hợp lệ ${data.invalid} | trùng ${data.duplicates}`;
  renderPreview();
}

function renderPreview() {
  const tbody = $("previewRows");
  if (!tbody) return;
  renderPreviewHead();
  updatePreviewFilterButtons();
  const visibleRows = state.previewFilter === "ALL" ? state.previewRows : state.previewRows.filter((row) => row.status === state.previewFilter);
  tbody.innerHTML = visibleRows
    .map(
      (row) => `
        <tr>
          <td><input type="checkbox" data-row="${row.index}" ${row.selected ? "checked" : ""} ${row.status !== "VALID" ? "disabled" : ""}></td>
          <td>${row.index}</td>
          ${state.previewColumns.map((column) => `<td>${escapeHtml(row.data?.[column] ?? "")}</td>`).join("")}
          <td>${badge(row.status)}</td>
        </tr>
      `,
    )
    .join("");
  tbody.querySelectorAll("input[type='checkbox']").forEach((box) => {
    box.addEventListener("change", (event) => {
      const row = state.previewRows.find((item) => item.index === Number(event.target.dataset.row));
      if (row) row.selected = event.target.checked;
      updateRecipientCounter();
    });
  });
  updateRecipientCounter();
}

function renderPreviewHead() {
  const head = $("previewHead");
  if (!head) return;
  const columns = state.previewColumns.length ? state.previewColumns : ["Số điện thoại", "Tên"];
  head.innerHTML = `
    <tr>
      <th></th>
      <th>STT</th>
      ${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}
      <th>Trạng thái</th>
    </tr>
  `;
}

function updatePreviewFilterButtons() {
  document.querySelectorAll("[data-preview-filter]").forEach((button) => {
    button.classList.toggle("active", button.dataset.previewFilter === state.previewFilter);
  });
}

function selectedRecipients() {
  return state.previewRows.filter((row) => row.selected && row.status === "VALID").map((row) => ({ phone: row.phone, name: row.name }));
}

function updateRecipientCounter() {
  if ($("recipientCounter")) {
    $("recipientCounter").textContent = `Đã chọn ${selectedRecipients().length} người nhận`;
  }
}

async function startJob() {
  const recipients = selectedRecipients();
  const message = $("bulkMessage").value.trim();
  const images = state.bulkImages || [];
  if (!recipients.length) {
    alert("Không có người nhận hợp lệ được chọn");
    return;
  }
  if (!message && !images.length) {
    alert("Nhập nội dung tin nhắn hoặc chọn hình ảnh");
    return;
  }
  const imageText = images.length ? ` kèm ${images.length} hình ảnh` : "";
  if (!confirm(`Bạn chuẩn bị gửi cho ${recipients.length} người${imageText}.`)) {
    return;
  }
  const button = $("startJobBtn");
  button.disabled = true;
  try {
    const requestOptions = images.length
      ? buildBulkSendFormRequest(recipients, message, images)
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ recipients, message }),
          timeout: 30000,
        };
    const data = await api("/api/jobs/bulk-send", requestOptions);
    state.currentJobId = data.job_id;
    $("stopJobBtn").disabled = false;
    startPolling();
    await loadJobs();
  } catch (error) {
    alert(translateMessage(error.message));
  } finally {
    button.disabled = false;
  }
}

function buildBulkSendFormRequest(recipients, message, images) {
  const form = new FormData();
  form.append("payload", JSON.stringify({ recipients, message }));
  images.forEach((file) => form.append("images", file));
  return {
    method: "POST",
    body: form,
    timeout: 60000,
  };
}

function startPolling() {
  if (state.pollTimer) clearInterval(state.pollTimer);
  pollJob();
  state.pollTimer = setInterval(pollJob, 1500);
}

async function pollJob() {
  if (!state.currentJobId || !$("currentJobLabel")) return;
  try {
    const job = await api(`/api/jobs/${state.currentJobId}`, { timeout: 15000 });
    renderJob(job);
    if (["COMPLETED", "FAILED", "STOPPED", "INTERRUPTED", "LOGIN_REQUIRED", "USER_ACTION_REQUIRED"].includes(job.status)) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
      if ($("stopJobBtn")) $("stopJobBtn").disabled = true;
      await loadJobs();
    }
  } catch {
    clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
}

function renderJob(job) {
  $("currentJobLabel").innerHTML = `Phiên gửi #${job.id} ${badge(job.status)}`;
  $("progressBar").style.width = `${job.percent}%`;
  $("processedCount").textContent = `${job.processed}/${job.total}`;
  $("sentCount").textContent = job.success;
  $("failedCount").textContent = job.failed;
  const canResume = ["LOGIN_REQUIRED", "USER_ACTION_REQUIRED", "STOPPED", "FAILED"].includes(job.status) && job.pending > 0;
  if ($("resumeJobBtn")) $("resumeJobBtn").hidden = !canResume;
  if ($("stopJobBtn")) $("stopJobBtn").disabled = job.status !== "RUNNING";
  $("logs").innerHTML = (job.latest_logs || [])
    .map((line) => `<div class="log-line">${escapeHtml(line.created_at)} ${escapeHtml(line.level)} ${escapeHtml(translateLog(line.message))}</div>`)
    .join("");
}

async function resumeJob() {
  if (!state.currentJobId) return;
  const button = $("resumeJobBtn");
  button.disabled = true;
  try {
    await refreshStatus();
    await api(`/api/jobs/${state.currentJobId}/resume`, { method: "POST", timeout: 15000 });
    button.hidden = true;
    $("stopJobBtn").disabled = false;
    startPolling();
  } catch (error) {
    alert(translateMessage(error.message));
  } finally {
    button.disabled = false;
  }
}

async function stopJob() {
  if (!state.currentJobId) return;
  const button = $("stopJobBtn");
  button.disabled = true;
  try {
    await api(`/api/jobs/${state.currentJobId}/stop`, { method: "POST", timeout: 15000 });
    await pollJob();
  } catch (error) {
    alert(translateMessage(error.message));
    button.disabled = false;
  }
}

async function loadJobs() {
  if (!$("jobRows")) return;
  try {
    const rows = await api("/api/jobs", { timeout: 15000 });
    $("jobRows").innerHTML = rows
      .map(
        (job) => `
          <tr>
            <td><button class="btn btn-secondary job-link" data-id="${job.id}" type="button">#${job.id}</button></td>
            <td>${badge(job.status)}</td>
            <td>${job.total}</td>
            <td>${job.success}</td>
            <td>${job.failed}</td>
            <td><a href="/api/jobs/${job.id}/export">Xuất Excel</a></td>
          </tr>
        `,
      )
      .join("");
    document.querySelectorAll(".job-link").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.currentJobId = Number(btn.dataset.id);
        startPolling();
      });
    });
  } catch {
    $("jobRows").innerHTML = "";
  }
}

function setAllSelection(value) {
  state.previewRows.forEach((row) => {
    if (row.status === "VALID") row.selected = value;
  });
  renderPreview();
}

function render() {
  state.activeCategory = "zalo";
  renderZaloPage();
}

function bindShellEvents() {
  if (!$("globalSearch")) {
    window.addEventListener("popstate", render);
    return;
  }

  $("globalSearch").addEventListener("input", (event) => {
    state.search = event.target.value;
    state.activeCategory = "all";
    event.target.closest(".search-wrap").classList.toggle("has-value", Boolean(state.search));
    if (window.location.pathname !== "/" && window.location.pathname !== "/tools") {
      history.pushState({}, "", "/tools");
    }
    renderHome();
  });

  $("clearSearchBtn").addEventListener("click", () => {
    state.search = "";
    state.activeCategory = "all";
    $("globalSearch").value = "";
    $("globalSearch").closest(".search-wrap").classList.remove("has-value");
    renderHome();
  });

  $("themeToggle").addEventListener("click", () => {
    document.body.classList.toggle("dark");
    localStorage.setItem("toolsuite:theme", document.body.classList.contains("dark") ? "dark" : "light");
  });

  document.querySelectorAll("[data-route]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      navigate(link.dataset.route);
    });
  });

  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      $("globalSearch").focus();
    }
  });

  window.addEventListener("popstate", render);
}

function initTheme() {
  const saved = localStorage.getItem("toolsuite:theme");
  const preferDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  if (saved === "dark" || (!saved && preferDark)) {
    document.body.classList.add("dark");
  }
}

initTheme();
bindShellEvents();
render();
setInterval(refreshStatus, 5000);
