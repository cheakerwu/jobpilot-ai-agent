const API_BASE = "/api";

// ── Auth ────────────────────────────────────────────────────────────────
function getToken() {
    return localStorage.getItem("token");
}

function getCurrentUser() {
    try { return JSON.parse(localStorage.getItem("user")); } catch { return null; }
}

function logout() {
    if (!confirm("确定要退出登录吗？")) return;
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    window.location.href = "/login";
}

function checkAuth() {
    if (!getToken()) {
        window.location.href = "/login";
        return false;
    }
    return true;
}

// 所有 /api/* 请求自动带 Authorization header，401 时跳转登录
const _origFetch = window.fetch.bind(window);
window.fetch = async function (url, options = {}) {
    const token = getToken();
    if (token && typeof url === "string" && url.startsWith("/api/")) {
        options.headers = options.headers || {};
        if (options.headers instanceof Headers) {
            options.headers.set("Authorization", `Bearer ${token}`);
        } else {
            options.headers["Authorization"] = `Bearer ${token}`;
        }
    }
    const res = await _origFetch(url, options);
    if (res.status === 401) {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        window.location.href = "/login";
    }
    return res;
};

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

const ANALYZER_LABELS = {
    hybrid: "AI + 规则混合",
    llm: "AI 深度分析",
    rule: "规则评分",
    rule_fallback: "规则评分",
};

function formatAnalyzerType(type) {
    return ANALYZER_LABELS[type] || type || "-";
}

function showToast(message, type = "success") {
    const colors = { success: "bg-emerald-600", error: "bg-red-600", info: "bg-indigo-600" };
    const icons = { success: "solar:check-circle-bold", error: "solar:close-circle-bold", info: "solar:info-circle-bold" };
    const toast = document.createElement("div");
    toast.className = `toast ${colors[type] || colors.info} text-white px-5 py-3 rounded-xl shadow-lg text-sm font-medium flex items-center gap-2`;
    toast.innerHTML = `<iconify-icon icon="${icons[type] || icons.info}" width="18"></iconify-icon>${escapeHtml(message)}`;
    document.body.appendChild(toast);
    setTimeout(() => { toast.style.opacity = "0"; toast.style.transition = "opacity 0.3s"; setTimeout(() => toast.remove(), 300); }, 3000);
}

function switchPage(page, target) {
    document.querySelectorAll("[id^='page-']").forEach((el) => el.classList.add("hidden"));
    document.getElementById(`page-${page}`).classList.remove("hidden");
    document.querySelectorAll(".nav-item").forEach((el) => el.classList.remove("nav-active"));
    if (target) target.classList.add("nav-active");

    // 离开分析页时销毁图表，防止 canvas 冲突
    if (document.getElementById("page-analytics")?.classList.contains("hidden") === false && page !== "analytics") {
        destroyChart("distribution");
        destroyChart("city");
        destroyChart("platform");
    }

    if (page === "jobs") loadJobs();
    if (page === "kanban") loadKanbanBoard();
    if (page === "evidence") loadEvidence();
    if (page === "runs") loadRuns();
    if (page === "analytics") loadSalaryAnalytics();
}

function goToPage(page) {
    const navItem = document.querySelector(`.nav-item[data-page="${page}"]`);
    switchPage(page, navItem);
}

async function loadOnboardingStatus() {
    const panel = document.getElementById("onboarding-panel");
    if (!panel) return;
    try {
        const res = await fetch(`${API_BASE}/onboarding/status`);
        const data = await res.json();
        if (!data.success) return;
        renderOnboardingPanel(data.data);
    } catch {}
}

function renderOnboardingPanel(status) {
    const panel = document.getElementById("onboarding-panel");
    if (!panel) return;
    const progress = Array.isArray(status.progress) ? status.progress : [];
    const next = status.next_step || {};
    const activeKey = next.key;

    if (status.is_complete) {
        panel.classList.add("hidden");
        panel.innerHTML = "";
        return;
    }

    panel.className = "mb-6 bg-white border border-slate-200 rounded-xl p-5";
    panel.innerHTML = `
        <div class="flex flex-col xl:flex-row xl:items-center justify-between gap-5">
            <div class="min-w-0">
                <div class="text-sm font-bold text-slate-900">当前进度</div>
                <div class="text-sm text-slate-500 mt-1">${escapeHtml(next.description || "")}</div>
            </div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-2 xl:w-[520px]">
                ${progress.map((item) => {
                    const active = item.key === activeKey;
                    const done = item.completed;
                    const cls = done
                        ? "bg-emerald-50 text-emerald-700 border-emerald-100"
                        : active
                            ? "bg-indigo-50 text-indigo-700 border-indigo-100"
                            : "bg-slate-50 text-slate-500 border-slate-100";
                    const icon = done ? "solar:check-circle-bold" : active ? "solar:play-circle-bold" : "solar:clock-circle-bold";
                    return `
                        <div class="border rounded-lg px-3 py-2 ${cls}">
                            <div class="flex items-center gap-1.5 text-xs font-semibold whitespace-nowrap">
                                <iconify-icon icon="${icon}" width="14"></iconify-icon>${escapeHtml(item.label)}
                            </div>
                            <div class="text-lg font-bold mt-1">${item.count ?? 0}</div>
                        </div>
                    `;
                }).join("")}
            </div>
            <button class="btn btn-primary justify-center xl:shrink-0" onclick="goToPage('${escapeHtml(next.action_page || "jobs")}')">
                <iconify-icon icon="solar:arrow-right-bold-duotone"></iconify-icon>${escapeHtml(next.action_label || "继续")}
            </button>
        </div>
    `;
}

async function loadStats() {
    const el = document.getElementById("stat-total");
    if (!el) return;
    const res = await fetch(`${API_BASE}/jobs/stats`);
    const data = await res.json();
    if (!data.success) return;
    const stats = data.data;
    el.textContent = stats.total ?? 0;
    document.getElementById("stat-new").textContent = stats.new ?? 0;
    document.getElementById("stat-analyzed").textContent = stats.analyzed ?? 0;
    document.getElementById("stat-recommended").textContent = stats.recommended ?? 0;
    document.getElementById("stat-applied").textContent = stats.applied ?? 0;
}

function renderJdConfidence(confidence) {
    const container = document.getElementById("smart-jd-confidence");
    if (!container) return;
    if (!confidence || Object.keys(confidence).length === 0) {
        container.innerHTML = "";
        return;
    }
    const labels = {
        title: "职位",
        company: "公司",
        city: "城市",
        salary: "薪资",
        url: "链接",
        description: "描述",
        requirements: "要求",
    };
    container.innerHTML = Object.entries(labels).map(([key, label]) => {
        const ok = confidence?.[key] === "auto_extracted";
        const cls = ok ? "confidence-auto" : "confidence-missing";
        const text = ok ? "已识别" : "待补充";
        return `<span class="confidence-pill ${cls}">${escapeHtml(label)} · ${escapeHtml(text)}</span>`;
    }).join("");
}

function fillSmartJdForm(parsed) {
    const form = document.getElementById("smart-jd-import-form");
    if (!form) return;
    ["title", "company", "city", "salary", "url", "description", "requirements"].forEach((field) => {
        const input = form.querySelector(`[name="${field}"]`);
        if (input) input.value = parsed?.[field] || "";
    });
}

async function parseJdText() {
    const raw = document.getElementById("smart-jd-raw-text")?.value.trim() || "";
    const result = document.getElementById("smart-jd-parse-result");
    const panel = document.getElementById("smart-jd-result-panel");
    if (!result || !panel) return;
    if (raw.length < 10) {
        result.textContent = "请先粘贴完整一些的 JD 内容。";
        showToast("JD 内容太短，先多粘贴一点", "info");
        return;
    }

    result.textContent = "正在识别...";
    try {
        const res = await fetch(`${API_BASE}/imports/parse-jd`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({text: raw}),
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
            result.textContent = `识别失败：${data.detail || data.message || "请稍后再试"}`;
            showToast(data.detail || data.message || "识别失败", "error");
            return;
        }
        fillSmartJdForm(data.parsed);
        renderJdConfidence(data.confidence);
        panel.classList.remove("hidden");
        result.textContent = "已识别，可在右侧校正后导入。";
    } catch {
        result.textContent = "识别失败，请检查网络或稍后重试。";
        showToast("识别失败", "error");
    }
}

