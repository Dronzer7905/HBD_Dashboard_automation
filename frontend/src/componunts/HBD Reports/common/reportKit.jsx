/**
 * Shared building blocks for the HBD Reports + Data Enrichment pages.
 *
 *  - useReport(url, params)   live data hook with a "refresh" that bypasses the backend cache
 *  - ReportLayout             page header (title, live timestamp, Refresh) + error / warning panels
 *  - Section                  same loading / error handling for one block of a multi-report page
 *  - KpiCard, ChartCard       cards
 *  - StatusBadge, FillBar     status (icon + label, never colour alone) and inline % bars
 *  - DataTable                sortable, searchable table with CSV download
 *  - SimpleBar, SimplePie     recharts wrappers with a colour-blind-checked palette
 *  - detailPath, DrillLink    links into the Detail Report with filters pre-set
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Card, CardBody, CardHeader, Typography, Spinner, Button } from "@material-tailwind/react";
import {
  ArrowPathIcon,
  ArrowDownTrayIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  XCircleIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  MagnifyingGlassIcon,
} from "@heroicons/react/24/solid";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell,
  LabelList,
} from "recharts";
import api from "../../../utils/Api";

// ─── Colours ────────────────────────────────────────────────────────────────
// Categorical order is fixed (validated for colour-blind separation) - never cycled.
export const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"];
export const OTHER_GRAY = "#b4b2a9";
// Ordered ranks (Rank 1 darkest -> Rank 5 lightest), one hue.
export const RANK_RAMP = ["#104281", "#1c5cab", "#2a78d6", "#5598e7", "#86b6ef"];
export const STATUS = {
  good: { color: "#0ca30c", text: "#006300", bg: "bg-green-50", label: "Good", Icon: CheckCircleIcon },
  warning: { color: "#fab219", text: "#8a5a00", bg: "bg-amber-50", label: "Needs work", Icon: ExclamationTriangleIcon },
  critical: { color: "#d03b3b", text: "#a12626", bg: "bg-red-50", label: "Critical", Icon: XCircleIcon },
};
const INK = { secondary: "#52514e", muted: "#898781", grid: "#e1e0d9", axis: "#c3c2b7" };

// ─── Formatting ─────────────────────────────────────────────────────────────
export const fmt = (v) => (v === null || v === undefined || Number.isNaN(Number(v)) ? "—" : Number(v).toLocaleString("en-IN"));
export const fmtPct = (v, d = 1) => (v === null || v === undefined ? "—" : `${Number(v).toFixed(d)}%`);
export const compact = (v) => {
  const n = Number(v || 0);
  if (Math.abs(n) >= 1e7) return `${(n / 1e7).toFixed(1)}Cr`;
  if (Math.abs(n) >= 1e5) return `${(n / 1e5).toFixed(1)}L`;
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return `${n}`;
};
const timeOf = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
};

// ─── Data hook ──────────────────────────────────────────────────────────────
export function useReport(url, params) {
  const [state, setState] = useState({
    loading: true, data: null, errors: [], error: null, generatedAt: null, cached: false,
  });
  const paramsKey = JSON.stringify(params || {});
  const latest = useRef(0); // only the newest request may update the page (filters change fast)

  const load = useCallback(
    async (refresh = false) => {
      const id = ++latest.current;
      setState((s) => ({ ...s, loading: true, error: null }));
      try {
        const res = await api.get(url, {
          params: { ...(params || {}), ...(refresh ? { refresh: true } : {}) },
          timeout: 300000,
        });
        if (id !== latest.current) return;
        const body = res.data || {};
        if (body.status !== "success") throw new Error(body.message || "Report failed");
        setState({
          loading: false, data: body.data, errors: body.errors || [], error: null,
          generatedAt: body.generated_at, cached: !!body.cached,
        });
      } catch (e) {
        if (id !== latest.current) return;
        const msg = e?.response?.data?.message || e?.message || "Could not load the report.";
        setState((s) => ({ ...s, loading: false, error: msg }));
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [url, paramsKey],
  );

  useEffect(() => {
    load(false);
  }, [load]);

  const mutate = useCallback((updater) => setState((s) => ({ ...s, data: updater(s.data) })), []);
  return { ...state, reload: () => load(true), mutate };
}

// ─── Layout pieces ──────────────────────────────────────────────────────────
function Warnings({ errors }) {
  const [open, setOpen] = useState(false);
  if (!errors || errors.length === 0) return null;
  return (
    <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
      <button type="button" onClick={() => setOpen(!open)} className="flex w-full items-center gap-2 text-left">
        <ExclamationTriangleIcon className="h-5 w-5 text-amber-700" />
        <span className="text-sm font-semibold text-amber-900">
          {errors.length} check{errors.length > 1 ? "s" : ""} could not run - the rest of the report is still live
        </span>
        <span className="ml-auto text-xs text-amber-800">{open ? "Hide" : "Show details"}</span>
      </button>
      {open && (
        <ul className="mt-2 list-disc space-y-1 pl-8 text-xs text-amber-900">
          {errors.map((e, i) => (
            <li key={i}>
              <span className="font-semibold">{e.step}:</span> {e.error}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Loading({ label = "Loading live data..." }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16">
      <Spinner className="h-8 w-8 text-blue-500" />
      <Typography className="animate-pulse text-sm font-medium text-gray-600">{label}</Typography>
    </div>
  );
}

function ErrorBox({ message, onRetry }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-4">
      <div className="flex items-start gap-2">
        <XCircleIcon className="mt-0.5 h-5 w-5 flex-none text-red-600" />
        <div className="flex-1">
          <Typography className="text-sm font-semibold text-red-800">Could not load this report</Typography>
          <Typography className="mt-1 break-words text-xs text-red-700">{message}</Typography>
        </div>
        {onRetry && (
          <Button size="sm" variant="outlined" color="red" onClick={onRetry}>
            Try again
          </Button>
        )}
      </div>
    </div>
  );
}

export function LiveStamp({ report }) {
  if (!report?.generatedAt) return null;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-green-200 bg-green-50 px-2.5 py-1 text-xs font-medium text-green-800">
      <span className="h-2 w-2 rounded-full bg-green-600" />
      Live DB · {timeOf(report.generatedAt)}
      {report.cached ? " (cached)" : ""}
    </span>
  );
}

export function RefreshButton({ onClick, loading }) {
  return (
    <Button size="sm" variant="outlined" color="blue-gray" className="flex items-center gap-2" onClick={onClick} disabled={loading}>
      <ArrowPathIcon className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
      Refresh
    </Button>
  );
}

/** Full page wrapper for one report. children is a function (data) => JSX. */
export function ReportLayout({ title, subtitle, report, actions, children }) {
  return (
    <div className="mb-12 mt-6 px-1 md:px-4">
      <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <Typography variant="h4" color="blue-gray" className="font-bold">
            {title}
          </Typography>
          {subtitle && (
            <Typography variant="small" className="mt-1 max-w-3xl text-gray-600">
              {subtitle}
            </Typography>
          )}
        </div>
        <div className="flex flex-none flex-wrap items-center justify-end gap-2">
          <LiveStamp report={report} />
          {actions}
          <RefreshButton onClick={report.reload} loading={report.loading} />
        </div>
      </div>
      {report.error && !report.data ? (
        <ErrorBox message={report.error} onRetry={report.reload} />
      ) : !report.data ? (
        <Loading />
      ) : (
        <>
          {report.error && <div className="mb-4"><ErrorBox message={report.error} onRetry={report.reload} /></div>}
          <Warnings errors={report.errors} />
          {children(report.data)}
        </>
      )}
    </div>
  );
}

