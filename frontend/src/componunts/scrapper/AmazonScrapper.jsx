import React, { useState, useEffect, useRef, useCallback } from "react";
import api from "../../utils/Api";

// ── Color helpers ────────────────────────────────────────────────────────────
const LOG_COLORS = {
  success: "text-emerald-400",
  error:   "text-red-400 font-bold",
  warning: "text-yellow-400",
  system:  "text-blue-400 font-bold",
  info:    "text-gray-200",
};

// ── Stat Card ─────────────────────────────────────────────────────────────────
const StatCard = ({ icon, label, value, sub, color = "green", pulse = false }) => (
  <div className="bg-gray-800/60 rounded-xl p-4 border border-gray-700/50 flex items-start gap-3">
    <div className={`p-2 rounded-lg bg-${color}-500/20 flex-shrink-0`}>
      <span className={`text-${color}-400 text-xl`}>{icon}</span>
    </div>
    <div>
      <p className="text-gray-400 text-xs font-medium">{label}</p>
      <p className={`text-white text-xl font-bold tabular-nums ${pulse ? "animate-pulse" : ""}`}>
        {typeof value === "number" ? value.toLocaleString("en-IN") : value}
      </p>
      {sub && <p className="text-gray-500 text-xs mt-0.5">{sub}</p>}
    </div>
  </div>
);

