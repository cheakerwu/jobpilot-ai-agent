const API_BASE = "/api";

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function switchPage(page, target) {
    document.querySelectorAll("[id^='page-']").forEach((el) => el.classList.add("hidden"));
    document.getElementById(`page-${page}`).classList.remove("hidden");
    document.querySelectorAll(".nav-item").forEach((el) => el.classList.remove("nav-active"));
    if (target) target.classList.add("nav-active");

    if (page === "dashboard") loadStats();
    if (page === "jobs") loadJobs();
    if (page === "evidence") loadEvidence();
    if (page === "runs") loadRuns();
    if (page === "settings") loadModelSettings();
}

async function loadStats() {
    const res = await fetch(`${API_BASE}/jobs/stats`);
    const data = await res.json();
    if (!data.success) return;
    const stats = data.data;
    document.getElementById("stat-total").textContent = stats.total ?? 0;
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
    result.textContent = data.success ? `导入成功：${data.job.title}` : `导入失败：${data.message || data.detail}`;
    if (data.success) {
        form.reset();
        loadStats();
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
    result.textContent = data.success
        ? `导入完成：成功 ${data.success_count}，失败 ${data.failed_count}，跳过 ${data.skipped_count}`
        : `导入失败：${data.message || data.detail}`;
    if (data.success) {
        form.reset();
        loadStats();
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
    result.textContent = data.success
        ? `导入成功：${data.job.title} · ${data.job.company}`
        : `导入失败：${data.detail || data.message}`;
    if (data.success) {
        form.reset();
        loadStats();
    }
}

async function loadJobs() {
    const container = document.getElementById("jobs-list");
    container.innerHTML = "<div class='text-sm text-slate-500'>加载中...</div>";
    const res = await fetch(`${API_BASE}/jobs?per_page=50`);
    const data = await res.json();
    if (!data.success || data.data.length === 0) {
        container.innerHTML = "<div class='panel p-5 text-sm text-slate-500'>暂无岗位，先导入一条 JD。</div>";
        return;
    }

    container.innerHTML = data.data.map((job) => `
        <article class="panel p-5">
            <div class="flex items-start justify-between gap-4">
                <div>
                    <h3 class="font-bold">${escapeHtml(job.title)}</h3>
                    <p class="text-sm text-slate-500 mt-1">${escapeHtml(job.company)} · ${escapeHtml(job.city || "未知城市")} · ${escapeHtml(job.salary || "薪资未填")}</p>
                    <p class="text-xs text-slate-400 mt-2">
                        来源：${escapeHtml(job.source)} ·
                        状态：<span id="job-status-${job.id}">${escapeHtml(job.status)}</span> ·
                        匹配分：<span id="job-score-${job.id}">${job.match_score ?? "-"}</span>
                    </p>
                </div>
                <div class="flex gap-2 shrink-0">
                    <button class="btn btn-secondary" onclick="analyzeJob(${job.id})"><iconify-icon icon="solar:magic-stick-3-bold-duotone"></iconify-icon>分析</button>
                    <button class="btn btn-secondary" onclick="showAnalysis(${job.id})"><iconify-icon icon="solar:chart-2-bold-duotone"></iconify-icon>匹配详情</button>
                    <button class="btn btn-primary" onclick="generateResume(${job.id})"><iconify-icon icon="solar:document-text-bold-duotone"></iconify-icon>生成简历</button>
                    <button class="btn btn-secondary" onclick="showResumeVersions(${job.id})"><iconify-icon icon="solar:documents-bold-duotone"></iconify-icon>简历版本</button>
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
        <div class="mt-4 border-t border-slate-200 pt-4 space-y-4">
            <div class="grid grid-cols-2 xl:grid-cols-4 gap-3">
                <div class="bg-slate-50 rounded-md p-3"><div class="text-xs text-slate-500">推荐等级</div><div class="text-xl font-bold">${escapeHtml(analysis.recommendation_level || "-")}</div></div>
                <div class="bg-slate-50 rounded-md p-3"><div class="text-xs text-slate-500">匹配分</div><div class="text-xl font-bold">${analysis.match_score ?? "-"}</div></div>
                <div class="bg-slate-50 rounded-md p-3"><div class="text-xs text-slate-500">风险分</div><div class="text-xl font-bold">${analysis.risk_score ?? "-"}</div></div>
                <div class="bg-slate-50 rounded-md p-3"><div class="text-xs text-slate-500">分析器</div><div class="text-xl font-bold">${escapeHtml(analysis.analyzer_type || "-")}</div></div>
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
    return `<ul class="mt-2 space-y-2">${items.map((item) => `
        <li class="bg-green-50 rounded-md p-2">
            <span class="font-medium text-green-800">${escapeHtml(item.requirement || "要求")}</span>
            <span class="text-green-700"> → ${escapeHtml(item.evidence_title || `证据 #${item.evidence_id ?? "-"}`)}</span>
        </li>
    `).join("")}</ul>`;
}

function renderGaps(items) {
    if (!items.length) {
        return `<p class="mt-2 text-slate-400">暂无明显待补充项。</p>`;
    }
    return `<ul class="mt-2 space-y-2">${items.map((item) => `
        <li class="bg-amber-50 rounded-md p-2">
            <div class="font-medium text-amber-800">${escapeHtml(item.requirement || "缺口")}</div>
            <div class="text-amber-700">${escapeHtml(item.suggestion || "")}</div>
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
    return `<ul class="mt-2 space-y-2">${riskItems.map((item) => `
        <li class="bg-red-50 rounded-md p-2 text-red-700">${escapeHtml(item)}</li>
    `).join("")}</ul>`;
}

function renderResumePanel(version) {
    const warnings = Array.isArray(version.risk_warnings) ? version.risk_warnings : [];
    const evidenceLinks = Array.isArray(version.evidence_links) ? version.evidence_links : [];
    const coverage = version.keyword_coverage && typeof version.keyword_coverage === "object"
        ? Object.entries(version.keyword_coverage)
        : [];
    return `
        <div class="mt-4 border-t border-slate-200 pt-4 space-y-4">
            <div class="flex items-center justify-between gap-4">
                <div>
                    <div class="font-semibold text-slate-800">简历版本 #${version.id}</div>
                    <div class="text-xs text-slate-500">${escapeHtml(version.title || "")} · ${escapeHtml(version.created_at || "")}</div>
                </div>
                <button class="btn btn-secondary" onclick="copyResumeContent(${version.id})"><iconify-icon icon="solar:copy-bold-duotone"></iconify-icon>复制内容</button>
            </div>
            ${warnings.length ? `
                <div>
                    <div class="font-semibold text-slate-800">风险提示</div>
                    <ul class="mt-2 space-y-2">${warnings.map((item) => `<li class="bg-amber-50 rounded-md p-2 text-amber-800">${escapeHtml(item)}</li>`).join("")}</ul>
                </div>
            ` : ""}
            ${evidenceLinks.length ? `
                <div>
                    <div class="font-semibold text-slate-800">引用证据</div>
                    <ul class="mt-2 space-y-2">${evidenceLinks.slice(0, 8).map((item) => `
                        <li class="bg-green-50 rounded-md p-2 text-green-800">证据 #${escapeHtml(item.evidence_id)}：${escapeHtml(item.bullet_text || "")}</li>
                    `).join("")}</ul>
                </div>
            ` : ""}
            ${coverage.length ? `
                <div>
                    <div class="font-semibold text-slate-800">关键词覆盖</div>
                    <div class="flex flex-wrap gap-2 mt-2">${coverage.slice(0, 24).map(([key, value]) => `
                        <span class="px-2 py-1 rounded text-xs ${value ? "bg-blue-50 text-blue-700" : "bg-slate-100 text-slate-500"}">${escapeHtml(key)} ${value ? "✓" : "×"}</span>
                    `).join("")}</div>
                </div>
            ` : ""}
            <div>
                <div class="font-semibold text-slate-800 mb-2">简历预览</div>
                <pre id="resume-content-${version.id}" class="bg-slate-950 text-slate-50 rounded-md p-4 overflow-auto max-h-[560px] whitespace-pre-wrap text-sm leading-6">${escapeHtml(version.content || "")}</pre>
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
        container.innerHTML = "<div class='panel p-5 text-sm text-slate-500'>暂无证据，可以手动新增或调用 /api/evidence/init 初始化。</div>";
        return;
    }
    container.innerHTML = data.data.map((ev) => `
        <article class="panel p-5">
            <div class="flex items-start justify-between gap-4">
                <div>
                    <h3 class="font-bold">${escapeHtml(ev.title)}</h3>
                    <p class="text-xs text-slate-500 mt-1">${escapeHtml(ev.type)} · ${escapeHtml((ev.skill_tags || []).join(", "))}</p>
                    <p class="text-sm text-slate-600 mt-2 whitespace-pre-wrap">${escapeHtml(ev.content || "")}</p>
                </div>
                <button class="btn btn-secondary" onclick="deleteEvidence(${ev.id})"><iconify-icon icon="solar:trash-bin-trash-bold-duotone"></iconify-icon>删除</button>
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
    result.textContent = data.success
        ? `导入完成：新增 ${data.count} 条证据`
        : `导入失败：${data.detail || data.message}`;
    if (data.success) {
        form.reset();
        loadEvidence();
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
        container.innerHTML = "<div class='panel p-5 text-sm text-slate-500'>暂无 Agent 运行记录。</div>";
        return;
    }
    container.innerHTML = data.data.map((run) => `
        <article class="panel p-5">
            <div class="flex items-center justify-between">
                <div>
                    <h3 class="font-bold">#${run.id} ${escapeHtml(run.workflow_name)}</h3>
                    <p class="text-sm text-slate-500 mt-1">岗位 ID：${run.job_id ?? "-"} · 状态：${escapeHtml(run.status)} · 开始：${escapeHtml(run.started_at || "")}</p>
                    ${run.error_message ? `<p class="text-sm text-red-600 mt-2">${escapeHtml(run.error_message)}</p>` : ""}
                </div>
                <button class="btn btn-secondary" onclick="loadRunSteps(${run.id})"><iconify-icon icon="solar:list-check-bold-duotone"></iconify-icon>步骤</button>
            </div>
            <div id="run-steps-${run.id}" class="mt-3 text-sm"></div>
        </article>
    `).join("");
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
    result.textContent = data.success ? "模型配置已保存" : `保存失败：${formatApiError(data)}`;
    if (data.success) {
        await loadModelSettings();
    }
}

window.addEventListener("load", () => {
    loadStats();
});