async function quickImportJd(event) {
    event.preventDefault();
    const form = event.target;
    const result = document.getElementById("smart-jd-import-result");
    const formData = new FormData(form);
    const payload = {
        title: formData.get("title") || "",
        company: formData.get("company") || "",
        city: formData.get("city") || "",
        salary: formData.get("salary") || "",
        url: formData.get("url") || "",
        description: formData.get("description") || "",
        requirements: formData.get("requirements") || "",
        auto_analyze: formData.get("auto_analyze") === "on",
        use_ai: aiToggleEnabled,
    };
    result.textContent = payload.auto_analyze ? "正在导入并分析..." : "正在导入...";

    const res = await fetch(`${API_BASE}/imports/quick-import`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.success) {
        const analysis = data.analysis;
        if (analysis?.success) {
            result.textContent = `导入并分析完成：${data.job.title}，匹配 ${analysis.data?.match_score ?? "-"} 分`;
            if (analysis.ai_usage_count !== undefined) updateTrialUI(analysis.ai_usage_count);
        } else if (payload.auto_analyze && analysis) {
            result.textContent = `导入成功：${data.job.title}。分析未完成：${analysis.message || "请稍后手动分析"}`;
        } else {
            result.textContent = `导入成功：${data.job.title}`;
        }
        showToast(`已导入：${data.job.title}`);
        form.reset();
        document.getElementById("smart-jd-result-panel")?.classList.add("hidden");
        renderJdConfidence({});
        loadStats();
        loadOnboardingStatus();
    } else {
        result.textContent = `导入失败：${data.message || data.detail}`;
        showToast(data.message || data.detail || "导入失败", "error");
    }
}

async function importManual(event) {
    event.preventDefault();
    const form = event.target;
    const result = document.getElementById("manual-import-result");
    const payload = Object.fromEntries(new FormData(form).entries());
    result.textContent = "正在导入...";

    const res = await fetch(`${API_BASE}/imports/manual`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.success) {
        result.textContent = `导入成功：${data.job.title}`;
        showToast(`已导入：${data.job.title}`);
        form.reset();
        loadStats();
        loadOnboardingStatus();
    } else {
        result.textContent = `导入失败：${data.message || data.detail}`;
        showToast(data.message || data.detail || "导入失败", "error");
    }
}

async function importCsv(event) {
    event.preventDefault();
    const form = event.target;
    const result = document.getElementById("csv-import-result");
    const body = new FormData(form);
    result.textContent = "正在导入...";

    const res = await fetch(`${API_BASE}/imports/csv`, {method: "POST", body});
    const data = await res.json();
    if (data.success) {
        result.textContent = `导入完成：成功 ${data.success_count}，失败 ${data.failed_count}，跳过 ${data.skipped_count}`;
        showToast(`批量导入完成：${data.success_count} 条`);
        form.reset();
        loadStats();
        loadOnboardingStatus();
    } else {
        result.textContent = `导入失败：${data.message || data.detail}`;
        showToast(data.message || data.detail || "导入失败", "error");
    }
}

async function importJdPdf(event) {
    event.preventDefault();
    const form = event.target;
    const result = document.getElementById("pdf-jd-import-result");
    const body = new FormData(form);
    result.textContent = "正在识别 PDF JD...";

    const res = await fetch(`${API_BASE}/imports/pdf-jd`, {method: "POST", body});
    const data = await res.json();
    if (data.success) {
        result.textContent = `导入成功：${data.job.title} · ${data.job.company}`;
        showToast(`已导入：${data.job.title}`);
        form.reset();
        loadStats();
        loadOnboardingStatus();
    } else {
        result.textContent = `导入失败：${data.detail || data.message}`;
        showToast(data.detail || data.message || "导入失败", "error");
    }
}

let jobsCurrentPage = 1;
const JOBS_PER_PAGE = 20;

function getJobNextAction(job) {
    const status = job.status || "new";
    if (status === "new") {
        return {key: "analyze", label: "分析岗位", hint: "先看匹配与风险", icon: "solar:magic-stick-3-bold-duotone", handler: `analyzeJob(${job.id})`};
    }
    if (["analyzed", "recommended"].includes(status)) {
        return {key: "resume", label: "生成简历", hint: "产出定制版本", icon: "solar:document-text-bold-duotone", handler: `generateResume(${job.id})`};
    }
    if (status === "resume_generated") {
        return {key: "versions", label: "查看简历", hint: "复制或下载版本", icon: "solar:documents-bold-duotone", handler: `showResumeVersions(${job.id})`};
    }
    if (["to_apply", "applied", "screening"].includes(status)) {
        return {key: "cover", label: "生成求职信", hint: "补齐投递材料", icon: "solar:letter-bold-duotone", handler: `generateCoverLetter(${job.id})`};
    }
    if (status === "interviewing") {
        return {key: "prep", label: "面试准备", hint: "准备问题与回答", icon: "solar:notebook-bold-duotone", handler: `generateInterviewPrep(${job.id})`};
    }
    return {key: "analysis", label: "查看详情", hint: "回看匹配结论", icon: "solar:chart-2-bold-duotone", handler: `showAnalysis(${job.id})`};
}

function renderJobActionButtons(job, nextAction) {
    const actions = [
        {key: "analyze", label: "重析", icon: "solar:magic-stick-3-bold-duotone", handler: `analyzeJob(${job.id})`},
        {key: "analysis", label: "详情", icon: "solar:chart-2-bold-duotone", handler: `showAnalysis(${job.id})`},
        {key: "resume", label: "简历", icon: "solar:document-text-bold-duotone", handler: `generateResume(${job.id})`},
        {key: "versions", label: "版本", icon: "solar:documents-bold-duotone", handler: `showResumeVersions(${job.id})`},
        {key: "cover", label: "求职信", icon: "solar:letter-bold-duotone", handler: `generateCoverLetter(${job.id})`},
        {key: "prep", label: "面试", icon: "solar:notebook-bold-duotone", handler: `generateInterviewPrep(${job.id})`},
    ].filter((action) => action.key !== nextAction.key);

    return `
        <button class="btn btn-primary" onclick="${nextAction.handler}"><iconify-icon icon="${nextAction.icon}"></iconify-icon>${escapeHtml(nextAction.label)}</button>
        ${actions.map((action) => `
            <button class="btn btn-secondary" onclick="${action.handler}"><iconify-icon icon="${action.icon}"></iconify-icon>${escapeHtml(action.label)}</button>
        `).join("")}
    `;
}