// ── Phase Badge ───────────────────────────────────────────────────────────────
const PhaseBadge = ({ phase }) => {
  const map = {
    running:    { label: "⚡ Running in Background",   color: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30" },
    completed:  { label: "✅ Complete",                color: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30" },
    idle:       { label: "⏸ Idle",                     color: "bg-gray-500/20 text-gray-400 border-gray-500/30" },
    error:      { label: "❌ Error",                   color: "bg-red-500/20 text-red-300 border-red-500/30" },
  };
  const info = map[phase] || map.idle;
  return (
    <span className={`text-xs font-semibold px-3 py-1 rounded-full border ${info.color}`}>
      {info.label}
    </span>
  );
};

// ── Main Component ────────────────────────────────────────────────────────────
const AmazonScrapper = () => {
  // Controls
  const [searchTerm, setSearchTerm] = useState("");
  const [pages, setPages] = useState("1");
  const [resume, setResume] = useState(false);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Task state
  const [taskId, setTaskId] = useState(null);
  const [taskData, setTaskData] = useState(null);
  const [logs, setLogs] = useState([]);
  const [phase, setPhase] = useState("idle");

  // DB stats (live)
  const [dbStats, setDbStats] = useState({
    total_products: 0,
    distinct_brands: 0,
    products_null_category_id: 0,
    top_categories: [], // Maps to top brands in Amazon case
    last_scrape_state: {},
  });

  // Session counters
  const [runStats, setRunStats] = useState({
    products_scraped: 0,
    products_inserted: 0,
    products_updated: 0,
    duplicates_prevented: 0,
  });

  const pollRef = useRef(null);
  const logEndRef = useRef(null);
  const prevLogsLen = useRef(0);

  // ── Auto-scroll logs ───────────────────────────────────────────────────────
  useEffect(() => {
    if (logs.length !== prevLogsLen.current) {
      logEndRef.current?.scrollIntoView({ behavior: "smooth" });
      prevLogsLen.current = logs.length;
    }
  }, [logs]);

  // ── Fetch DB stats ─────────────────────────────────────────────────────────
  const fetchDbStats = useCallback(async () => {
    try {
      const res = await api.get("/scrape_amazon/db-stats");
      setDbStats(res.data);
      const st = res.data.last_scrape_state || {};
      setRunStats({
        products_scraped: st.products_scraped || 0,
        products_inserted: st.products_inserted || 0,
        products_updated: st.products_updated || 0,
        duplicates_prevented: st.duplicates_prevented || 0,
      });
    } catch (_) {}
  }, []);

  // ── Initial load ───────────────────────────────────────────────────────────
  useEffect(() => {
    fetchDbStats();
    api.get("/scrape_amazon/status")
      .then(res => {
        if (res.data?.task) setTaskData(res.data.task);
        if (res.data?.task?.status === "RUNNING") {
          setLoading(true);
          setPhase("running");
          if (res.data.task.id) {
            setTaskId(res.data.task.id);
            startPolling(res.data.task.id);
          }
        }
      })
      .catch(() => {});
  }, [fetchDbStats]);

  // ── Cleanup poll on unmount ────────────────────────────────────────────────
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  // ── Log parser ─────────────────────────────────────────────────────────────
  const parseLogLine = (line) => {
    let type = "info";
    let msg = line;
    let ts = new Date().toLocaleTimeString("en-IN", { hour12: false });

    const parts = line.split(" | ");
    if (parts.length >= 3) {
      const tsMatch = parts[0].match(/\d{2}:\d{2}:\d{2}/);
      if (tsMatch) ts = tsMatch[0];
      const level = (parts[1] || "").trim();
      msg = parts.slice(2).join(" | ");
      if (["ERROR", "CRITICAL"].includes(level)) type = "error";
      else if (level === "WARNING") type = "warning";
      else if (level === "SUCCESS") type = "success";
      else if (level === "SYSTEM") type = "system";
    } else {
      const u = line.toUpperCase();
      if (u.includes("ERROR") || u.includes("FAILED") || u.includes("FATAL")) type = "error";
      else if (u.includes("SUCCESS") || u.includes("COMPLETE")) type = "success";
      else if (u.includes("WARNING") || u.includes("SKIP")) type = "warning";
      else if (line.startsWith("===") || line.includes("[Phase") || line.includes("[Config")) type = "system";
    }
    return { ts, msg, type };
  };

  // ── Start polling for task updates ─────────────────────────────────────────
  const startPolling = (tid) => {
    if (pollRef.current) clearInterval(pollRef.current);

    pollRef.current = setInterval(async () => {
      try {
        const taskRes = await api.get(`/tasks/${tid}`);
        const task = taskRes.data;
        setTaskData(task);

        try {
          const logRes = await api.get(`/tasks/${tid}/amazon-logs`);
          const lines = logRes.data.logs || [];
          if (lines.length > 0) {
            setLogs(lines.map(parseLogLine));
          }
        } catch (_) {}

        fetchDbStats();

        if (task.status) {
          const st = task.status.toLowerCase();
          if (st === "completed") setPhase("completed");
          else if (st === "error") setPhase("error");
          else if (st === "running") setPhase("running");
        }

        if (["COMPLETED", "ERROR", "STOPPED", "FAILED"].includes(task.status)) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setLoading(false);
          fetchDbStats();

          const finalMsg = task.status === "COMPLETED"
            ? `✅ Amazon scrape COMPLETED! ${task.total_found?.toLocaleString("en-IN") || ""} products found.`
            : `❌ Scraper ${task.status}: ${task.error_message || "Unknown error"}`;
          setLogs(prev => [...prev, {
            ts: new Date().toLocaleTimeString("en-IN"),
            msg: finalMsg,
            type: task.status === "COMPLETED" ? "success" : "error",
          }]);
        }
      } catch (_) {}
    }, 2500);
  };

  // ── Handle Scrape ──────────────────────────────────────────────────────────
  const handleScrape = async () => {
    if (!searchTerm.trim()) {
      setError("Please enter a search query.");
      return;
    }

    setError("");
    setLogs([]);
    setPhase("running");
    setLoading(true);

    const addLog = (msg, type = "system") =>
      setLogs(prev => [...prev, { ts: new Date().toLocaleTimeString("en-IN"), msg, type }]);

    addLog(`[SYSTEM] Initializing Amazon Automation Engine...`);
    addLog(`[CONFIG] Query: ${searchTerm} | Pages: ${pages} | Resume: ${resume}`);
    addLog(`[INFO] Scraper running in background — you can continue using the dashboard.`, "success");

    try {
      const res = await api.post("/scrape_amazon", {
        search_term: searchTerm,
        pages: parseInt(pages) || 1,
        resume,
      });

      const { task_id, message } = res.data;
      setTaskId(task_id);
      addLog(`[SYSTEM] Task started! Task ID: #${task_id}`, "success");
      addLog(`[INFO] ${message}`, "info");
      startPolling(task_id);

    } catch (err) {
      const msg = err.response?.data?.error || "Failed to start Amazon scraper.";
      setError(msg);
      addLog(`[ERROR] ${msg}`, "error");
      setLoading(false);
      setPhase("error");
    }
  };

  // ── Handle Stop ────────────────────────────────────────────────────────────
  const handleStop = async () => {
    try {
      await api.post("/scrape_amazon/stop", { task_id: taskId });
      setLogs(prev => [...prev, {
        ts: new Date().toLocaleTimeString("en-IN"),
        msg: "[SYSTEM] Stop signal sent to scraper.",
        type: "warning",
      }]);
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      setLoading(false);
      setPhase("idle");
    } catch (err) {
      setError(err.response?.data?.error || "Failed to stop scraper.");
    }
  };

  const progress = taskData?.progress || 0;
  const totalFound = taskData?.total_found || 0;

  return (
    <div className="min-h-screen p-6 space-y-6"
         style={{ background: "linear-gradient(135deg, #111827 0%, #0f172a 50%, #111827 100%)" }}>

      {/* ── Header ── */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4
                      bg-white/5 backdrop-blur-sm p-6 rounded-2xl border border-white/10 shadow-xl">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-3xl shadow-lg"
               style={{ background: "linear-gradient(135deg, #f59e0b, #d97706)" }}>
            📦
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2 flex-wrap">
              Amazon Automation System
              <PhaseBadge phase={phase} />
            </h1>
            <p className="text-gray-400 text-sm mt-1">
              Production-grade crawler · Real-time search extraction
            </p>
            {loading && (
              <p className="text-yellow-400 text-xs mt-1 animate-pulse">
                ⚡ Scraper is running in the background
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <div className="bg-white/5 rounded-xl px-4 py-2 border border-white/10 text-center">
            <p className="text-gray-400 text-xs">DB Products</p>
            <p className="text-green-400 font-bold text-lg">{dbStats.total_products.toLocaleString("en-IN")}</p>
          </div>
          <div className="bg-white/5 rounded-xl px-4 py-2 border border-white/10 text-center">
            <p className="text-gray-400 text-xs">Brands</p>
            <p className="text-purple-400 font-bold text-lg">{dbStats.distinct_brands.toLocaleString("en-IN")}</p>
          </div>
        </div>
      </div>

      {/* ── Progress Bar ── */}
      {loading && (
        <div className="bg-white/5 backdrop-blur-sm rounded-xl border border-white/10 p-4 space-y-2">
          <div className="flex justify-between text-xs text-gray-400 mb-1">
            <span>Overall Progress</span>
            <span className="text-white font-bold">{progress}% — {totalFound.toLocaleString("en-IN")} products found</span>
          </div>
          <div className="w-full h-3 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${progress}%`,
                background: "linear-gradient(90deg, #f59e0b, #d97706)",
                boxShadow: "0 0 12px rgba(245,158,11,0.5)",
              }}
            />
          </div>
          <p className="text-yellow-400 text-xs font-mono animate-pulse">
            {taskData?.status || "Processing..."} · Task #{taskId}
          </p>
        </div>
      )}

      {/* ── Main Grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* ── LEFT: Control Panel ── */}
        <div className="lg:col-span-4 space-y-4">
          <div className="bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10 p-5 space-y-5">
            <h2 className="text-white font-bold text-base flex items-center gap-2">🎛️ Control Panel</h2>

            {/* Search Query */}
            <div>
              <label className="text-gray-400 text-xs uppercase font-bold tracking-wider mb-1.5 block">
                Search Query
              </label>
              <input
                type="text"
                placeholder="e.g. laptops under 50000"
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                disabled={loading}
                className="w-full bg-gray-800/80 text-white text-sm rounded-xl border border-gray-700 px-3 py-2.5 outline-none focus:border-yellow-500 transition placeholder-gray-600"
              />
            </div>

            {/* Pages Limit */}
            <div>
              <label className="text-gray-400 text-xs uppercase font-bold tracking-wider mb-1.5 block">
                Pages to Scrape
              </label>
              <input
                type="number"
                min="1"
                max="20"
                value={pages}
                onChange={e => setPages(e.target.value)}
                disabled={loading}
                className="w-full bg-gray-800/80 text-white text-sm rounded-xl border border-gray-700 px-3 py-2.5 outline-none focus:border-yellow-500 transition placeholder-gray-600"
              />
            </div>

            {/* Resume Toggle */}
            <div className="flex items-center gap-3 bg-gray-800/40 rounded-xl p-3 border border-gray-700/50">
              <button
                onClick={() => !loading && setResume(r => !r)}
                className={`w-11 h-6 rounded-full transition-all relative ${resume ? "bg-yellow-500" : "bg-gray-600"}`}
              >
                <div className="absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all"
                     style={{ left: resume ? "22px" : "2px" }} />
              </button>
              <div>
                <p className="text-white text-sm font-medium">Resume session logs</p>
                <p className="text-gray-500 text-xs">Maintain counters from previous scrape</p>
              </div>
            </div>

            {/* Buttons */}
            <div className="space-y-2 pt-1">
              {!loading ? (
                <button
                  onClick={handleScrape}
                  className="w-full py-3.5 rounded-xl text-white font-bold text-sm flex items-center justify-center gap-2 transition hover:opacity-90 active:scale-95"
                  style={{ background: "linear-gradient(135deg, #f59e0b, #d97706)" }}
                >
                  <span>🚀</span> Start Amazon Scraper
                </button>
              ) : (
                <>
                  <button
                    onClick={handleStop}
                    className="w-full py-3.5 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition bg-red-500/20 border border-red-500/40 text-red-300 hover:bg-red-500/30"
                  >
                    <span className="w-4 h-4 border-2 border-red-400 border-t-transparent rounded-full animate-spin" />
                    Stop Scraper
                  </button>
                </>
              )}
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3">
                <p className="text-red-400 text-xs font-semibold">⚠️ {error}</p>
              </div>
            )}
          </div>

          {/* ── Top Brands ── */}
          {dbStats.top_categories.length > 0 && (
            <div className="bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10 p-4">
              <h3 className="text-white font-bold text-sm mb-3">📊 Top Brands Extracted</h3>
              <div className="space-y-1.5">
                {dbStats.top_categories.slice(0, 8).map((c, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className="w-full bg-gray-800 rounded-full h-1.5 flex-1">
                      <div
                        className="h-1.5 rounded-full bg-gradient-to-r from-yellow-500 to-amber-600"
                        style={{ width: `${Math.min(100, (c.count / (dbStats.top_categories[0]?.count || 1)) * 100)}%` }}
                      />
                    </div>
                    <span className="text-gray-400 text-xs w-36 truncate text-right" title={c.category}>{c.category}</span>
                    <span className="text-gray-500 text-xs w-14 text-right">{c.count.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ── RIGHT: Stats + Terminal ── */}
        <div className="lg:col-span-8 flex flex-col gap-4">

          {/* Live Stats Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard icon="🛒" label="Products Scraped" value={runStats.products_scraped}
                      pulse={loading} color="yellow" sub="this run" />
            <StatCard icon="✨" label="New Insertions"   value={runStats.products_inserted}
                      pulse={loading} color="blue" sub="new ASINs" />
            <StatCard icon="🛡️" label="Dupes Prevented"
                      value={runStats.duplicates_prevented}
                      color="green" />
            <StatCard icon="📦" label="Total in DB"      value={dbStats.total_products}
                      color="indigo" />
          </div>

          {/* ── Terminal ── */}
          <div className="flex-1 rounded-2xl overflow-hidden border border-gray-700/50 shadow-2xl"
               style={{ background: "#0d1117" }}>
            <div className="flex items-center justify-between px-4 py-2.5 bg-gray-900 border-b border-gray-700/50">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500" />
                <div className="w-3 h-3 rounded-full bg-yellow-500" />
                <div className="w-3 h-3 rounded-full bg-green-500" />
                <span className="text-gray-500 text-xs font-mono ml-2">amazon-scraper@worker</span>
              </div>
              <div className="flex items-center gap-2">
                {taskId && (
                  <span className="text-gray-500 text-xs font-mono">task #{taskId}</span>
                )}
                <span className={`text-xs font-bold px-2 py-0.5 rounded font-mono border ${
                  loading
                    ? "text-yellow-400 border-yellow-500/30 bg-yellow-500/10"
                    : "text-gray-500 border-gray-600/30 bg-gray-800"
                }`}>
                  {loading ? "● LIVE" : "○ IDLE"}
                </span>
              </div>
            </div>

            <div className="h-[420px] overflow-y-auto p-4 space-y-1 font-mono text-xs" id="terminal-body">
              {logs.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-gray-600 gap-3">
                  <span className="text-4xl">🤖</span>
                  <p className="text-center">Amazon Automation Engine ready.</p>
                  <p className="text-center text-gray-700">Enter a search query and click <strong className="text-gray-500">Start Amazon Scraper</strong>.</p>
                </div>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className="flex items-start gap-2 leading-relaxed">
                    <span className="text-gray-600 select-none flex-shrink-0">[{log.ts}]</span>
                    <span className={LOG_COLORS[log.type] || "text-gray-200"}>{log.msg}</span>
                  </div>
                ))
              )}
              <div ref={logEndRef} />
            </div>
          </div>

          <RecentHistory />
        </div>
      </div>
    </div>
  );
};

const RecentHistory = () => {
  const [history, setHistory] = useState([]);
  useEffect(() => {
    api.get("/scrape_amazon/history?limit=5")
      .then(r => setHistory(r.data || []))
      .catch(() => {});
  }, []);

  if (!history.length) return null;

  return (
    <div className="bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10 p-4">
      <h3 className="text-white font-bold text-sm mb-3">🕐 Recent Scrape History</h3>
      <div className="space-y-1.5">
        {history.map(t => (
          <div key={t.id}
               className="flex items-center justify-between text-xs bg-gray-800/50 rounded-xl px-4 py-2.5 border border-gray-700/30">
            <span className="text-gray-400 font-mono">#{t.id}</span>
            <span className="text-gray-300 flex-1 mx-4 truncate">{t.query}</span>
            <span className="text-yellow-400 font-mono mr-4">{(t.total_found || 0).toLocaleString("en-IN")} products</span>
            <span className={`px-2 py-0.5 rounded-full font-bold ${
              t.status === "COMPLETED" ? "bg-green-500/20 text-green-400" :
              t.status === "ERROR"     ? "bg-red-500/20 text-red-400" :
              t.status === "RUNNING"   ? "bg-yellow-500/20 text-yellow-400" :
                                          "bg-gray-600/20 text-gray-400"
            }`}>
              {t.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default AmazonScrapper;
