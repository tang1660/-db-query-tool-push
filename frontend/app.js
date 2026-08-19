/* 智能数据库查询工具 前端逻辑 */
const API = "/api/v1";

const state = {
  conn: "company_db",
  lastSql: "",
  lastResult: null,
  lastNlSql: "",
};

const $ = (id) => document.getElementById(id);

/* ============ 工具 ============ */
function toast(msg, type = "") {
  const el = $("toast");
  el.textContent = msg;
  el.className = "toast " + type;
  setTimeout(() => el.classList.add("hidden"), 2600);
}

function nowTime() {
  return new Date().toLocaleTimeString("zh-CN", { hour12: false });
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

/* ============ 初始化 ============ */
async function init() {
  await loadConnections();
  await checkHealth();
  bindMenu();
  bindSql();
  bindNl();
  bindAuto();
  bindHistory();
}

async function loadConnections() {
  try {
    const res = await fetch(`${API}/dbs`);
    const data = await res.json();
    const sel = $("connSelect");
    sel.innerHTML = "";
    data.items.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.name;
      opt.textContent = `${c.name}（${c.dbType}）`;
      sel.appendChild(opt);
    });
    sel.value = state.conn;
    updateConnDesc();
    sel.addEventListener("change", () => {
      state.conn = sel.value;
      updateConnDesc();
      loadHistory();
    });
  } catch (e) {
    toast("加载数据库列表失败", "error");
  }
}

function updateConnDesc() {
  const sel = $("connSelect");
  const opt = sel.options[sel.selectedIndex];
  $("connDesc").textContent = opt ? opt.textContent : "";
}

async function checkHealth() {
  const tag = $("healthTag");
  tag.className = "health-tag checking";
  tag.textContent = "检测中…";
  try {
    const res = await fetch("/health");
    const data = await res.json();
    if (data.status === "healthy") {
      tag.className = "health-tag ok";
      tag.textContent = "● 后端正常";
    } else {
      throw new Error();
    }
  } catch {
    tag.className = "health-tag err";
    tag.textContent = "● 后端异常";
  }
}

/* ============ 菜单切换：仅当前激活，其余折叠 ============ */
function bindMenu() {
  document.querySelectorAll(".menu-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".menu-item").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
      $("tab-" + btn.dataset.tab).classList.add("active");
      if (btn.dataset.tab === "history") loadHistory();
    });
  });
}

/* ============ SQL 查询 ============ */
function bindSql() {
  $("runSqlBtn").addEventListener("click", runSql);
  $("exportCsvBtn").addEventListener("click", () => exportCurrent("csv"));
  $("exportJsonBtn").addEventListener("click", () => exportCurrent("json"));
}

async function runSql() {
  const sql = $("sqlInput").value.trim();
  if (!sql) return toast("请输入 SQL", "error");
  $("runSqlBtn").disabled = true;
  try {
    const res = await fetch(`${API}/dbs/${state.conn}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sql }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "查询失败");
    state.lastSql = sql;
    state.lastResult = data;
    renderResult($("resultArea"), data);
    $("exportBar").classList.remove("hidden");
    toast("查询完成", "success");
  } catch (e) {
    $("resultArea").classList.add("empty");
    $("resultArea").innerHTML = `<p class="placeholder" style="color:var(--danger)">查询出错：${esc(e.message)}</p>`;
    $("exportBar").classList.add("hidden");
  } finally {
    $("runSqlBtn").disabled = false;
  }
}

function renderResult(container, data) {
  container.classList.remove("empty");
  let html = `
    <div class="result-meta">
      <span class="badge">${data.rowCount} 行</span>
      <span class="badge green">${data.columns.length} 列</span>
      <span class="time">耗时 ${data.executionTimeMs} ms</span>
      <span class="time">SQL: ${esc(data.sql || "")}</span>
    </div>`;
  if (data.rowCount === 0) {
    html += `<p class="placeholder" style="padding:24px;text-align:center">查询无结果。</p>`;
  } else {
    html += `<div class="table-wrap"><table><thead><tr>`;
    data.columns.forEach((c) => (html += `<th>${esc(c)}</th>`));
    html += `</tr></thead><tbody>`;
    data.rows.forEach((row) => {
      html += `<tr>`;
      row.forEach((v) => (html += `<td>${esc(v ?? "")}</td>`));
      html += `</tr>`;
    });
    html += `</tbody></table></div>`;
  }
  container.innerHTML = html;
}

/* ============ 导出当前结果（基于已执行 SQL） ============ */
async function exportCurrent(fmt) {
  if (!state.lastSql) return toast("请先执行查询", "error");
  await downloadExport(`${API}/dbs/${state.conn}/export`, {
    sql: state.lastSql,
    format: fmt,
    baseName: "query_result",
  }, fmt);
}

async function downloadExport(url, body, fmt) {
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "导出失败");
    }
    const blob = await res.blob();
    const metaRaw = res.headers.get("X-Export-Meta");
    const meta = metaRaw ? JSON.parse(decodeURIComponent(metaRaw)) : {};
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = meta.filename || `export.${fmt}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(a.href);
    toast(`已导出 ${fmt.toUpperCase()}：${meta.rowCount ?? ""} 行 · ${meta.byteSize ?? blob.size} 字节`, "success");
    return meta;
  } catch (e) {
    toast(e.message, "error");
    return null;
  }
}

/* ============ 自然语言查询 + AI 主动询问导出 ============ */
function bindNl() {
  $("nlSendBtn").addEventListener("click", sendNl);
  $("nlInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendNl();
  });
  document.addEventListener("click", (e) => {
    const chip = e.target.closest(".ex-chip");
    if (chip) {
      $("nlInput").value = chip.dataset.prompt;
      sendNl();
    }
  });
}