async function loadJobs(page) {
    if (page !== undefined) jobsCurrentPage = page;
    const container = document.getElementById("jobs-list");
    container.innerHTML = "<div class='text-sm text-slate-500'>加载中...</div>";
    const res = await fetch(`${API_BASE}/jobs?page=${jobsCurrentPage}&per_page=${JOBS_PER_PAGE}`);
    const data = await res.json();
    if (!data.success || data.data.length === 0) {
        container.innerHTML = "<div class='card p-5 text-sm text-slate-500'>暂无岗位，先导入一条 JD。</div>";
        return;
    }

    const jobsHtml = data.data.map((job) => {
        const nextAction = getJobNextAction(job);
        return `
        <article class="card p-5">
            <div class="job-card-top flex items-start justify-between gap-4">
                <div class="min-w-0 flex-1">
                    <h3 class="font-bold text-sm">${escapeHtml(job.title)}</h3>
                    <p class="text-xs text-slate-500 mt-1">${escapeHtml(job.company)} · ${escapeHtml(job.city || "未知城市")} · ${escapeHtml(job.salary || "薪资未填")}</p>
                    <p class="text-xs text-slate-400 mt-1.5">
                        来源：${escapeHtml(job.source)} ·
                        状态：<span id="job-status-${job.id}" class="font-medium">${escapeHtml(job.status)}</span> ·
                        匹配分：<span id="job-score-${job.id}" class="font-medium">${job.match_score ?? "-"}</span>
                    </p>
                    <p class="text-xs text-indigo-600 mt-2">
                        建议下一步：<span class="font-semibold">${escapeHtml(nextAction.label)}</span>
                        <span class="text-slate-400"> · ${escapeHtml(nextAction.hint)}</span>
                    </p>
                </div>
                <div class="job-actions flex flex-wrap gap-1.5 shrink-0">
                    ${renderJobActionButtons(job, nextAction)}
                </div>
            </div>
            <div id="job-result-${job.id}" class="text-sm mt-3 text-slate-600"></div>
        </article>
    `;
    }).join("");

    const totalPages = Math.ceil((data.total || 0) / JOBS_PER_PAGE);
    let paginationHtml = "";
    if (totalPages > 1) {
        paginationHtml = `<div class="flex items-center justify-center gap-2 mt-4 py-3">`;
        if (jobsCurrentPage > 1) {
            paginationHtml += `<button class="btn btn-secondary text-xs" onclick="loadJobs(${jobsCurrentPage - 1})">上一页</button>`;
        }
        paginationHtml += `<span class="text-sm text-slate-500">第 ${jobsCurrentPage} / ${totalPages} 页（共 ${data.total} 条）</span>`;
        if (jobsCurrentPage < totalPages) {
            paginationHtml += `<button class="btn btn-secondary text-xs" onclick="loadJobs(${jobsCurrentPage + 1})">下一页</button>`;
        }
        paginationHtml += `</div>`;
    }

    container.innerHTML = jobsHtml + paginationHtml;
}

const SPINNER = '<iconify-icon icon="solar:spinner-bold-duotone" class="animate-spin"></iconify-icon>';

function setJobButtonsLoading(jobId, loading) {
    const container = document.querySelector(`#job-result-${jobId}`)?.closest("article");
    if (!container) return;
    const buttons = container.querySelectorAll(".btn");
    buttons.forEach((btn) => {
        btn.disabled = loading;
        btn.style.opacity = loading ? "0.5" : "";
        btn.style.pointerEvents = loading ? "none" : "";
    });
}

async function analyzeJob(jobId) {
    const result = document.getElementById(`job-result-${jobId}`);
    setJobButtonsLoading(jobId, true);
    result.innerHTML = `${SPINNER} Agent 正在分析...`;
    try {
        const res = await fetch(`${API_BASE}/analyses/jobs/${jobId}?use_ai=${aiToggleEnabled}`, {method: "POST"});
        const data = await res.json();
        if (res.status === 403) {
            result.textContent = data.detail || "AI 试用次数已用完";
            showToast("AI 试用次数已用完", "error");
            updateTrialUI(10);
            return;
        }
        if (data.success) {
            const analysis = data.data;
            result.innerHTML = renderAnalysisPanel(analysis);
            const newStatus = ["A", "B"].includes(analysis.recommendation_level) ? "recommended" : "analyzed";
            updateJobCardMeta(jobId, analysis.match_score, newStatus);
            loadStats();
            loadOnboardingStatus();
            if (data.ai_usage_count !== undefined) updateTrialUI(data.ai_usage_count);
        } else {
            result.textContent = `分析失败：${data.detail || data.message}`;
        }
    } finally {
        setJobButtonsLoading(jobId, false);
    }
}

async function showAnalysis(jobId) {
    const result = document.getElementById(`job-result-${jobId}`);
    result.textContent = "正在读取匹配详情...";
    const res = await fetch(`${API_BASE}/analyses/jobs/${jobId}/latest`);
    const data = await res.json();
    if (data.success) {
        result.innerHTML = renderAnalysisPanel(data.data);
    } else {
        result.textContent = data.detail || "该岗位还没有分析结果，请先点击分析。";
    }
}

async function generateResume(jobId) {
    const result = document.getElementById(`job-result-${jobId}`);
    setJobButtonsLoading(jobId, true);
    result.innerHTML = `${SPINNER} 正在生成简历版本...`;
    try {
        const res = await fetch(`${API_BASE}/resumes/generate`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({job_id: jobId, use_ai: aiToggleEnabled}),
        });
        const data = await res.json();
        if (res.status === 403) {
            result.textContent = data.detail || "AI 试用次数已用完";
            showToast("AI 试用次数已用完", "error");
            updateTrialUI(10);
            return;
        }
        result.innerHTML = data.success
            ? renderResumePanel(data.data)
            : `<div class="text-red-600">生成失败：${escapeHtml(data.detail || data.message)}</div>`;
        if (data.success) {
            updateJobCardMeta(jobId, null, "resume_generated");
            loadStats();
            loadOnboardingStatus();
            if (data.ai_usage_count !== undefined) updateTrialUI(data.ai_usage_count);
        }
    } finally {
        setJobButtonsLoading(jobId, false);
    }
}

function updateJobCardMeta(jobId, matchScore, status) {
    const scoreEl = document.getElementById(`job-score-${jobId}`);
    const statusEl = document.getElementById(`job-status-${jobId}`);
    if (scoreEl && matchScore !== null && matchScore !== undefined) {
        scoreEl.textContent = matchScore;
    }
    if (statusEl && status) {
        statusEl.textContent = status;
    }
}

async function showResumeVersions(jobId) {
    const result = document.getElementById(`job-result-${jobId}`);
    result.textContent = "正在读取简历版本...";
    const res = await fetch(`${API_BASE}/resumes/jobs/${jobId}`);
    const data = await res.json();
    if (!data.success) {
        result.textContent = data.detail || "读取失败";
        return;
    }
    if (!data.data.length) {
        result.textContent = "该岗位还没有简历版本，请先点击生成简历。";
        return;
    }
    result.innerHTML = renderResumePanel(data.data[0]);
}

function renderAnalysisPanel(analysis) {
    const explanation = analysis.score_explanation || {};
    const matched = Array.isArray(analysis.matched_evidence) ? analysis.matched_evidence : [];
    const gaps = Array.isArray(analysis.gaps) ? analysis.gaps : [];
    const risks = Array.isArray(analysis.risks) ? analysis.risks : [];
    const doNotExaggerate = Array.isArray(analysis.do_not_exaggerate) ? analysis.do_not_exaggerate : [];
    const requiredSkills = explanation.skill_requirements || analysis.parsed_jd?.required_skills || [];

    return `
        <div class="mt-4 border-t border-slate-100 pt-4 space-y-4">
            <div class="grid grid-cols-2 xl:grid-cols-4 gap-3">
                <div class="bg-slate-50 rounded-xl p-3"><div class="text-xs text-slate-500">推荐等级</div><div class="text-xl font-bold mt-1">${escapeHtml(analysis.recommendation_level || "-")}</div></div>
                <div class="bg-indigo-50 rounded-xl p-3"><div class="text-xs text-indigo-600">匹配分</div><div class="text-xl font-bold mt-1 text-indigo-700">${analysis.match_score ?? "-"}</div></div>
                <div class="bg-amber-50 rounded-xl p-3"><div class="text-xs text-amber-600">风险分</div><div class="text-xl font-bold mt-1 text-amber-700">${analysis.risk_score ?? "-"}</div></div>
                <div class="bg-slate-50 rounded-xl p-3"><div class="text-xs text-slate-500">分析器</div><div class="text-xl font-bold mt-1">${escapeHtml(formatAnalyzerType(analysis.analyzer_type))}</div></div>
            </div>
            <div>
                <div class="font-semibold text-slate-800">匹配结论</div>
                <p class="mt-1 text-slate-600">${escapeHtml(analysis.summary || "暂无总结")}</p>
                <p class="mt-1 text-slate-600">${escapeHtml(analysis.action_suggestion || "")}</p>
            </div>
            <div>
                <div class="font-semibold text-slate-800">评分机制</div>
                <p class="mt-1 text-slate-600">${escapeHtml(explanation.formula || "暂无评分说明")}</p>
                <p class="mt-1 text-slate-500">${escapeHtml(explanation.risk_rule || "")}</p>
            </div>
            <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
                <div>
                    <div class="font-semibold text-slate-800">JD 技能要求</div>
                    ${renderTagList(requiredSkills, "未识别到明确技能关键词")}
                </div>
                <div>
                    <div class="font-semibold text-slate-800">已匹配证据</div>
                    ${renderMatchedEvidence(matched)}
                </div>
            </div>
            <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
                <div>
                    <div class="font-semibold text-slate-800">简历可补强项</div>
                    ${renderGaps(gaps)}
                </div>
                <div>
                    <div class="font-semibold text-slate-800">风险与不要夸大</div>
                    ${renderRisks(risks, doNotExaggerate)}
                </div>
            </div>
        </div>
    `;
}

