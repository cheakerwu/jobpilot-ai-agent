const DEFAULT_BASE_URL = "http://127.0.0.1:8787";
const MAX_TEXT_LENGTH = 48000;

const baseUrlInput = document.getElementById("base-url");
const connectButton = document.getElementById("connect-button");
const openAppButton = document.getElementById("open-app-button");
const captureButton = document.getElementById("capture-button");
const autoAnalyzeInput = document.getElementById("auto-analyze");
const useAiInput = document.getElementById("use-ai");
const accountStatus = document.getElementById("account-status");
const captureStatus = document.getElementById("capture-status");

init();

async function init() {
  const saved = await chrome.storage.local.get(["baseUrl", "token", "user"]);
  baseUrlInput.value = saved.baseUrl || DEFAULT_BASE_URL;
  renderAccount(saved.token, saved.user);

  baseUrlInput.addEventListener("change", saveBaseUrl);
  connectButton.addEventListener("click", connectJobPilot);
  openAppButton.addEventListener("click", openJobPilot);
  captureButton.addEventListener("click", captureCurrentPage);
}

async function saveBaseUrl() {
  await chrome.storage.local.set({ baseUrl: normalizeBaseUrl(baseUrlInput.value) });
}

async function openJobPilot() {
  const baseUrl = await getBaseUrl();
  await chrome.tabs.create({ url: `${baseUrl}/app` });
}

async function connectJobPilot() {
  setStatus(accountStatus, "正在查找已登录的 JobPilot 页面...", "info");
  const baseUrl = await getBaseUrl();
  const tab = await findJobPilotTab(baseUrl);
  if (!tab?.id) {
    setStatus(accountStatus, "没有找到已打开的 JobPilot 页面，请先打开并登录。", "error");
    return;
  }

  try {
    const [result] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: readJobPilotAuth,
    });
    const auth = result?.result || {};
    if (!auth.token) {
      setStatus(accountStatus, "当前 JobPilot 页面未登录，请登录后重试。", "error");
      return;
    }

    await chrome.storage.local.set({
      baseUrl,
      token: auth.token,
      user: auth.user || null,
    });
    renderAccount(auth.token, auth.user);
  } catch (error) {
    setStatus(accountStatus, `连接失败：${toMessage(error)}`, "error");
  }
}

async function captureCurrentPage() {
  const { token } = await chrome.storage.local.get(["token"]);
  if (!token) {
    setStatus(captureStatus, "请先连接已登录的 JobPilot 页面。", "error");
    return;
  }

  const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!activeTab?.id || !canCaptureUrl(activeTab.url || "")) {
    setStatus(captureStatus, "当前页面不能采集，请切到招聘岗位页面后再试。", "error");
    return;
  }

  captureButton.disabled = true;
  setStatus(captureStatus, "正在读取当前页面...", "info");

  try {
    const [result] = await chrome.scripting.executeScript({
      target: { tabId: activeTab.id },
      func: collectCurrentPage,
      args: [MAX_TEXT_LENGTH],
    });
    const captured = result?.result;
    if (!captured?.page_title && !captured?.selected_text && !captured?.page_text) {
      setStatus(captureStatus, "没有读到可保存的岗位内容。", "error");
      return;
    }

    const baseUrl = await getBaseUrl();
    const payload = {
      ...captured,
      auto_analyze: autoAnalyzeInput.checked,
      use_ai: useAiInput.checked,
    };
    setStatus(captureStatus, payload.auto_analyze ? "正在保存并分析..." : "正在保存...", "info");
    const response = await fetch(`${baseUrl}/api/imports/capture`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || !data.success) {
      setStatus(captureStatus, `保存失败：${data.detail || data.message || "请稍后再试"}`, "error");
      return;
    }

    const analysis = data.analysis;
    const suffix = analysis?.success
      ? `，匹配 ${analysis.data?.match_score ?? "-"} 分`
      : "";
    setStatus(captureStatus, `已保存：${data.job.title} · ${data.job.company}${suffix}`, "success");
  } catch (error) {
    setStatus(captureStatus, `采集失败：${toMessage(error)}`, "error");
  } finally {
    captureButton.disabled = false;
  }
}

async function findJobPilotTab(baseUrl) {
  const tabs = await chrome.tabs.query({});
  const normalizedBase = normalizeBaseUrl(baseUrl);
  return tabs.find((tab) => {
    const url = tab.url || "";
    return url === `${normalizedBase}/app` || url.startsWith(`${normalizedBase}/app?`) || url.startsWith(`${normalizedBase}/app#`);
  });
}

async function getBaseUrl() {
  const baseUrl = normalizeBaseUrl(baseUrlInput.value || DEFAULT_BASE_URL);
  baseUrlInput.value = baseUrl;
  await chrome.storage.local.set({ baseUrl });
  return baseUrl;
}

function renderAccount(token, user) {
  if (!token) {
    setStatus(accountStatus, "尚未连接", "muted");
    return;
  }
  const username = safeJson(user)?.username || user?.username || "已登录用户";
  setStatus(accountStatus, `已连接：${username}`, "success");
}

function readJobPilotAuth() {
  const token = window.localStorage.getItem("token");
  let user = null;
  try {
    user = JSON.parse(window.localStorage.getItem("user") || "null");
  } catch {
    user = null;
  }
  return { token, user };
}

function collectCurrentPage(maxTextLength) {
  const selection = String(window.getSelection?.() || "").trim();
  const metaDescription = document.querySelector('meta[name="description"]')?.content || "";
  const bodyText = document.body?.innerText || "";
  const pageText = clampText(bodyText, maxTextLength);
  const selectedText = clampText(selection || metaDescription || bodyText, maxTextLength);
  return {
    page_title: document.title || "",
    page_url: window.location.href,
    selected_text: selectedText,
    page_text: pageText,
  };
}

function canCaptureUrl(url) {
  if (!url) return false;
  return /^(https?:|file:)/i.test(url) && !url.startsWith("chrome://") && !url.startsWith("edge://");
}

function clampText(value, maxTextLength) {
  return String(value || "")
    .replace(/\u0000/g, " ")
    .replace(/[ \t\r\f\v]+/g, " ")
    .trim()
    .slice(0, maxTextLength);
}

function normalizeBaseUrl(value) {
  const url = String(value || DEFAULT_BASE_URL).trim().replace(/\/+$/, "");
  return url || DEFAULT_BASE_URL;
}

function setStatus(element, message, type) {
  element.textContent = message;
  element.className = `status ${type || "muted"}`;
}

function safeJson(value) {
  if (!value || typeof value !== "string") return value;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function toMessage(error) {
  return error?.message || String(error || "未知错误");
}
