const API_BASE = "/api";

// ── Auth ────────────────────────────────────────────────────────────────
function getToken() {
    return localStorage.getItem("token");
}

function getCurrentUser() {
    try { return JSON.parse(localStorage.getItem("user")); } catch { return null; }
}

function logout() {
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

    if (page === "jobs") loadJobs();
    if (page === "kanban") loadKanbanBoard();
    if (page === "evidence") loadEvidence();
    if (page === "runs") loadRuns();
    if (page === "analytics") loadSalaryAnalytics();
    if (page === "settings") loadModelSettings();
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
    } else {
        result.textContent = `导入失败：${data.detail || data.message}`;
        showToast(data.detail || data.message || "导入失败", "error");
    }
}

async function loadJobs() {
    const container = document.getElementById("jobs-list");
    container.innerHTML = "<div class='text-sm text-slate-500'>加载中...</div>";
    const res = await fetch(`${API_BASE}/jobs?per_page=50`);
    const data = await res.json();
    if (!data.success || data.data.length === 0) {
        container.innerHTML = "<div class='card p-5 text-sm text-slate-500'>暂无岗位，先导入一条 JD。</div>";
        return;
    }

    container.innerHTML = data.data.map((job) => `
        <article class="card p-5">
            <div class="flex items-start justify-between gap-4">
                <div class="min-w-0 flex-1">
                    <h3 class="font-bold text-sm">${escapeHtml(job.title)}</h3>
                    <p class="text-xs text-slate-500 mt-1">${escapeHtml(job.company)} · ${escapeHtml(job.city || "未知城市")} · ${escapeHtml(job.salary || "薪资未填")}</p>
                    <p class="text-xs text-slate-400 mt-1.5">
                        来源：${escapeHtml(job.source)} ·
                        状态：<span id="job-status-${job.id}" class="font-medium">${escapeHtml(job.status)}</span> ·
                        匹配分：<span id="job-score-${job.id}" class="font-medium">${job.match_score ?? "-"}</span>
                    </p>
                </div>
                <div class="flex flex-wrap gap-1.5 shrink-0">
                    <button class="btn btn-secondary" onclick="analyzeJob(${job.id})"><iconify-icon icon="solar:magic-stick-3-bold-duotone"></iconify-icon>分析</button>
                    <button class="btn btn-secondary" onclick="showAnalysis(${job.id})"><iconify-icon icon="solar:chart-2-bold-duotone"></iconify-icon>详情</button>
                    <button class="btn btn-primary" onclick="generateResume(${job.id})"><iconify-icon icon="solar:document-text-bold-duotone"></iconify-icon>简历</button>
                    <button class="btn btn-secondary" onclick="showResumeVersions(${job.id})"><iconify-icon icon="solar:documents-bold-duotone"></iconify-icon>版本</button>
                    <button class="btn btn-secondary" onclick="generateCoverLetter(${job.id})"><iconify-icon icon="solar:letter-bold-duotone"></iconify-icon>Cover Letter</button>
                    <button class="btn btn-secondary" onclick="generateInterviewPrep(${job.id})"><iconify-icon icon="solar:notebook-bold-duotone"></iconify-icon>面试</button>
                </div>
            </div>
            <div id="job-result-${job.id}" class="text-sm mt-3 text-slate-600"></div>
        </article>
    `).join("");
}