function renderTagList(items, emptyText) {
    if (!Array.isArray(items) || items.length === 0) {
        return `<p class="mt-2 text-slate-400">${escapeHtml(emptyText)}</p>`;
    }
    return `<div class="flex flex-wrap gap-2 mt-2">${items.map((item) => `
        <span class="px-2 py-1 rounded bg-blue-50 text-blue-700 text-xs">${escapeHtml(item)}</span>
    `).join("")}</div>`;
}

function renderMatchedEvidence(items) {
    if (!items.length) {
        return `<p class="mt-2 text-slate-400">暂无匹配证据。可以先在证据库导入 PDF 简历或手动补充项目经历。</p>`;
    }
    return `<ul class="mt-2 space-y-1.5">${items.map((item) => `
        <li class="bg-emerald-50 rounded-lg p-2.5">
            <span class="font-medium text-emerald-800 text-sm">${escapeHtml(item.requirement || "要求")}</span>
            <span class="text-emerald-600 text-sm"> → ${escapeHtml(item.evidence_title || `证据 #${item.evidence_id ?? "-"}`)}</span>
        </li>
    `).join("")}</ul>`;
}

function renderGaps(items) {
    if (!items.length) {
        return `<p class="mt-2 text-slate-400">暂无明显待补充项。</p>`;
    }
    return `<ul class="mt-2 space-y-1.5">${items.map((item) => `
        <li class="bg-amber-50 rounded-lg p-2.5">
            <div class="font-medium text-amber-800 text-sm">${escapeHtml(item.requirement || "缺口")}</div>
            <div class="text-amber-600 text-sm">${escapeHtml(item.suggestion || "")}</div>
        </li>
    `).join("")}</ul>`;
}

function renderRisks(risks, doNotExaggerate) {
    const riskItems = [
        ...risks.map((item) => item.point || item.requirement || ""),
        ...doNotExaggerate,
    ].filter(Boolean);
    if (!riskItems.length) {
        return `<p class="mt-2 text-slate-400">暂无明显风险提示。</p>`;
    }
    return `<ul class="mt-2 space-y-1.5">${riskItems.map((item) => `
        <li class="bg-red-50 rounded-lg p-2.5 text-red-600 text-sm">${escapeHtml(item)}</li>
    `).join("")}</ul>`;
}

function renderResumePanel(version) {
    const warnings = Array.isArray(version.risk_warnings) ? version.risk_warnings : [];
    const evidenceLinks = Array.isArray(version.evidence_links) ? version.evidence_links : [];
    const coverage = version.keyword_coverage && typeof version.keyword_coverage === "object"
        ? Object.entries(version.keyword_coverage)
        : [];
    return `
        <div class="mt-4 border-t border-slate-100 pt-4 space-y-4">
            <div class="flex items-center justify-between gap-4">
                <div>
                    <div class="font-semibold text-sm">简历版本 #${version.id}</div>
                    <div class="text-xs text-slate-500 mt-0.5">${escapeHtml(version.title || "")} · ${escapeHtml(version.created_at || "")}</div>
                </div>
                <div class="flex flex-wrap gap-2 shrink-0">
                    <button class="btn btn-secondary" onclick="copyResumeContent(${version.id})"><iconify-icon icon="solar:copy-bold-duotone"></iconify-icon>复制</button>
                    <button class="btn btn-secondary" onclick="downloadApiFile('/api/resumes/${version.id}/download', 'resume-${version.id}.md')"><iconify-icon icon="solar:download-bold-duotone"></iconify-icon>下载 MD</button>
                </div>
            </div>
            ${warnings.length ? `
                <div>
                    <div class="font-semibold text-sm text-slate-800">风险提示</div>
                    <ul class="mt-2 space-y-1.5">${warnings.map((item) => `<li class="bg-amber-50 rounded-lg p-2.5 text-amber-700 text-sm">${escapeHtml(item)}</li>`).join("")}</ul>
                </div>
            ` : ""}
            ${evidenceLinks.length ? `
                <div>
                    <div class="font-semibold text-sm text-slate-800">引用证据</div>
                    <ul class="mt-2 space-y-1.5">${evidenceLinks.slice(0, 8).map((item) => `
                        <li class="bg-emerald-50 rounded-lg p-2.5 text-emerald-700 text-sm">证据 #${escapeHtml(item.evidence_id)}：${escapeHtml(item.bullet_text || "")}</li>
                    `).join("")}</ul>
                </div>
            ` : ""}
            ${coverage.length ? `
                <div>
                    <div class="font-semibold text-sm text-slate-800">关键词覆盖</div>
                    <div class="flex flex-wrap gap-1.5 mt-2">${coverage.slice(0, 24).map(([key, value]) => `
                        <span class="px-2 py-1 rounded-lg text-xs font-medium ${value ? "bg-indigo-50 text-indigo-700" : "bg-slate-100 text-slate-500"}">${escapeHtml(key)} ${value ? "✓" : "×"}</span>
                    `).join("")}</div>
                </div>
            ` : ""}
            <div>
                <div class="font-semibold text-sm text-slate-800 mb-2">简历预览</div>
                <pre id="resume-content-${version.id}" class="bg-slate-950 text-slate-50 rounded-xl p-4 overflow-auto max-h-[560px] whitespace-pre-wrap text-sm leading-6">${escapeHtml(version.content || "")}</pre>
            </div>
        </div>
    `;
}

async function copyResumeContent(versionId) {
    const el = document.getElementById(`resume-content-${versionId}`);
    if (!el) return;
    await navigator.clipboard.writeText(el.innerText);
    showToast("已复制到剪贴板");
}

function getDownloadFilename(disposition, fallbackName) {
    if (!disposition) return fallbackName;
    const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (utf8Match) {
        try { return decodeURIComponent(utf8Match[1].replaceAll('"', "")); } catch {}
    }
    const asciiMatch = disposition.match(/filename="?([^";]+)"?/i);
    return asciiMatch ? asciiMatch[1] : fallbackName;
}

async function downloadApiFile(url, fallbackName) {
    try {
        const res = await fetch(url);
        if (!res.ok) {
            let message = "下载失败";
            try {
                const data = await res.json();
                message = data.detail || data.message || message;
            } catch {}
            showToast(message, "error");
            return;
        }
        const blob = await res.blob();
        const filename = getDownloadFilename(res.headers.get("Content-Disposition"), fallbackName);
        const href = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = href;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(href);
        showToast("文件已开始下载");
    } catch {
        showToast("下载失败", "error");
    }
}

async function loadEvidence() {
    const container = document.getElementById("evidence-list");
    container.innerHTML = "<div class='text-sm text-slate-500'>加载中...</div>";
    const res = await fetch(`${API_BASE}/evidence`);
    const data = await res.json();
    if (!data.success || data.data.length === 0) {
        container.innerHTML = "<div class='card p-5 text-sm text-slate-500'>暂无证据，点击上方按钮手动新增。</div>";
        return;
    }
    container.innerHTML = data.data.map((ev) => `
        <article class="card p-5">
            <div class="flex items-start justify-between gap-4">
                <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2">
                        <h3 class="font-bold text-sm">${escapeHtml(ev.title)}</h3>
                        <span class="px-2 py-0.5 rounded-md bg-slate-100 text-xs text-slate-500">${escapeHtml(ev.type)}</span>
                    </div>
                    <p class="text-xs text-slate-400 mt-1">${escapeHtml((ev.skill_tags || []).join(", ") || "无标签")}</p>
                    <p class="text-sm text-slate-600 mt-2 whitespace-pre-wrap leading-relaxed">${escapeHtml(ev.content || "")}</p>
                </div>
                <button class="btn btn-ghost text-red-500 hover:bg-red-50 hover:text-red-600" onclick="deleteEvidence(${ev.id})"><iconify-icon icon="solar:trash-bin-trash-bold-duotone"></iconify-icon></button>
            </div>
        </article>
    `).join("");
}

