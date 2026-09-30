import React, { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Button, Spinner, Typography } from "@material-tailwind/react";
import {
  ArrowDownTrayIcon, ChevronDownIcon, ChevronUpIcon, ChevronLeftIcon, ChevronRightIcon, XMarkIcon,
} from "@heroicons/react/24/solid";
import {
  useReport, ReportLayout, KpiCard, ChartCard, SimpleBar, SimplePie, StatusBadge, downloadCsv,
  SERIES, RANK_RAMP, OTHER_GRAY, STATUS, fmt, fmtPct,
} from "./common/reportKit";
import api from "../../utils/Api";

/**
 * Detail Report - the full list behind every number in the other reports.
 * e.g. "Rank 1 has 181 cities" -> which 181 cities, their state, how many
 * records each has in the data, and which are still pending.
 *
 * Everything lives in the URL (?list=city&rank=1&status=pending), so a
 * filtered view can be opened from the Count / Ranking reports or shared.
 * Filtering, sorting and paging run in the database.
 */

const LISTS = [
  { group: "Master lists", items: [
    ["city", "City"], ["area", "Area"], ["state", "State"], ["country", "Country"],
    ["business_category", "Business Category"], ["product_category", "Product Category"], ["pincode", "Pincode"],
  ] },
  { group: "Location master", items: [["location", "All locations"]] },
  { group: "Rank tables", items: [["top_cities", "Top cities rank"], ["top_categories", "Top categories rank"]] },
];
const FILTER_KEYS = ["q", "parent", "type", "level", "rank", "status", "min_records", "max_records"];
const PAGE_SIZES = [25, 50, 100, 200, 500];

const rankLabel = (r) => (r === null || r === undefined ? "Unranked" : `Rank ${r}`);
const rankColor = (label) => {
  const m = /^Rank (\d+)$/.exec(label || "");
  if (m && Number(m[1]) >= 1 && Number(m[1]) <= 5) return RANK_RAMP[Number(m[1]) - 1];
  return label === "Unranked" ? "#898781" : OTHER_GRAY;
};

// Records filter box accepts: 0   >10   >=10   <5   <=5   =3   10-50
function parseRecords(text) {
  const t = (text || "").replace(/[,\s]/g, "");
  if (!t) return { min_records: "", max_records: "" };
  let m = /^(\d+)-(\d+)$/.exec(t);
  if (m) return { min_records: m[1], max_records: m[2] };
  m = /^(>=|<=|>|<|=)?(\d+)$/.exec(t);
  if (!m) return null;
  const n = Number(m[2]);
  switch (m[1]) {
    case ">": return { min_records: String(n + 1), max_records: "" };
    case ">=": return { min_records: String(n), max_records: "" };
    case "<": return { min_records: "", max_records: String(Math.max(n - 1, 0)) };
    case "<=": return { min_records: "", max_records: String(n) };
    default: return { min_records: String(n), max_records: String(n) };
  }
}
function recordsText(min, max) {
  if (min && max) return min === max ? `=${min}` : `${min}-${max}`;
  if (min) return `>=${min}`;
  if (max) return `<=${max}`;
  return "";
}

/** Text box that waits until you stop typing before it filters. */
function useDebounced(value, onCommit, delay = 450) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  useEffect(() => {
    if (draft === value) return undefined;
    const t = setTimeout(() => onCommit(draft), delay);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft]);
  return [draft, setDraft];
}

const inputCls = (active) =>
  `w-full min-w-[80px] rounded border px-2 py-1 text-xs font-normal normal-case text-blue-gray-800 focus:border-blue-500 focus:outline-none ${
    active ? "border-blue-400 bg-blue-50" : "border-gray-300 bg-white"
  }`;

function TextFilter({ value, onChange, placeholder, label }) {
  const [draft, setDraft] = useDebounced(value, onChange);
  return (
    <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={placeholder} aria-label={`Filter ${label}`} className={inputCls(!!value)} />
  );
}