async function analyzeJob(jobId) {
    const result = document.getElementById(`job-result-${jobId}`);
    result.textContent = "Agent 正在分析...";
    const res = await fetch(`${API_BASE}/analyses/jobs/${jobId}`, {method: "POST"});
    const data = await res.json();
    if (data.success) {
        const analysis = data.data;
        result.innerHTML = renderAnalysisPanel(analysis);
        const newStatus = ["A", "B"].includes(analysis.recommendation_level) ? "recommended" : "analyzed";
        updateJobCardMeta(jobId, analysis.match_score, newStatus);
        loadStats();
    } else {
        result.textContent = `分析失败：${data.detail || data.message}`;
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
    result.textContent = "正在生成简历版本...";
    const res = await fetch(`${API_BASE}/resumes/generate`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({job_id: jobId}),
    });
    const data = await res.json();
    result.innerHTML = data.success
        ? renderResumePanel(data.data)
        : `<div class="text-red-600">生成失败：${escapeHtml(data.detail || data.message)}</div>`;
    if (data.success) {
        updateJobCardMeta(jobId, null, "resume_generated");
        loadStats();
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
                <div class="bg-slate-50 rounded-xl p-3"><div class="text-xs text-slate-500">分析器</div><div class="text-xl font-bold mt-1">${escapeHtml(analysis.analyzer_type || "-")}</div></div>
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
                <button class="btn btn-secondary" onclick="copyResumeContent(${version.id})"><iconify-icon icon="solar:copy-bold-duotone"></iconify-icon>复制</button>
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
}

async function loadEvidence() {
    const container = document.getElementById("evidence-list");
    container.innerHTML = "<div class='text-sm text-slate-500'>加载中...</div>";
    const res = await fetch(`${API_BASE}/evidence`);
    const data = await res.json();
    if (!data.success || data.data.length === 0) {
        container.innerHTML = "<div class='card p-5 text-sm text-slate-500'>暂无证据，可以手动新增或调用 /api/evidence/init 初始化。</div>";
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
    } else {
        alert(data.detail || data.message || "保存失败");
    }
}

async function deleteEvidence(id) {
    const res = await fetch(`${API_BASE}/evidence/${id}`, {method: "DELETE"});
    const data = await res.json();
    if (data.success) loadEvidence();
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

let modelSettingsState = {providers: [], current: {}};

const modelLimitFields = [
    {key: "max_tokens", inputId: "model-max-tokens", checkboxId: "model-max-tokens-unlimited", fallback: 2000},
    {key: "rate_limit", inputId: "model-rate-limit", checkboxId: "model-rate-limit-unlimited", fallback: 10},
    {key: "daily_limit", inputId: "model-daily-limit", checkboxId: "model-daily-limit-unlimited", fallback: 10},
];

async function loadModelSettings() {
    const res = await fetch(`${API_BASE}/settings/models`);
    const data = await res.json();
    if (!data.success) return;
    modelSettingsState = data;

    const providerSelect = document.getElementById("model-provider");
    providerSelect.innerHTML = data.providers.map((provider) => `
        <option value="${escapeHtml(provider.key)}">${escapeHtml(provider.label)}</option>
    `).join("");

    document.getElementById("model-provider").value = data.current.provider;
    document.getElementById("model-name").value = data.current.model || "";
    modelLimitFields.forEach((field) => setLimitField(field, data.current[field.key]));
    document.getElementById("model-cache-enabled").checked = Boolean(data.current.cache_enabled);
    document.getElementById("model-enable-thinking").checked = Boolean(data.current.enable_thinking);
    document.getElementById("model-base-url").value = data.current.base_url || "";
    onProviderChanged();
}

function setLimitField(field, value) {
    const input = document.getElementById(field.inputId);
    const checkbox = document.getElementById(field.checkboxId);
    const unlimited = value === null || value === undefined;

    checkbox.checked = unlimited;
    input.disabled = unlimited;
    input.value = unlimited ? "" : value;
    input.placeholder = unlimited ? "不限" : String(field.fallback);
}

function toggleLimitField(inputId) {
    const field = modelLimitFields.find((item) => item.inputId === inputId);
    if (!field) return;
    const input = document.getElementById(field.inputId);
    const checkbox = document.getElementById(field.checkboxId);

    input.disabled = checkbox.checked;
    input.placeholder = checkbox.checked ? "不限" : String(field.fallback);
    if (checkbox.checked) {
        input.value = "";
    } else if (!input.value) {
        input.value = field.fallback;
    }
}

function readLimitField(field) {
    const checkbox = document.getElementById(field.checkboxId);
    if (checkbox.checked) {
        return null;
    }

    const raw = document.getElementById(field.inputId).value.trim();
    return raw ? Number(raw) : field.fallback;
}

function formatApiError(data) {
    const detail = data?.detail || data?.message;
    if (Array.isArray(detail)) {
        return detail.map((item) => {
            const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : "";
            const labels = {
                max_tokens: "最大输出 Tokens",
                rate_limit: "每分钟调用上限",
                daily_limit: "每日调用上限",
                provider: "模型提供商",
                model: "模型名称",
            };
            const label = labels[field] || field || "配置项";
            return `${label}：${item.msg || "填写不正确"}`;
        }).join("；");
    }
    if (detail && typeof detail === "object") {
        return JSON.stringify(detail);
    }
    return detail || "未知错误";
}

function getSelectedProviderMeta() {
    const provider = document.getElementById("model-provider").value;
    return modelSettingsState.providers.find((item) => item.key === provider) || {};
}

function onProviderChanged() {
    const meta = getSelectedProviderMeta();
    const datalist = document.getElementById("model-options");
    datalist.innerHTML = (meta.models || []).map((model) => `<option value="${escapeHtml(model)}"></option>`).join("");

    document.getElementById("model-thinking-wrap").classList.toggle("hidden", !meta.supports_thinking);
    document.getElementById("model-base-url-wrap").classList.toggle("hidden", !meta.supports_base_url);

    const status = meta.api_key_configured
        ? `已检测到 ${meta.env_key}，该 provider 可调用。`
        : `未检测到 ${meta.env_key}。保存模型选择可以生效，但调用模型前需要在 .env 中配置该变量。`;
    document.getElementById("model-api-key-status").textContent = status;
}

async function saveModelSettings(event) {
    event.preventDefault();
    const result = document.getElementById("model-settings-result");
    const payload = {
        provider: document.getElementById("model-provider").value,
        model: document.getElementById("model-name").value.trim(),
        max_tokens: readLimitField(modelLimitFields[0]),
        rate_limit: readLimitField(modelLimitFields[1]),
        daily_limit: readLimitField(modelLimitFields[2]),
        cache_enabled: document.getElementById("model-cache-enabled").checked,
        enable_thinking: document.getElementById("model-enable-thinking").checked,
        base_url: document.getElementById("model-base-url").value.trim(),
    };
    result.textContent = "正在保存...";

    const res = await fetch(`${API_BASE}/settings/models`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.success) {
        result.textContent = "模型配置已保存";
        showToast("模型配置已保存");
        await loadModelSettings();
    } else {
        result.textContent = `保存失败：${formatApiError(data)}`;
        showToast("保存失败", "error");
    }
}

// ── Cover Letter & Interview Prep ──────────────────────────────────────

async function generateCoverLetter(jobId) {
    const result = document.getElementById(`job-result-${jobId}`);
    result.textContent = "正在生成 Cover Letter...";
    const res = await fetch(`${API_BASE}/cover-letters/generate`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({job_id: jobId}),
    });
    const data = await res.json();
    result.innerHTML = data.success
        ? renderCoverLetterPanel(data.data)
        : `<div class="text-red-600">生成失败：${escapeHtml(data.detail || data.message)}</div>`;
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
                <button class="btn btn-secondary" onclick="copyCoverLetterContent(${cl.id})"><iconify-icon icon="solar:copy-bold-duotone"></iconify-icon>复制</button>
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
}

async function generateInterviewPrep(jobId) {
    const result = document.getElementById(`job-result-${jobId}`);
    result.textContent = "正在生成面试准备材料...";
    const res = await fetch(`${API_BASE}/interview-prep/generate`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({job_id: jobId}),
    });
    const data = await res.json();
    result.innerHTML = data.success
        ? renderInterviewPrepPanel(data.data)
        : `<div class="text-red-600">生成失败：${escapeHtml(data.detail || data.message)}</div>`;
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

async function loadKanbanBoard() {
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
                ${jobs.map((j) => renderKanbanCard(j)).join("")}
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

window.addEventListener("load", () => {
    checkAuth();
    loadKanbanBoard();
    // 显示当前用户名
    const user = getCurrentUser();
    const el = document.getElementById("current-username");
    if (el && user) el.textContent = user.username;
});