async function importResumePdf(event) {
    event.preventDefault();
    const form = event.target;
    const result = document.getElementById("resume-pdf-import-result");
    const body = new FormData(form);
    result.textContent = "正在识别 PDF 简历...";

    const res = await fetch(`${API_BASE}/evidence/import-resume-pdf`, {method: "POST", body});
    const data = await res.json();
    if (data.success) {
        result.textContent = `导入完成：新增 ${data.count} 条证据`;
        showToast(`已导入 ${data.count} 条证据`);
        form.reset();
        loadEvidence();
        loadOnboardingStatus();
    } else {
        result.textContent = `导入失败：${data.detail || data.message}`;
        showToast(data.detail || data.message || "导入失败", "error");
    }
}

async function createEvidence(event) {
    event.preventDefault();
    const form = event.target;
    const values = Object.fromEntries(new FormData(form).entries());
    const tags = values.skill_tags
        ? values.skill_tags.split(",").map((item) => item.trim()).filter(Boolean)
        : [];
    const payload = {...values, skill_tags: tags};
    const res = await fetch(`${API_BASE}/evidence`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.success) {
        form.reset();
        loadEvidence();
        loadOnboardingStatus();
        showToast("证据已保存");
    } else {
        showToast(data.detail || data.message || "保存失败", "error");
    }
}

async function deleteEvidence(id) {
    if (!confirm("确定要删除这条证据吗？")) return;
    const res = await fetch(`${API_BASE}/evidence/${id}`, {method: "DELETE"});
    const data = await res.json();
    if (data.success) {
        loadEvidence();
        loadOnboardingStatus();
        showToast("证据已删除");
    } else {
        showToast(data.detail || data.message || "删除失败", "error");
    }
}

async function loadRuns() {
    const container = document.getElementById("runs-list");
    container.innerHTML = "<div class='text-sm text-slate-500'>加载中...</div>";
    const res = await fetch(`${API_BASE}/agent-runs?limit=30`);
    const data = await res.json();
    if (!data.success || data.data.length === 0) {
        container.innerHTML = "<div class='card p-5 text-sm text-slate-500'>暂无 Agent 运行记录。</div>";
        return;
    }
    container.innerHTML = data.data.map((run) => {
        const statusColors = { completed: "bg-emerald-100 text-emerald-700", failed: "bg-red-100 text-red-700", running: "bg-amber-100 text-amber-700" };
        const statusClass = statusColors[run.status] || "bg-slate-100 text-slate-600";
        return `
        <article class="card p-5">
            <div class="flex items-center justify-between">
                <div>
                    <div class="flex items-center gap-2">
                        <h3 class="font-bold text-sm">#${run.id} ${escapeHtml(run.workflow_name)}</h3>
                        <span class="px-2 py-0.5 rounded-md text-xs font-medium ${statusClass}">${escapeHtml(run.status)}</span>
                    </div>
                    <p class="text-xs text-slate-500 mt-1">岗位 ID：${run.job_id ?? "-"} · 开始：${escapeHtml(run.started_at || "")}</p>
                    ${run.error_message ? `<p class="text-xs text-red-500 mt-1.5">${escapeHtml(run.error_message)}</p>` : ""}
                </div>
                <button class="btn btn-secondary" onclick="loadRunSteps(${run.id})"><iconify-icon icon="solar:list-check-bold-duotone"></iconify-icon>步骤</button>
            </div>
            <div id="run-steps-${run.id}" class="mt-3 text-sm"></div>
        </article>
        `;
    }).join("");
}

async function loadRunSteps(runId) {
    const container = document.getElementById(`run-steps-${runId}`);
    const res = await fetch(`${API_BASE}/agent-runs/${runId}/steps`);
    const data = await res.json();
    if (!data.success) {
        container.textContent = data.detail || "加载失败";
        return;
    }
    container.innerHTML = data.data.map((step) => `
        <div class="py-2 border-t border-slate-100">
            <span class="font-semibold">${escapeHtml(step.step_name)}</span>
            <span class="text-slate-500"> · ${escapeHtml(step.status)}</span>
            ${step.error_message ? `<span class="text-red-600"> · ${escapeHtml(step.error_message)}</span>` : ""}
        </div>
    `).join("");
}

// ── AI Trial Management ───────────────────────────────────────────────

const AI_TRIAL_LIMIT = 10;
let aiToggleEnabled = true;

function updateTrialUI(aiUsageCount) {
    const remaining = Math.max(0, AI_TRIAL_LIMIT - (aiUsageCount || 0));
    const sidebarEl = document.getElementById("sidebar-trial-count");
    const badge = document.getElementById("ai-trial-badge");

    if (sidebarEl) sidebarEl.textContent = remaining;

    if (remaining <= 0) {
        aiToggleEnabled = false;
        if (badge) {
            badge.className = "mb-3 px-3 py-2 bg-red-50 rounded-lg text-center";
            badge.innerHTML = '<span class="text-xs text-red-600 font-medium">AI 试用次数已用完</span>';
        }
    } else if (remaining <= 3) {
        if (badge) badge.className = "mb-3 px-3 py-2 bg-amber-50 rounded-lg text-center";
    }
}

// ── Cover Letter & Interview Prep ──────────────────────────────────────

async function generateCoverLetter(jobId) {
    const result = document.getElementById(`job-result-${jobId}`);
    setJobButtonsLoading(jobId, true);
    result.innerHTML = `${SPINNER} 正在生成 Cover Letter...`;
    try {
        const res = await fetch(`${API_BASE}/cover-letters/generate`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({job_id: jobId, use_ai: aiToggleEnabled}),
        });
        const data = await res.json();
        if (res.status === 403) {
            result.textContent = data.detail || "AI 试用次数已用完";
            showToast("AI 试用次数已用完", "error");
            updateTrialUI(10);
            return;
        }
        result.innerHTML = data.success
            ? renderCoverLetterPanel(data.data)
            : `<div class="text-red-600">生成失败：${escapeHtml(data.detail || data.message)}</div>`;
        if (data.success && data.ai_usage_count !== undefined) updateTrialUI(data.ai_usage_count);
    } finally {
        setJobButtonsLoading(jobId, false);
    }
}

function renderCoverLetterPanel(cl) {
    const evidenceLinks = Array.isArray(cl.evidence_links) ? cl.evidence_links : [];
    const highlights = Array.isArray(cl.highlights) ? cl.highlights : [];
    return `
        <div class="mt-4 border-t border-slate-100 pt-4 space-y-4">
            <div class="flex items-center justify-between gap-4">
                <div>
                    <div class="font-semibold text-sm">Cover Letter #${cl.id}</div>
                    <div class="text-xs text-slate-500 mt-0.5">${escapeHtml(cl.title || "")} · ${escapeHtml(cl.created_at || "")}</div>
                </div>
                <div class="flex flex-wrap gap-2 shrink-0">
                    <button class="btn btn-secondary" onclick="copyCoverLetterContent(${cl.id})"><iconify-icon icon="solar:copy-bold-duotone"></iconify-icon>复制</button>
                    <button class="btn btn-secondary" onclick="downloadApiFile('/api/cover-letters/${cl.id}/download', 'cover-letter-${cl.id}.md')"><iconify-icon icon="solar:download-bold-duotone"></iconify-icon>下载 MD</button>
                </div>
            </div>
            ${highlights.length ? `<div><div class="font-semibold text-sm text-slate-800">核心亮点</div><div class="flex flex-wrap gap-1.5 mt-2">${highlights.map((h) => `<span class="px-2 py-1 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-medium">${escapeHtml(h)}</span>`).join("")}</div></div>` : ""}
            ${evidenceLinks.length ? `<div><div class="font-semibold text-sm text-slate-800">引用证据</div><ul class="mt-2 space-y-1.5">${evidenceLinks.slice(0, 6).map((e) => `<li class="bg-emerald-50 rounded-lg p-2.5 text-emerald-700 text-sm">证据 #${escapeHtml(e.evidence_id)}：${escapeHtml(e.bullet_text || "")}</li>`).join("")}</ul></div>` : ""}
            <div>
                <div class="font-semibold text-sm text-slate-800 mb-2">求职信预览</div>
                <pre id="cover-letter-content-${cl.id}" class="bg-slate-950 text-slate-50 rounded-xl p-4 overflow-auto max-h-[400px] whitespace-pre-wrap text-sm leading-6">${escapeHtml(cl.content || "")}</pre>
            </div>
        </div>
    `;
}