/** One block on a page that combines several reports (e.g. the Overview). */
export function Section({ report, children, label }) {
  if (report.error && !report.data) return <ErrorBox message={report.error} onRetry={report.reload} />;
  if (!report.data) return <Loading label={label} />;
  return children(report.data);
}

export function KpiCard({ label, value, sub, accent = SERIES[0], status }) {
  const st = status ? STATUS[status] : null;
  return (
    <Card className="border border-blue-gray-100 shadow-sm">
      <CardBody className="p-4">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: st ? st.color : accent }} />
          <Typography className="text-xs font-semibold uppercase tracking-wide text-blue-gray-500">{label}</Typography>
        </div>
        <Typography variant="h4" color="blue-gray" className="mt-2 font-bold">
          {value}
        </Typography>
        {sub && <Typography className="mt-1 text-xs text-gray-600">{sub}</Typography>}
      </CardBody>
    </Card>
  );
}

export function ChartCard({ title, subtitle, children, right, className = "" }) {
  return (
    <Card className={`border border-blue-gray-100 shadow-sm ${className}`}>
      <CardHeader floated={false} shadow={false} className="m-0 flex items-start justify-between gap-2 rounded-none px-5 pt-4">
        <div>
          <Typography variant="h6" color="blue-gray">
            {title}
          </Typography>
          {subtitle && <Typography className="mt-0.5 text-xs text-gray-600">{subtitle}</Typography>}
        </div>
        {right}
      </CardHeader>
      <CardBody className="px-5 pb-5 pt-3">{children}</CardBody>
    </Card>
  );
}