function RecordsFilter({ min, max, onChange, label }) {
  const current = recordsText(min, max);
  const [bad, setBad] = useState(false);
  const [draft, setDraft] = useDebounced(current, (text) => {
    const parsed = parseRecords(text);
    setBad(!parsed);
    if (parsed) onChange(parsed);
  });
  return (
    <input
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      placeholder="e.g. 0  >10  5-50"
      title="0 = no records · >10 · >=10 · <5 · 10-50"
      aria-label={`Filter ${label}`}
      className={`${inputCls(!!current)} ${bad ? "border-red-400 bg-red-50" : ""}`}
    />
  );
}

function SelectFilter({ value, onChange, options, label }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={`Filter ${label}`} className={inputCls(!!value)}>
      <option value="">All</option>
      {options.map(([v, l]) => (
        <option key={v} value={v}>
          {l}
        </option>
      ))}
    </select>
  );
}

export function DetailReport() {
  const [sp, setSp] = useSearchParams();
  const list = sp.get("list") || "city";
  const get = (k, d = "") => sp.get(k) ?? d;
  const filters = Object.fromEntries(FILTER_KEYS.map((k) => [k, get(k)]).filter(([, v]) => v !== ""));
  const sort = get("sort", "name");
  const dir = get("dir", "asc");
  const page = Math.max(Number(get("page", "1")) || 1, 1);
  const pageSize = Number(get("page_size", "50")) || 50;

  // Any filter change goes back to page 1
  const update = (changes, keepPage = false) => {
    const next = new URLSearchParams(sp);
    Object.entries(changes).forEach(([k, v]) => (v === "" || v === null || v === undefined ? next.delete(k) : next.set(k, String(v))));
    if (!keepPage) next.delete("page");
    setSp(next, { replace: true });
  };
  const setFilter = (k) => (v) => update({ [k]: v });
  const clearFilters = () => update(Object.fromEntries(FILTER_KEYS.map((k) => [k, ""])));
  const chooseList = (key) => setSp(new URLSearchParams({ list: key }), { replace: false });

  const summary = useReport(`/hbd-reports/detail/${list}`, filters);
  const rows = useReport(`/hbd-reports/detail/${list}/rows`, { ...filters, sort, dir, page, page_size: pageSize });
  const report = { ...summary, reload: () => { summary.reload(); rows.reload(); } };
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState(null);

  const listLabel = useMemo(() => LISTS.flatMap((g) => g.items).find(([k]) => k === list)?.[1] || list, [list]);
  const activeCount = FILTER_KEYS.filter((k) => get(k) !== "").length;

  const picker = (
    <div className="mb-5 space-y-2">
      {LISTS.map((g) => (
        <div key={g.group} className="flex flex-wrap items-center gap-2">
          <span className="w-32 flex-none text-xs font-semibold uppercase tracking-wide text-blue-gray-500">{g.group}</span>
          {g.items.map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => chooseList(key)}
              className={`rounded-full border px-3 py-1 text-sm font-medium transition ${
                key === list ? "border-blue-600 bg-blue-600 text-white" : "border-blue-gray-200 bg-white text-blue-gray-800 hover:border-blue-400"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      ))}
    </div>
  );

  return (
    <ReportLayout
      title="Detail Report"
      subtitle="The full list behind every total - for example which cities are in Rank 1, their state, how many records each one has in the data, and which are still pending. Every column can be filtered and sorted; click a rank to see only that rank."
      report={report}
    >
      {(data) => {
        const meta = data.meta || {};
        if (meta.available === false) {
          return (
            <>
              {picker}
              <ChartCard title={listLabel}>
                <Typography className="text-sm text-gray-700">The master table for this list does not exist in this database yet.</Typography>
              </ChartCard>
            </>
          );
        }
        const s = data.summary || {};
        const byRank = data.by_rank || [];
        const options = data.options || {};
        const recLabel = meta.records_label || "Records in data";
        const pageRows = rows.data?.rows || [];
        const totalPages = Math.max(Math.ceil((s.total || 0) / pageSize), 1);
        const from = s.total ? (page - 1) * pageSize + 1 : 0;
        const to = Math.min(page * pageSize, s.total || 0);

        const rankOptions = [
          ...byRank.filter((b) => b.rank !== null).map((b) => [String(b.rank), b.label]),
          ...(byRank.some((b) => b.rank !== null && b.rank > 5) ? [["6+", "Rank 6 and above"]] : []),
          ...(byRank.some((b) => b.rank === null) ? [["none", "Unranked"]] : []),
        ];
        // keep a rank that came in from a link visible even if it has no rows now
        if (filters.rank && !rankOptions.some(([v]) => v === filters.rank)) {
          rankOptions.push([filters.rank, filters.rank === "none" ? "Unranked" : filters.rank.endsWith("+") ? `Rank ${filters.rank}` : `Rank ${filters.rank}`]);
        }

        const columns = [
          { key: "no", label: "#", sortable: false, render: (_, i) => <span className="tabular-nums text-gray-500">{fmt(from + i)}</span> },
          {
            key: "name", label: meta.name_label || "Name",
            filter: <TextFilter value={get("q")} onChange={setFilter("q")} placeholder="Search name..." label="name" />,
            render: (r) => <span className="font-semibold">{r.name ?? "—"}</span>,
          },
          meta.parent_label && {
            key: "parent", label: meta.parent_label,
            filter: <TextFilter value={get("parent")} onChange={setFilter("parent")} placeholder={`${meta.parent_label}... (none = blank)`} label={meta.parent_label} />,
            render: (r) => r.parent ?? <span className="text-gray-400">—</span>,
          },
          meta.has_type && {
            key: "type", label: "Type",
            filter: <SelectFilter value={get("type")} onChange={setFilter("type")} options={(options.type || []).map((t) => [t, t])} label="type" />,
            render: (r) => r.location_type ?? "—",
          },
          meta.has_level && {
            key: "level", label: "Level", align: "right",
            filter: <SelectFilter value={get("level")} onChange={setFilter("level")} options={(options.level || []).map((l) => [String(l), `Level ${l}`])} label="level" />,
            render: (r) => r.level ?? "—",
          },
          meta.has_rank && {
            key: "rank", label: "Rank", align: "right",
            filter: <SelectFilter value={get("rank")} onChange={setFilter("rank")} options={rankOptions} label="rank" />,
            render: (r) => (r.rank === null ? <span className="text-gray-500">Unranked</span> : r.rank),
          },
          {
            key: "records", label: recLabel, align: "right",
            filter: <RecordsFilter min={get("min_records")} max={get("max_records")} onChange={(v) => update(v)} label={recLabel} />,
            render: (r) => fmt(r.records),
          },
          {
            key: "status", label: "Status", sortable: false,
            filter: <SelectFilter value={get("status")} onChange={setFilter("status")} options={[["has_data", "Has data"], ["pending", "Pending"]]} label="status" />,
            render: (r) => <StatusBadge status={r.status === "Has data" ? "good" : "critical"} label={r.status} />,
          },
        ].filter(Boolean);

        const csvColumns = [
          { key: "name", label: meta.name_label || "Name" },
          ...(meta.parent_label ? [{ key: "parent", label: meta.parent_label }] : []),
          ...(meta.has_type ? [{ key: "location_type", label: "Type" }] : []),
          ...(meta.has_level ? [{ key: "level", label: "Level" }] : []),
          ...(meta.has_rank ? [{ key: "rank", label: "Rank", csv: (r) => (r.rank === null ? "Unranked" : r.rank) }] : []),
          { key: "records", label: recLabel },
          { key: "status", label: "Status" },
        ];

        const toggleSort = (key) => {
          if (sort === key) update({ dir: dir === "asc" ? "desc" : "asc" }, true);
          else update({ sort: key, dir: key === "records" || key === "rank" ? (key === "rank" ? "asc" : "desc") : "asc" }, true);
        };

        const downloadAll = async () => {
          setDownloading(true);
          setDownloadError(null);
          try {
            const res = await api.get(`/hbd-reports/detail/${list}/rows`, { params: { ...filters, sort, dir, export: 1 }, timeout: 300000 });
            if (res.data?.status !== "success") throw new Error(res.data?.message || "Download failed");
            const parts = [list, ...Object.entries(filters).map(([k, v]) => `${k}-${v}`)].join("_").replace(/[^\w.+-]+/g, "_");
            downloadCsv(`detail_${parts}`, csvColumns, res.data.data.rows || []);
          } catch (e) {
            setDownloadError(e?.response?.data?.message || e?.message || "Download failed");
          } finally {
            setDownloading(false);
          }
        };

        const chips = FILTER_KEYS.filter((k) => get(k) !== "" && !(k === "max_records" && get("min_records") !== "")).map((k) => {
          let text;
          if (k === "q") text = `Name contains "${get(k)}"`;
          else if (k === "parent") text = get(k).toLowerCase() === "none" ? `No ${meta.parent_label || "parent"}` : `${meta.parent_label || "Parent"} contains "${get(k)}"`;
          else if (k === "type") text = `Type: ${get(k)}`;
          else if (k === "level") text = `Level ${get(k)}`;
          else if (k === "rank") text = get(k) === "none" ? "Unranked" : `Rank ${get(k)}`;
          else if (k === "status") text = get(k) === "pending" ? "Pending only" : "Has data only";
          else text = `${recLabel}: ${recordsText(get("min_records"), get("max_records"))}`;
          const clear = k === "min_records" || k === "max_records" ? { min_records: "", max_records: "" } : { [k]: "" };
          return (
            <span key={k} className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-900">
              {text}
              <button type="button" onClick={() => update(clear)} aria-label={`Remove filter ${text}`} className="rounded-full p-0.5 hover:bg-blue-100">
                <XMarkIcon className="h-3.5 w-3.5" />
              </button>
            </span>
          );
        });

        const rankChart = byRank.map((b) => ({ name: b.label, "Has data": b.has_data, Pending: b.pending }));
        const statusPie = [
          { name: "Has data", value: s.has_data || 0, color: STATUS.good.color },
          { name: "Pending", value: s.pending || 0, color: STATUS.critical.color },
        ];

        return (
          <>
            {picker}

            <div className="mb-4 flex flex-wrap items-center gap-2">
              <Typography className="text-sm font-semibold text-blue-gray-800">
                {listLabel}
                <span className="ml-2 text-xs font-normal text-gray-600">
                  from {meta.master_source}
                  {meta.data_source ? ` · records from ${meta.data_source}` : ""}
                  {meta.rank_source ? ` · rank from ${meta.rank_source}` : ""}
                </span>
              </Typography>
            </div>
            {activeCount > 0 && (
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold text-blue-gray-600">Filters:</span>
                {chips}
                <Button size="sm" variant="text" color="blue-gray" className="py-1" onClick={clearFilters}>
                  Clear all
                </Button>
              </div>
            )}

            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <KpiCard label={activeCount ? `${listLabel} (filtered)` : `${listLabel} in master`} value={fmt(s.total)} sub={activeCount ? "matching the filters" : `every row of ${meta.master_source}`} />
              <KpiCard label="Has data" value={fmt(s.has_data)} status="good" sub={`${fmtPct(s.coverage_pct)} · ${recLabel.toLowerCase()} > 0`} />
              <KpiCard label="Pending" value={fmt(s.pending)} status="critical" sub="no records yet" />
              <KpiCard label={`Total ${recLabel.toLowerCase()}`} value={fmt(s.total_records)} sub={meta.data_source || ""} accent={SERIES[3]} />
            </div>

            <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-5">
              {meta.has_rank ? (
                <>
                  <ChartCard
                    title="Count per rank"
                    subtitle={`How many ${listLabel.toLowerCase()} are in each rank (other filters applied). Click a row to list only that rank.`}
                    className="xl:col-span-3"
                  >
                    <div className="overflow-auto rounded-lg border border-blue-gray-100">
                      <table className="w-full border-collapse text-left text-sm">
                        <thead className="bg-blue-gray-50 text-xs font-bold uppercase tracking-wide text-blue-gray-600">
                          <tr>
                            <th className="px-3 py-2">Rank</th>
                            <th className="px-3 py-2 text-right">{listLabel}</th>
                            <th className="px-3 py-2 text-right">Has data</th>
                            <th className="px-3 py-2 text-right">Pending</th>
                            <th className="px-3 py-2 text-right">Coverage</th>
                            <th className="px-3 py-2 text-right">{recLabel}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {byRank.length === 0 && (
                            <tr>
                              <td colSpan={6} className="px-3 py-4 text-center text-gray-500">No rows for these filters.</td>
                            </tr>
                          )}
                          {byRank.map((b) => {
                            const value = b.rank === null ? "none" : String(b.rank);
                            const active = get("rank") === value;
                            return (
                              <tr
                                key={b.label}
                                onClick={() => update({ rank: active ? "" : value })}
                                className={`cursor-pointer border-t border-blue-gray-50 ${active ? "bg-blue-50" : "hover:bg-blue-gray-50/60"}`}
                                title={active ? "Show all ranks" : `List only ${b.label}`}
                              >
                                <td className="whitespace-nowrap px-3 py-2 font-semibold">
                                  <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full align-middle" style={{ background: rankColor(b.label) }} />
                                  <span className="text-blue-700 underline decoration-blue-300 underline-offset-2">{b.label}</span>
                                </td>
                                <td className="px-3 py-2 text-right tabular-nums font-semibold">{fmt(b.total)}</td>
                                <td className="px-3 py-2 text-right tabular-nums">
                                  <button type="button" className="text-blue-700 hover:underline" onClick={(e) => { e.stopPropagation(); update({ rank: value, status: "has_data" }); }}>
                                    {fmt(b.has_data)}
                                  </button>
                                </td>
                                <td className="px-3 py-2 text-right tabular-nums">
                                  <button type="button" className="text-blue-700 hover:underline" onClick={(e) => { e.stopPropagation(); update({ rank: value, status: "pending" }); }}>
                                    {fmt(b.pending)}
                                  </button>
                                </td>
                                <td className="px-3 py-2 text-right tabular-nums">{fmtPct(b.coverage_pct)}</td>
                                <td className="px-3 py-2 text-right tabular-nums">{fmt(b.records)}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                        {byRank.length > 1 && (
                          <tfoot className="bg-blue-gray-50 font-semibold">
                            <tr>
                              <td className="px-3 py-2">Total</td>
                              {["total", "has_data", "pending"].map((k) => (
                                <td key={k} className="px-3 py-2 text-right tabular-nums">{fmt(byRank.reduce((a, b) => a + (b[k] || 0), 0))}</td>
                              ))}
                              <td className="px-3 py-2 text-right tabular-nums">
                                {fmtPct((byRank.reduce((a, b) => a + b.has_data, 0) * 100) / Math.max(byRank.reduce((a, b) => a + b.total, 0), 1))}
                              </td>
                              <td className="px-3 py-2 text-right tabular-nums">{fmt(byRank.reduce((a, b) => a + Number(b.records || 0), 0))}</td>
                            </tr>
                          </tfoot>
                        )}
                      </table>
                    </div>
                  </ChartCard>
                  <ChartCard title="Has data vs pending, per rank" className="xl:col-span-2">
                    <SimpleBar
                      data={rankChart}
                      bars={[
                        { key: "Has data", color: STATUS.good.color },
                        { key: "Pending", color: STATUS.critical.color },
                      ]}
                      stacked
                      height={Math.max(240, rankChart.length * 34 + 60)}
                      horizontal
                      yWidth={80}
                    />
                  </ChartCard>
                </>
              ) : (
                <ChartCard title="Has data vs pending" subtitle="For the current filters" className="xl:col-span-2">
                  <SimplePie data={statusPie} stack />
                </ChartCard>
              )}
            </div>

            <ChartCard
              title={`${listLabel} - full list`}
              subtitle={`Type in the boxes under each heading to filter; click a heading to sort. "${recLabel}" = ${
                meta.data_source && !meta.data_source.includes(".business_count")
                  ? "rows in the data with this exact name (case and spaces ignored)"
                  : "the value stored in the table"
              }.`}
            >
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <span className="text-xs text-gray-600">
                  {s.total ? `${fmt(from)}-${fmt(to)} of ${fmt(s.total)}` : "0 rows"}
                </span>
                {rows.loading && <Spinner className="h-4 w-4 text-blue-500" />}
                <div className="ml-auto flex flex-wrap items-center gap-2">
                  <label className="flex items-center gap-1 text-xs text-gray-700">
                    Rows per page
                    <select value={pageSize} onChange={(e) => update({ page_size: e.target.value })} className="rounded border border-gray-300 px-1.5 py-1 text-xs">
                      {PAGE_SIZES.map((n) => (
                        <option key={n} value={n}>{n}</option>
                      ))}
                    </select>
                  </label>
                  <Button size="sm" variant="text" color="blue-gray" className="flex items-center gap-1.5" onClick={downloadAll} disabled={downloading || !s.total}>
                    {downloading ? <Spinner className="h-4 w-4" /> : <ArrowDownTrayIcon className="h-4 w-4" />}
                    CSV ({fmt(Math.min(s.total || 0, 100000))} rows)
                  </Button>
                </div>
              </div>
              {downloadError && <Typography className="mb-2 text-xs text-red-700">{downloadError}</Typography>}
              {rows.error && <Typography className="mb-2 text-xs text-red-700">{rows.error}</Typography>}

              <div className={`overflow-auto rounded-lg border border-blue-gray-100 transition-opacity ${rows.loading ? "opacity-60" : ""}`} style={{ maxHeight: 640 }}>
                <table className="w-full border-collapse text-left">
                  <thead className="sticky top-0 z-10 bg-blue-gray-50">
                    <tr>
                      {columns.map((c) => (
                        <th
                          key={c.key}
                          onClick={c.sortable === false ? undefined : () => toggleSort(c.key)}
                          className={`whitespace-nowrap border-b border-blue-gray-100 px-3 py-2.5 text-xs font-bold uppercase tracking-wide text-blue-gray-600 ${
                            c.sortable === false ? "" : "cursor-pointer select-none"
                          } ${c.align === "right" ? "text-right" : ""}`}
                        >
                          <span className="inline-flex items-center gap-1">
                            {c.label}
                            {sort === c.key && (dir === "asc" ? <ChevronUpIcon className="h-3 w-3" /> : <ChevronDownIcon className="h-3 w-3" />)}
                          </span>
                        </th>
                      ))}
                    </tr>
                    <tr className="bg-white">
                      {columns.map((c) => (
                        <th key={c.key} className="border-b border-blue-gray-100 px-2 py-1.5">
                          {c.filter || null}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {pageRows.length === 0 && !rows.loading && (
                      <tr>
                        <td colSpan={columns.length} className="px-3 py-6 text-center text-sm text-gray-500">No rows match these filters.</td>
                      </tr>
                    )}
                    {pageRows.map((r, i) => (
                      <tr key={`${r.id ?? ""}-${i}`} className="border-b border-blue-gray-50 hover:bg-blue-gray-50/50">
                        {columns.map((c) => (
                          <td key={c.key} className={`px-3 py-2 align-top text-sm text-blue-gray-800 ${c.align === "right" ? "whitespace-nowrap text-right tabular-nums" : ""}`}>
                            {c.render(r, i)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="mt-3 flex flex-wrap items-center justify-end gap-2">
                <Button size="sm" variant="outlined" color="blue-gray" className="flex items-center gap-1 px-3 py-1.5" disabled={page <= 1} onClick={() => update({ page: page - 1 }, true)}>
                  <ChevronLeftIcon className="h-4 w-4" /> Prev
                </Button>
                <span className="text-xs text-gray-700">
                  Page{" "}
                  <input
                    key={page}
                    defaultValue={page}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        const n = Math.min(Math.max(Number(e.currentTarget.value) || 1, 1), totalPages);
                        update({ page: n }, true);
                      }
                    }}
                    aria-label="Page number"
                    className="w-14 rounded border border-gray-300 px-1.5 py-0.5 text-center text-xs"
                  />{" "}
                  of {fmt(totalPages)}
                </span>
                <Button size="sm" variant="outlined" color="blue-gray" className="flex items-center gap-1 px-3 py-1.5" disabled={page >= totalPages} onClick={() => update({ page: page + 1 }, true)}>
                  Next <ChevronRightIcon className="h-4 w-4" />
                </Button>
              </div>
            </ChartCard>
          </>
        );
      }}
    </ReportLayout>
  );
}

export default DetailReport;