async function copyCoverLetterContent(clId) {
    const el = document.getElementById(`cover-letter-content-${clId}`);
    if (!el) return;
    await navigator.clipboard.writeText(el.innerText);
    showToast("已复制到剪贴板");
}

async function generateInterviewPrep(jobId) {
    const result = document.getElementById(`job-result-${jobId}`);
    setJobButtonsLoading(jobId, true);
    result.innerHTML = `${SPINNER} 正在生成面试准备材料...`;
    try {
        const res = await fetch(`${API_BASE}/interview-prep/generate`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({job_id: jobId, use_ai: aiToggleEnabled}),
        });
        const data = await res.json();
        if (res.status === 403) {
            result.textContent = data.detail || "AI 试用次数已用完";
            showToast("AI 试用次数已用完", "error");
            updateTrialUI(10);
            return;
        }
        result.innerHTML = data.success
            ? renderInterviewPrepPanel(data.data)
            : `<div class="text-red-600">生成失败：${escapeHtml(data.detail || data.message)}</div>`;
        if (data.success && data.ai_usage_count !== undefined) updateTrialUI(data.ai_usage_count);
    } finally {
        setJobButtonsLoading(jobId, false);
    }
}

function renderInterviewPrepPanel(prep) {
    const questions = Array.isArray(prep.questions) ? prep.questions : [];
    const tips = Array.isArray(prep.preparation_tips) ? prep.preparation_tips : [];
    const risks = Array.isArray(prep.risk_areas) ? prep.risk_areas : [];
    const insights = prep.company_insights || {};
    const categoryColors = {
        "技术": "bg-blue-100 text-blue-700",
        "项目": "bg-indigo-100 text-indigo-700",
        "行为": "bg-amber-100 text-amber-700",
        "岗位匹配": "bg-green-100 text-green-700",
    };

    return `
        <div class="mt-4 border-t border-slate-100 pt-4 space-y-4">
            <div class="flex items-center justify-between gap-4">
                <div>
                    <div class="font-semibold text-sm text-slate-800">面试准备 #${prep.id}</div>
                    <div class="text-xs text-slate-500 mt-0.5">${escapeHtml(prep.title || "")} · ${escapeHtml(prep.created_at || "")}</div>
                </div>
                <button class="btn btn-secondary shrink-0" onclick="downloadApiFile('/api/interview-prep/${prep.id}/download', 'interview-prep-${prep.id}.md')"><iconify-icon icon="solar:download-bold-duotone"></iconify-icon>下载 MD</button>
            </div>
            <div class="font-semibold text-sm text-slate-800">面试问题 (${questions.length})</div>
            <div class="space-y-2.5">
                ${questions.map((q, i) => {
                    const cat = q.category || "通用";
                    const color = categoryColors[cat] || "bg-slate-100 text-slate-700";
                    return `
                        <div class="bg-slate-50 rounded-xl p-4">
                            <div class="flex items-center gap-2 mb-2">
                                <span class="px-2 py-0.5 rounded-md text-xs font-medium ${color}">${escapeHtml(cat)}</span>
                                <span class="font-medium text-sm text-slate-800">Q${i + 1}</span>
                            </div>
                            <p class="text-sm font-medium text-slate-700 mb-1.5">${escapeHtml(q.question || "")}</p>
                            <p class="text-sm text-slate-500 leading-relaxed">${escapeHtml(q.answer || "")}</p>
                        </div>
                    `;
                }).join("")}
            </div>
            ${tips.length ? `<div><div class="font-semibold text-sm text-slate-800 mb-2">准备建议</div><ul class="space-y-1.5">${tips.map((t) => `<li class="text-sm text-slate-600 flex items-start gap-2"><iconify-icon icon="solar:check-circle-bold" class="text-emerald-500 mt-0.5 shrink-0" width="14"></iconify-icon>${escapeHtml(t)}</li>`).join("")}</ul></div>` : ""}
            ${risks.length ? `<div><div class="font-semibold text-sm text-slate-800 mb-2">风险领域</div><ul class="space-y-1.5">${risks.map((r) => `<li class="bg-amber-50 rounded-lg p-2.5 text-amber-700 text-sm">${escapeHtml(r.area || "")}: ${escapeHtml(r.suggestion || "")}</li>`).join("")}</ul></div>` : ""}
        </div>
    `;
}

// ── End Cover Letter & Interview Prep ──────────────────────────────────

// ── Salary Analytics ───────────────────────────────────────────────────

let salaryChartInstances = {};

async function loadSalaryAnalytics() {
    const overview = document.getElementById("salary-overview");
    overview.innerHTML = "<div class='text-sm text-slate-500'>加载中...</div>";
    const res = await fetch(`${API_BASE}/analytics/salary`);
    const data = await res.json();
    if (!data.success) {
        overview.innerHTML = "<div class='text-sm text-red-500'>加载失败</div>";
        return;
    }
    const d = data.data;
    renderSalaryOverview(d.overall);
    renderDistributionChart(d.distribution);
    renderCityChart(d.by_city);
    renderPlatformChart(d.by_platform);
    renderExpectationPanel(d.vs_expectation, d.overall);
}

function renderSalaryOverview(overall) {
    const container = document.getElementById("salary-overview");
    const fmt = (v) => v ? `${(v / 1000).toFixed(1)}K` : "-";
    container.innerHTML = `
        <div class="card p-5"><div class="text-xs text-slate-500">有效岗位</div><div class="text-2xl font-bold mt-1.5">${overall.count}</div></div>
        <div class="card p-5"><div class="text-xs text-slate-500">平均薪资</div><div class="text-2xl font-bold mt-1.5 text-indigo-600">${fmt(overall.avg)}</div></div>
        <div class="card p-5"><div class="text-xs text-slate-500">中位数</div><div class="text-2xl font-bold mt-1.5">${fmt(overall.median)}</div></div>
        <div class="card p-5"><div class="text-xs text-slate-500">最低</div><div class="text-2xl font-bold mt-1.5 text-emerald-600">${fmt(overall.min)}</div></div>
        <div class="card p-5"><div class="text-xs text-slate-500">最高</div><div class="text-2xl font-bold mt-1.5 text-amber-600">${fmt(overall.max)}</div></div>
    `;
}

function destroyChart(id) {
    if (salaryChartInstances[id]) {
        salaryChartInstances[id].destroy();
        delete salaryChartInstances[id];
    }
}

function renderDistributionChart(distribution) {
    destroyChart("distribution");
    const ctx = document.getElementById("salary-distribution-chart");
    if (!ctx) return;
    salaryChartInstances["distribution"] = new Chart(ctx, {
        type: "bar",
        data: {
            labels: distribution.buckets,
            datasets: [{label: "岗位数", data: distribution.counts, backgroundColor: "#3b82f6", borderRadius: 4}],
        },
        options: {responsive: true, plugins: {legend: {display: false}}, scales: {y: {beginAtZero: true, ticks: {stepSize: 1}}}},
    });
}

function renderCityChart(byCity) {
    destroyChart("city");
    const ctx = document.getElementById("salary-by-city-chart");
    if (!ctx) return;
    const entries = Object.entries(byCity).slice(0, 10);
    salaryChartInstances["city"] = new Chart(ctx, {
        type: "bar",
        data: {
            labels: entries.map(([k]) => k),
            datasets: [{label: "平均薪资 (K)", data: entries.map(([, v]) => v.avg / 1000), backgroundColor: "#10b981", borderRadius: 4}],
        },
        options: {indexAxis: "y", responsive: true, plugins: {legend: {display: false}}},
    });
}