function appendMsg(role, text, extraHtml = "") {
  const box = $("chatBox");
  const div = document.createElement("div");
  div.className = `chat-msg ${role}`;
  div.innerHTML = `
    <div class="avatar">${role === "ai" ? "AI" : "我"}</div>
    <div class="bubble">${text}${extraHtml}</div>`;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
  return div;
}

async function sendNl() {
  const prompt = $("nlInput").value.trim();
  if (!prompt) return;
  appendMsg("user", esc(prompt));
  $("nlInput").value = "";
  const thinking = appendMsg("ai", "正在将你的问题翻译为 SQL…");

  try {
    // 1. NL -> SQL
    const r1 = await fetch(`${API}/dbs/${state.conn}/query/natural`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    const gen = await r1.json();
    if (!r1.ok) throw new Error(gen.detail || "生成 SQL 失败");

    state.lastNlSql = gen.sql;
    state.lastSql = gen.sql;

    thinking.querySelector(".bubble").innerHTML =
      `${esc(gen.explanation)}<div class="sql-block">${esc(gen.sql)}</div>
       <div class="export-prompt">
         <span>✅ 已为你执行查询，是否导出结果？</span>
         <button class="btn csv ex-btn" data-fmt="csv">导出 CSV</button>
         <button class="btn json ex-btn" data-fmt="json">导出 JSON</button>
       </div>`;

    // 2. 执行 SQL
    const r2 = await fetch(`${API}/dbs/${state.conn}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sql: gen.sql }),
    });
    const result = await r2.json();
    if (!r2.ok) throw new Error(result.detail || "执行失败");
    state.lastResult = result;

    const area = $("nlResultArea");
    area.classList.remove("hidden");
    renderResult(area, result);

    // 绑定 AI 主动询问的导出按钮
    thinking.querySelectorAll(".ex-btn").forEach((btn) => {
      btn.addEventListener("click", () => exportCurrent(btn.dataset.fmt));
    });
  } catch (e) {
    thinking.querySelector(".bubble").innerHTML = `<span style="color:var(--danger)">出错了：${esc(e.message)}</span>`;
  }
}

/* ============ 一键查询并导出（自动化流程） ============ */
function bindAuto() {
  $("autoRunBtn").addEventListener("click", runAuto);
}

async function runAuto() {
  const prompt = $("autoPrompt").value.trim();
  const fmt = document.querySelector('input[name="autoFmt"]:checked').value;
  if (!prompt) return toast("请输入自然语言", "error");

  const log = $("autoLog");
  log.innerHTML = "";
  const addLog = (tag, text) => {
    const line = document.createElement("div");
    line.className = "log-line";
    line.innerHTML = `<span class="ll-time">${nowTime()}</span>
      <span class="ll-tag ${tag === "进行中" ? "run" : tag === "完成" ? "done" : "info"}">${tag}</span>
      <span class="ll-text">${text}</span>`;
    log.appendChild(line);
    log.scrollTop = log.scrollHeight;
  };

  $("autoRunBtn").disabled = true;
  addLog("进行中", "启动自动化流程：自然语言 → SQL → 查询 → 导出");
  addLog("信息", `Agent 子任务分解：①获取查询结果 ②格式化数据 ③创建文件`);

  try {
    addLog("进行中", "① 调用 NL2SQL 生成查询语句…");
    const meta = await downloadExport(`${API}/dbs/${state.conn}/query-and-export`, {
      prompt,
      format: fmt,
    }, fmt);

    if (meta) {
      addLog("完成", `① NL→SQL：<code>${esc(meta.generatedSql)}</code>`);
      addLog("完成", `② 格式化为 ${fmt.toUpperCase()}（${meta.rowCount} 行，${meta.byteSize} 字节）`);
      addLog("完成", `③ 创建文件：<code>${esc(meta.filename)}</code>`);
      addLog("信息", `AI 解释：${esc(meta.explanation)}`);
      addLog("完成", `✅ 一键流程结束，文件已开始下载。`);
      toast("一键查询并导出完成", "success");
    }
  } catch (e) {
    addLog("失败", `流程出错：${esc(e.message)}`);
  } finally {
    $("autoRunBtn").disabled = false;
  }
}

/* ============ 查询历史 ============ */
function bindHistory() {
  $("refreshHistoryBtn").addEventListener("click", loadHistory);
}

async function loadHistory() {
  try {
    const res = await fetch(`${API}/dbs/${state.conn}/history?limit=50`);
    const list = await res.json();
    const area = $("historyArea");
    if (!list.length) {
      area.innerHTML = `<p class="placeholder" style="padding:24px;text-align:center">暂无历史记录。</p>`;
      return;
    }
    area.innerHTML = list
      .map(
        (h) => `
        <div class="hist-item">
          <span class="hist-status ${h.success ? "ok" : "fail"}">${h.success ? "成功" : "失败"}</span>
          <div class="hist-sql">${esc(h.sqlText)}</div>
          <div class="hist-meta">
            ${h.querySource} · ${h.rowCount} 行 · ${h.executionTimeMs}ms<br/>
            ${new Date(h.executedAt).toLocaleString("zh-CN")}
          </div>
        </div>`
      )
      .join("");
  } catch {
    $("historyArea").innerHTML = `<p class="placeholder" style="padding:24px;color:var(--danger)">加载历史失败。</p>`;
  }
}

document.addEventListener("DOMContentLoaded", init);