export function StatusBadge({ status, label }) {
  const st = STATUS[status] || STATUS.warning;
  const Icon = st.Icon;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${st.bg}`} style={{ color: st.text }}>
      <Icon className="h-3.5 w-3.5" style={{ color: st.color }} />
      {label || st.label}
    </span>
  );
}

export function FillBar({ value, color = SERIES[0] }) {
  const v = Math.max(0, Math.min(100, Number(value || 0)));
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-gray-200">
        <div className="h-full rounded-full" style={{ width: `${v}%`, background: color }} />
      </div>
      <span className="w-14 text-right text-xs tabular-nums text-gray-700">{fmtPct(value)}</span>
    </div>
  );
}

// ─── Table ──────────────────────────────────────────────────────────────────
function toCsv(columns, rows) {
  const esc = (v) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const head = columns.map((c) => esc(c.label)).join(",");
  const body = rows.map((r) => columns.map((c) => esc(c.csv ? c.csv(r) : r[c.key])).join(","));
  return [head, ...body].join("\n");
}

export function downloadCsv(filename, columns, rows) {
  const blob = new Blob(["﻿" + toCsv(columns, rows)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename.endsWith(".csv") ? filename : `${filename}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/**
 * columns: [{ key, label, align, render(row), sortValue(row), csv(row), filterValue(row),
 *             filter (false = no filter box), hidden (CSV only), nowrap }]
 *
 * Every visible column gets a filter box under its header:
 *   - columns with only a few different values get a dropdown
 *   - number columns accept  >1000  <50  >=10  <=5  =0  or a plain number
 *   - text columns match anything containing what you type (not case sensitive)
 */
const rawFilterValue = (c, r) => {
  const v = c.filterValue ? c.filterValue(r) : c.csv ? c.csv(r) : r[c.key];
  if (Array.isArray(v)) return v.map((x) => (typeof x === "object" && x ? x.name ?? "" : x)).join(", ");
  return v;
};

function matchesNumber(value, expr) {
  const m = /^(>=|<=|>|<|=)?\s*(-?[\d,.]+)$/.exec(expr.trim());
  if (!m) return null; // not a number expression -> caller falls back to text match
  const n = Number(value);
  if (value === null || value === undefined || value === "" || Number.isNaN(n)) return false;
  const target = Number(m[2].replace(/,/g, ""));
  switch (m[1]) {
    case ">": return n > target;
    case "<": return n < target;
    case ">=": return n >= target;
    case "<=": return n <= target;
    default: return n === target;
  }
}

export function DataTable({
  columns, rows, filename = "report", searchable = false, searchKeys, maxHeight = 520,
  initialSort, footer, toolbar, emptyText = "No rows.", filters: showFilters = true,
}) {
  const [sort, setSort] = useState(initialSort || null);
  const [query, setQuery] = useState("");
  const [colFilters, setColFilters] = useState({});

  // What kind of filter each column gets (dropdown / number / text)
  const filterMeta = useMemo(() => {
    const meta = {};
    for (const c of columns) {
      if (c.hidden || c.filter === false) continue;
      const vals = (rows || []).map((r) => rawFilterValue(c, r)).filter((v) => v !== null && v !== undefined && v !== "");
      const numeric = vals.length > 0 && vals.every((v) => typeof v === "number");
      const distinct = [...new Set(vals.map((v) => String(v)))];
      if (!numeric && distinct.length > 1 && distinct.length <= 12) {
        meta[c.key] = { type: "select", options: distinct.sort((a, b) => a.localeCompare(b)) };
      } else {
        meta[c.key] = { type: numeric ? "number" : "text" };
      }
    }
    return meta;
  }, [columns, rows]);

  const activeFilters = Object.entries(colFilters).filter(([, v]) => v !== undefined && String(v).trim() !== "");

  const filtered = useMemo(() => {
    let out = rows || [];
    if (query.trim()) {
      const q = query.trim().toLowerCase();
      const keys = searchKeys || columns.map((c) => c.key);
      out = out.filter((r) => keys.some((k) => String(r[k] ?? "").toLowerCase().includes(q)));
    }
    for (const [key, fv] of activeFilters) {
      const col = columns.find((c) => c.key === key);
      const meta = filterMeta[key];
      if (!col || !meta) continue;
      const f = String(fv).trim();
      out = out.filter((r) => {
        const v = rawFilterValue(col, r);
        if (meta.type === "select") return String(v ?? "") === f;
        if (meta.type === "number") {
          const res = matchesNumber(v, f);
          if (res !== null) return res;
        }
        return String(v ?? "").toLowerCase().includes(f.toLowerCase());
      });
    }
    if (sort) {
      const col = columns.find((c) => c.key === sort.key);
      const val = (r) => (col?.sortValue ? col.sortValue(r) : r[sort.key]);
      out = [...out].sort((a, b) => {
        const x = val(a);
        const y = val(b);
        if (x === y) return 0;
        if (x === null || x === undefined) return 1;
        if (y === null || y === undefined) return -1;
        const cmp = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
        return sort.dir === "asc" ? cmp : -cmp;
      });
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, query, sort, columns, searchKeys, colFilters, filterMeta]);

  const visible = columns.filter((c) => !c.hidden);

  const toggleSort = (key) =>
    setSort((s) => (s && s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "desc" }));

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {searchable && (
          <div className="relative">
            <MagnifyingGlassIcon className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-gray-500" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search..."
              className="w-56 rounded-md border border-gray-300 py-2 pl-8 pr-3 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
        )}
        {toolbar}
        {activeFilters.length > 0 && (
          <Button size="sm" variant="outlined" color="blue-gray" className="py-1.5" onClick={() => setColFilters({})}>
            Clear {activeFilters.length} filter{activeFilters.length > 1 ? "s" : ""}
          </Button>
        )}
        <span className="text-xs text-gray-600">
          {fmt(filtered.length)} {(rows || []).length !== filtered.length ? `of ${fmt((rows || []).length)} ` : ""}row
          {filtered.length === 1 ? "" : "s"}
        </span>
        <Button
          size="sm"
          variant="text"
          color="blue-gray"
          className="ml-auto flex items-center gap-1.5"
          onClick={() => downloadCsv(filename, columns, filtered)}
        >
          <ArrowDownTrayIcon className="h-4 w-4" /> CSV
        </Button>
      </div>
      <div className="overflow-auto rounded-lg border border-blue-gray-100" style={{ maxHeight }}>
        <table className="w-full border-collapse text-left">
          <thead className="sticky top-0 z-10 bg-blue-gray-50">
            <tr>
              {visible.map((c) => (
                <th
                  key={c.key}
                  onClick={() => toggleSort(c.key)}
                  className={`cursor-pointer select-none whitespace-nowrap border-b border-blue-gray-100 px-3 py-2.5 text-xs font-bold uppercase tracking-wide text-blue-gray-600 ${
                    c.align === "right" ? "text-right" : ""
                  }`}
                >
                  <span className="inline-flex items-center gap-1">
                    {c.label}
                    {sort?.key === c.key &&
                      (sort.dir === "asc" ? <ChevronUpIcon className="h-3 w-3" /> : <ChevronDownIcon className="h-3 w-3" />)}
                  </span>
                </th>
              ))}
            </tr>
            {showFilters && (
              <tr className="bg-white">
                {visible.map((c) => {
                  const meta = filterMeta[c.key];
                  const val = colFilters[c.key] ?? "";
                  const set = (v) => setColFilters((f) => ({ ...f, [c.key]: v }));
                  const cls = `w-full min-w-[70px] rounded border px-2 py-1 text-xs font-normal normal-case text-blue-gray-800 focus:border-blue-500 focus:outline-none ${
                    val ? "border-blue-400 bg-blue-50" : "border-gray-300"
                  }`;
                  return (
                    <th key={c.key} className="border-b border-blue-gray-100 px-2 py-1.5">
                      {!meta ? null : meta.type === "select" ? (
                        <select value={val} onChange={(e) => set(e.target.value)} className={cls} aria-label={`Filter ${c.label}`}>
                          <option value="">All</option>
                          {meta.options.map((o) => (
                            <option key={o} value={o}>
                              {o}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          value={val}
                          onChange={(e) => set(e.target.value)}
                          placeholder={meta.type === "number" ? "e.g. >1000" : "Filter..."}
                          className={cls}
                          aria-label={`Filter ${c.label}`}
                        />
                      )}
                    </th>
                  );
                })}
              </tr>
            )}
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={visible.length} className="px-3 py-6 text-center text-sm text-gray-500">
                  {emptyText}
                </td>
              </tr>
            )}
            {filtered.map((r, i) => (
              <tr key={i} className="border-b border-blue-gray-50 hover:bg-blue-gray-50/50">
                {visible.map((c) => (
                  <td
                    key={c.key}
                    className={`px-3 py-2 align-top text-sm text-blue-gray-800 ${c.align === "right" ? "whitespace-nowrap text-right tabular-nums" : ""} ${c.nowrap ? "whitespace-nowrap" : ""}`}
                  >
                    {c.render ? c.render(r) : r[c.key] ?? "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
          {footer && (
            <tfoot className="sticky bottom-0 bg-blue-gray-50 font-semibold">
              <tr>
                {visible.map((c) => (
                  <td key={c.key} className={`px-3 py-2 text-sm ${c.align === "right" ? "text-right tabular-nums" : ""}`}>
                    {footer[c.key] ?? ""}
                  </td>
                ))}
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}

// ─── Charts ─────────────────────────────────────────────────────────────────
const axisProps = { tick: { fontSize: 11, fill: INK.secondary }, axisLine: { stroke: INK.axis }, tickLine: false };

/** Keep a pie readable: biggest (max-1) slices + "Other". */
export function foldForPie(rows, max = 6, nameKey = "name", valueKey = "value") {
  const sorted = [...(rows || [])].filter((r) => Number(r[valueKey]) > 0).sort((a, b) => b[valueKey] - a[valueKey]);
  if (sorted.length <= max) return sorted.map((r) => ({ name: r[nameKey], value: Number(r[valueKey]) }));
  const head = sorted.slice(0, max - 1).map((r) => ({ name: r[nameKey], value: Number(r[valueKey]) }));
  const rest = sorted.slice(max - 1).reduce((s, r) => s + Number(r[valueKey]), 0);
  return [...head, { name: `Other (${sorted.length - (max - 1)})`, value: rest, isOther: true }];
}

/**
 * bars: [{ key, label, color }]. horizontal=true puts categories on the Y axis
 * (better for long names). stacked=true stacks the series.
 */
export function SimpleBar({
  data, xKey = "name", bars, height = 320, horizontal = false, stacked = false,
  valueFormatter = fmt, showLegend, showValues = false, yWidth = 130,
}) {
  const legend = showLegend ?? bars.length > 1;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={data}
        layout={horizontal ? "vertical" : "horizontal"}
        margin={{ top: 8, right: showValues && horizontal ? 56 : 16, left: 4, bottom: horizontal ? 4 : 28 }}
        barCategoryGap="22%"
        barGap={2}
      >
        <CartesianGrid stroke={INK.grid} vertical={horizontal} horizontal={!horizontal} />
        {horizontal ? (
          <>
            <XAxis type="number" {...axisProps} tickFormatter={compact} />
            <YAxis type="category" dataKey={xKey} width={yWidth} {...axisProps} interval={0} />
          </>
        ) : (
          <>
            <XAxis dataKey={xKey} {...axisProps} interval={0} angle={data?.length > 6 ? -25 : 0} textAnchor={data?.length > 6 ? "end" : "middle"} height={data?.length > 6 ? 64 : 30} />
            <YAxis {...axisProps} tickFormatter={compact} width={52} />
          </>
        )}
        <Tooltip formatter={(v, n) => [valueFormatter(v), n]} cursor={{ fill: "rgba(42,120,214,0.06)" }} />
        {legend && <Legend wrapperStyle={{ fontSize: 12 }} iconType="circle" />}
        {bars.map((b, i) => (
          <Bar
            key={b.key}
            dataKey={b.key}
            name={b.label || b.key}
            fill={b.color || SERIES[i]}
            stackId={stacked ? "s" : undefined}
            radius={stacked ? (i === bars.length - 1 ? (horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]) : 0) : horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]}
            maxBarSize={38}
            stroke="#ffffff"
            strokeWidth={stacked ? 1 : 0}
          >
            {showValues && !stacked && (
              <LabelList dataKey={b.key} position={horizontal ? "right" : "top"} formatter={valueFormatter} style={{ fontSize: 11, fill: INK.secondary }} />
            )}
          </Bar>
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Donut with a value legend (name, value, share) - identity never relies on colour alone. */
export function SimplePie({ data, colors, height = 260, valueFormatter = fmt, stack = false }) {
  const total = (data || []).reduce((s, d) => s + Number(d.value || 0), 0);
  const colorFor = (d, i) => (d.color ? d.color : d.isOther ? OTHER_GRAY : (colors || SERIES)[i % (colors || SERIES).length]);
  if (!total) {
    return <Typography className="py-10 text-center text-sm text-gray-500">No data to chart.</Typography>;
  }
  return (
    <div className={`flex flex-col items-center gap-4 ${stack ? "" : "sm:flex-row"}`}>
      <div className={`h-full w-full ${stack ? "max-w-[280px]" : "sm:w-1/2"}`} style={{ height: stack ? Math.min(height, 220) : height }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius="55%" outerRadius="90%" paddingAngle={1} stroke="#ffffff" strokeWidth={2} isAnimationActive={false}>
              {data.map((d, i) => (
                <Cell key={d.name} fill={colorFor(d, i)} />
              ))}
            </Pie>
            <Tooltip formatter={(v, n) => [`${valueFormatter(v)} (${((v * 100) / total).toFixed(1)}%)`, n]} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className={`w-full space-y-1.5 ${stack ? "" : "sm:w-1/2"}`}>
        {data.map((d, i) => (
          <li key={d.name} className="flex items-center gap-2 text-sm">
            <span className="h-2.5 w-2.5 flex-none rounded-full" style={{ background: colorFor(d, i) }} />
            <span className="min-w-0 flex-1 truncate text-blue-gray-800" title={d.name}>{d.name}</span>
            <span className="whitespace-nowrap tabular-nums text-blue-gray-700">{valueFormatter(d.value)}</span>
            <span className="w-12 flex-none text-right text-xs tabular-nums text-gray-600">{((d.value * 100) / total).toFixed(1)}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export const reportPath = (p) => `/dashboard/hbd-reports${p}`;

/** Link to the Detail Report with filters already set, e.g. detailPath({ list: "city", rank: 1 }). */
export const detailPath = (params) => {
  const qs = new URLSearchParams(
    Object.entries(params || {}).filter(([, v]) => v !== null && v !== undefined && v !== ""),
  ).toString();
  return reportPath(`/detail${qs ? `?${qs}` : ""}`);
};

/** A number (or any text) that opens the list behind it. */
export function DrillLink({ to, children, title = "Open the full list" }) {
  return (
    <Link to={detailPath(to)} title={title} className="font-medium text-blue-700 underline decoration-blue-300 underline-offset-2 hover:decoration-blue-700">
      {children}
    </Link>
  );
}