function renderPlatformChart(byPlatform) {
    destroyChart("platform");
    const ctx = document.getElementById("salary-by-platform-chart");
    if (!ctx) return;
    const entries = Object.entries(byPlatform);
    const colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];
    salaryChartInstances["platform"] = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: entries.map(([k]) => `${k} (${byPlatform[k].count})`),
            datasets: [{data: entries.map(([, v]) => v.avg), backgroundColor: colors.slice(0, entries.length)}],
        },
        options: {responsive: true, plugins: {legend: {position: "bottom", labels: {font: {size: 11}}}}},
    });
}

function renderExpectationPanel(exp, overall) {
    const container = document.getElementById("salary-expectation-panel");
    if (!exp.user_min && !exp.user_max) {
        container.innerHTML = '<p class="text-slate-400">未设置薪资期望，请在 config/user_profile.json 的 filter_preferences 中设置 salary_min 和 salary_max。</p>';
        return;
    }
    const fmt = (v) => `${(v / 1000).toFixed(0)}K`;
    const total = exp.above_count + exp.within_count + exp.below_count || 1;
    const pctWithin = (exp.within_count / total * 100).toFixed(0);
    const pctAbove = (exp.above_count / total * 100).toFixed(0);
    const pctBelow = (exp.below_count / total * 100).toFixed(0);
    container.innerHTML = `
        <div class="mb-3">期望范围：<span class="font-semibold">${fmt(exp.user_min)} - ${fmt(exp.user_max)}</span></div>
        <div class="space-y-2">
            <div><span class="inline-block w-20 text-slate-500">高于期望</span><span class="font-semibold text-amber-700">${exp.above_count} 个 (${pctAbove}%)</span></div>
            <div><span class="inline-block w-20 text-slate-500">符合期望</span><span class="font-semibold text-green-700">${exp.within_count} 个 (${pctWithin}%)</span></div>
            <div><span class="inline-block w-20 text-slate-500">低于期望</span><span class="font-semibold text-red-700">${exp.below_count} 个 (${pctBelow}%)</span></div>
        </div>
        <div class="mt-3 h-3 bg-slate-100 rounded-full overflow-hidden flex">
            <div class="bg-amber-400" style="width:${pctAbove}%"></div>
            <div class="bg-green-400" style="width:${pctWithin}%"></div>
            <div class="bg-red-400" style="width:${pctBelow}%"></div>
        </div>
    `;
}

// ── End Salary Analytics ───────────────────────────────────────────────

// ── Kanban Board ───────────────────────────────────────────────────────

const KANBAN_STATUSES = [
    {key: "new", label: "新导入", color: "slate"},
    {key: "analyzed", label: "已分析", color: "blue"},
    {key: "recommended", label: "推荐", color: "green"},
    {key: "resume_generated", label: "简历已生成", color: "indigo"},
    {key: "to_apply", label: "待投递", color: "violet"},
    {key: "applied", label: "已投递", color: "purple"},
    {key: "screening", label: "筛选中", color: "amber"},
    {key: "interviewing", label: "面试中", color: "orange"},
    {key: "offer", label: "Offer", color: "emerald"},
    {key: "rejected", label: "已拒绝", color: "red"},
    {key: "archived", label: "已归档", color: "gray"},
];

const ENCOURAGEMENTS = {
    empty: [
        "先导入一个 JD，今天的进度就从这里亮起来。",
        "空白看板也没关系，第一份岗位会把节奏带起来。",
    ],
    started: [
        "已经收集了 {n} 个岗位，好的机会正在慢慢成形。",
        "岗位已就位，下一步可以挑一个先分析匹配度。",
    ],
    analyzing: [
        "已经分析了 {n} 个岗位，最高匹配度 {score} 分。",
        "匹配数据已经有眉目了，优先推进高分岗位会更省力。",
    ],
    applying: [
        "已投递 {n} 个岗位，节奏很稳，继续保持。",
        "每一次投递都让机会更近一点，今天也在前进。",
    ],
    interviewing: [
        "有 {n} 个面试正在推进，记得把准备材料顺手补齐。",
        "面试阶段已经启动，你离结果更近了。",
    ],
    offer: [
        "Offer 已经出现了，辛苦推进的结果正在兑现。",
        "拿到 offer 了，后面可以更从容地比较选择。",
    ],
};

const KANBAN_EMPTY_STATES = {
    new: {title: "还没有新岗位", body: "去导入页粘贴一个 JD 试试看。", accent: "#818cf8"},
    analyzed: {title: "分析区很安静", body: "把新岗位分析后会来到这里。", accent: "#60a5fa"},
    recommended: {title: "推荐位待点亮", body: "高匹配岗位会自动浮上来。", accent: "#34d399"},
    resume_generated: {title: "简历还没生成", body: "为合适岗位产出定制版本。", accent: "#6366f1"},
    to_apply: {title: "待投递列表空着", body: "准备好材料后放到这里。", accent: "#8b5cf6"},
    applied: {title: "还没有投递记录", body: "投出第一份后这里会热闹起来。", accent: "#a855f7"},
    screening: {title: "暂无筛选中岗位", body: "等待反馈时可以先推进下一批。", accent: "#f59e0b"},
    interviewing: {title: "面试栏待开启", body: "进入面试后记得准备问题清单。", accent: "#fb923c"},
    offer: {title: "Offer 位在等你", body: "保持节奏，结果会慢慢靠近。", accent: "#10b981"},
    rejected: {title: "暂时没有拒信", body: "复盘可以之后再慢慢整理。", accent: "#f87171"},
    archived: {title: "归档区很清爽", body: "结束的机会可以拖到这里。", accent: "#94a3b8"},
};

async function loadKanbanSummary() {
    const panel = document.getElementById("kanban-summary-panel");
    if (!panel) return;
    panel.innerHTML = "<div class='text-sm text-slate-500'>统计加载中...</div>";
    try {
        const res = await fetch(`${API_BASE}/stats/summary`);
        const data = await res.json();
        if (!data.success) {
            panel.innerHTML = "<div class='text-sm text-red-500'>统计加载失败</div>";
            return;
        }
        renderKanbanSummary(data.data);
    } catch {
        panel.innerHTML = "<div class='text-sm text-red-500'>统计加载失败</div>";
    }
}

function renderKanbanSummary(stats) {
    const panel = document.getElementById("kanban-summary-panel");
    if (!panel) return;
    const byStatus = stats.by_status || {};
    const tiles = [
        {label: "总岗位", value: stats.total_jobs ?? 0, icon: "solar:case-minimalistic-bold-duotone", color: "text-indigo-600"},
        {label: "已投递", value: stats.total_applied ?? byStatus.applied ?? 0, icon: "solar:plain-bold-duotone", color: "text-purple-600"},
        {label: "面试中", value: stats.total_interviewing ?? byStatus.interviewing ?? 0, icon: "solar:chat-round-check-bold-duotone", color: "text-orange-600"},
        {label: "Offer", value: stats.total_offers ?? byStatus.offer ?? 0, icon: "solar:star-bold-duotone", color: "text-emerald-600"},
    ];
    const encouragement = chooseEncouragement(stats);
    panel.innerHTML = `
        <div class="grid grid-cols-2 xl:grid-cols-4 gap-3">
            ${tiles.map((tile) => `
                <div class="kanban-stat-tile p-4">
                    <div class="flex items-center gap-2 text-xs font-semibold text-slate-500">
                        <iconify-icon icon="${tile.icon}" class="${tile.color}" width="18"></iconify-icon>${escapeHtml(tile.label)}
                    </div>
                    <div class="text-2xl font-bold text-slate-900 mt-2">${tile.value}</div>
                </div>
            `).join("")}
        </div>
        <div class="encouragement-banner mt-3 p-4 flex items-start gap-3">
            ${renderSparkleSvg()}
            <div>
                <div class="text-sm font-bold text-slate-800">${escapeHtml(encouragement.title)}</div>
                <div class="text-sm text-slate-500 mt-1">${escapeHtml(encouragement.body)}</div>
            </div>
        </div>
    `;
}

function chooseEncouragement(stats) {
    const total = stats.total_jobs ?? 0;
    const analyzed = stats.total_analyzed ?? 0;
    const applied = stats.total_applied ?? 0;
    const interviewing = stats.total_interviewing ?? 0;
    const offers = stats.total_offers ?? 0;
    const topScore = stats.top_match_score ?? 0;
    let group = "empty";
    if (offers > 0) group = "offer";
    else if (interviewing > 0) group = "interviewing";
    else if (applied > 0) group = "applying";
    else if (analyzed > 0) group = "analyzing";
    else if (total > 0) group = "started";

    const options = ENCOURAGEMENTS[group] || ENCOURAGEMENTS.empty;
    const template = options[(total + analyzed + applied + interviewing + offers) % options.length];
    return {
        title: group === "empty" ? "今天也可以从一小步开始" : "你的求职进度正在推进",
        body: template
            .replaceAll("{n}", String(group === "analyzing" ? analyzed : group === "applying" ? applied : group === "interviewing" ? interviewing : total))
            .replaceAll("{score}", String(topScore || "-")),
    };
}

function renderSparkleSvg() {
    return `
        <svg viewBox="0 0 48 48" class="shrink-0" width="42" height="42" aria-hidden="true">
            <defs>
                <linearGradient id="sparkleGradient" x1="0" x2="1" y1="0" y2="1">
                    <stop offset="0%" stop-color="#818cf8"/>
                    <stop offset="55%" stop-color="#f9a8d4"/>
                    <stop offset="100%" stop-color="#6ee7b7"/>
                </linearGradient>
            </defs>
            <path fill="url(#sparkleGradient)" d="M24 4l4.8 13.2L42 22l-13.2 4.8L24 40l-4.8-13.2L6 22l13.2-4.8z"/>
            <circle cx="38" cy="9" r="3" fill="#fde68a"/>
            <circle cx="11" cy="36" r="2.5" fill="#f9a8d4"/>
        </svg>
    `;
}

async function loadKanbanBoard() {
    loadKanbanSummary();
    const board = document.getElementById("kanban-board");
    board.innerHTML = "<div class='text-sm text-slate-500'>加载中...</div>";
    const res = await fetch(`${API_BASE}/kanban/board`);
    const data = await res.json();
    if (!data.success) {
        board.innerHTML = "<div class='text-sm text-red-500'>加载失败</div>";
        return;
    }
    const grouped = data.data;
    board.innerHTML = KANBAN_STATUSES.map((s) => renderKanbanColumn(s.key, s.label, grouped[s.key] || [])).join("");
}

function renderKanbanColumn(status, label, jobs) {
    const countBadge = jobs.length > 0
        ? `<span class="ml-2 px-1.5 py-0.5 rounded-md bg-slate-200 text-xs font-medium">${jobs.length}</span>`
        : "";
    return `
        <div class="kanban-column card p-3 flex flex-col" data-status="${escapeHtml(status)}"
             ondragover="kanbanDragOver(event)" ondragleave="kanbanDragLeave(event)" ondrop="kanbanDrop(event, '${escapeHtml(status)}')">
            <div class="font-semibold text-xs text-slate-600 mb-3 flex items-center uppercase tracking-wide">${escapeHtml(label)}${countBadge}</div>
            <div class="space-y-2 flex-1 min-h-[60px]">
                ${jobs.length ? jobs.map((j) => renderKanbanCard(j)).join("") : renderKanbanEmptyState(status)}
            </div>
        </div>
    `;
}

function renderKanbanCard(job) {
    return `
        <div class="kanban-card card p-3" draggable="true"
             data-job-id="${job.id}"
             ondragstart="kanbanDragStart(event, ${job.id})" ondragend="kanbanDragEnd(event)">
            <div class="font-bold text-xs">${escapeHtml(job.title)}</div>
            <div class="text-[11px] text-slate-500 mt-1">${escapeHtml(job.company)}</div>
            <div class="flex items-center justify-between mt-2 text-[11px] text-slate-400">
                <span>${escapeHtml(job.city || "-")}</span>
                <span>${escapeHtml(job.salary || "-")}</span>
            </div>
            ${job.match_score != null ? `<div class="mt-1.5"><span class="px-1.5 py-0.5 rounded-md bg-indigo-50 text-indigo-600 text-[11px] font-medium">匹配 ${job.match_score}</span></div>` : ""}
        </div>
    `;
}

function renderKanbanEmptyState(status) {
    const state = KANBAN_EMPTY_STATES[status] || KANBAN_EMPTY_STATES.new;
    return `
        <div class="kanban-empty-state p-4 text-center text-xs text-slate-500">
            ${renderEmptyMascotSvg(state.accent)}
            <div class="font-semibold text-slate-700 mt-2">${escapeHtml(state.title)}</div>
            <div class="mt-1 leading-5">${escapeHtml(state.body)}</div>
            <button class="btn btn-ghost mt-3 mx-auto text-xs" onclick="goToPage('import')">
                <iconify-icon icon="solar:import-bold-duotone"></iconify-icon>去导入
            </button>
        </div>
    `;
}

function renderEmptyMascotSvg(accent) {
    const color = escapeHtml(accent || "#818cf8");
    return `
        <svg viewBox="0 0 120 96" aria-hidden="true">
            <defs>
                <linearGradient id="emptyFaceGradient-${color.replace("#", "")}" x1="0" x2="1" y1="0" y2="1">
                    <stop offset="0%" stop-color="#ffffff"/>
                    <stop offset="100%" stop-color="#eef2ff"/>
                </linearGradient>
            </defs>
            <path d="M28 70c7 12 55 12 64 0 7-9 4-35-5-46-12-14-42-15-55 0-10 11-11 36-4 46z" fill="url(#emptyFaceGradient-${color.replace("#", "")})" stroke="${color}" stroke-width="3"/>
            <circle cx="47" cy="50" r="5" fill="#334155"/>
            <circle cx="73" cy="50" r="5" fill="#334155"/>
            <path d="M52 65c6 5 13 5 19 0" fill="none" stroke="#64748b" stroke-width="3" stroke-linecap="round"/>
            <path d="M30 25l-9-12 17 4" fill="#fbcfe8" stroke="${color}" stroke-width="3" stroke-linejoin="round"/>
            <path d="M89 25l10-12-18 4" fill="#bbf7d0" stroke="${color}" stroke-width="3" stroke-linejoin="round"/>
            <path d="M18 71l-8 5 8 5 5 8 5-8 8-5-8-5-5-8z" fill="#fde68a"/>
            <path d="M99 66l-5 3 5 3 3 5 3-5 5-3-5-3-3-5z" fill="#f9a8d4"/>
        </svg>
    `;
}

function kanbanDragStart(event, jobId) {
    event.dataTransfer.setData("text/plain", String(jobId));
    event.target.classList.add("dragging");
}

function kanbanDragEnd(event) {
    event.target.classList.remove("dragging");
}

function kanbanDragOver(event) {
    event.preventDefault();
    const col = event.currentTarget;
    col.classList.add("drag-over");
}

function kanbanDragLeave(event) {
    event.currentTarget.classList.remove("drag-over");
}

async function kanbanDrop(event, newStatus) {
    event.preventDefault();
    event.currentTarget.classList.remove("drag-over");
    const jobId = event.dataTransfer.getData("text/plain");
    if (!jobId) return;

    const res = await fetch(`${API_BASE}/kanban/jobs/${jobId}/move`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({new_status: newStatus}),
    });
    const data = await res.json();
    if (data.success) {
        loadKanbanBoard();
        loadStats();
        showToast("状态已更新");
    } else {
        showToast(data.detail || data.message || "移动失败", "error");
    }
}

// ── End Kanban ─────────────────────────────────────────────────────────

window.addEventListener("load", async () => {
    if (!checkAuth()) return;
    loadOnboardingStatus();
    loadKanbanBoard();
    const user = getCurrentUser();
    const el = document.getElementById("current-username");
    if (el && user) el.textContent = user.username;

    // 初始化 AI 试用状态
    try {
        const meRes = await fetch(`${API_BASE}/auth/me`);
        const meData = await meRes.json();
        if (meData.success) {
            updateTrialUI(meData.data.ai_usage_count);
        }
    } catch {}
});
