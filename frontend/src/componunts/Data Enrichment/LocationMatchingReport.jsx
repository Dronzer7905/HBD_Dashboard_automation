import React from "react";
import { Link } from "react-router-dom";
import { Typography } from "@material-tailwind/react";
import { CheckCircleIcon, ExclamationTriangleIcon, XCircleIcon } from "@heroicons/react/24/solid";
import {
  useReport, ReportLayout, KpiCard, ChartCard, DataTable, SimpleBar, SimplePie, StatusBadge, foldForPie,
  SERIES, STATUS, fmt, fmtPct, reportPath,
} from "../HBD Reports/common/reportKit";

/** "From the report" vs "Live now" table - the report number is never shown as if it were live. */
function CompareTable({ rows, filename }) {
  return (
    <DataTable
      columns={[
        { key: "label", label: "Metric", render: (r) => <span className="font-semibold">{r.label}</span> },
        { key: "doc", label: "From the report", align: "right", render: (r) => (r.doc === null || r.doc === undefined ? "—" : r.pct ? fmtPct(r.doc) : fmt(r.doc)) },
        { key: "live", label: "Live now", align: "right", render: (r) => (r.live === null || r.live === undefined ? <span className="text-gray-500">not in DB</span> : r.pct ? fmtPct(r.live) : fmt(r.live)) },
        {
          key: "change",
          label: "Change",
          align: "right",
          filter: false,
          csv: (r) => (r.live === null || r.live === undefined || r.doc === null || r.doc === undefined ? "" : r.live - r.doc),
          render: (r) => {
            if (r.live === null || r.live === undefined || r.doc === null || r.doc === undefined) return "—";
            const d = Math.round((r.live - r.doc) * 100) / 100;
            return <span className="tabular-nums text-blue-gray-700">{d > 0 ? "+" : ""}{r.pct ? `${d.toFixed(1)} pts` : fmt(d)}</span>;
          },
        },
        { key: "note", label: "Note", render: (r) => <span className="block max-w-xs whitespace-normal text-xs text-gray-700">{r.note || ""}</span> },
      ]}
      rows={rows}
      filename={filename}
      filters={false}
      maxHeight={420}
    />
  );
}

function NotLoaded({ table }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
      <ExclamationTriangleIcon className="mt-0.5 h-4 w-4 flex-none text-amber-700" />
      <Typography className="text-xs text-amber-900">
        <span className="font-mono">{table}</span> is not in the database yet - the report's numbers are shown; live numbers appear once it is loaded.
      </Typography>
    </div>
  );
}

/** 03 State match / Missing regions / Missing area / Location matching + 04 Location Master Data Report - re-checked live. */
export function LocationMatchingReport() {
  const report = useReport("/data-enrichment/location-matching");
  return (
    <ReportLayout
      title="Data Enrichment - Location Matching"
      subtitle="The team's location reports (State match, Missing Regions, Missing Area, Location Master Data Matching and the Location Master Data Report), each number checked again against the live database - so you can see what is done and what is still open."
      report={report}
    >
      {(data) => {
        const docs = data.docs || {};
        const live = data.live || {};
        const mp = data.priority || {};
        const m = docs.matching || {};
        const rg = docs.regions || {};
        const ar = docs.areas || {};
        const ss = docs.state_sync || {};
        const typeCount = (t) => (live.by_type || []).find((x) => String(x.name).toLowerCase() === t)?.value;
        const cities = live.new_cities || [];
        const validCities = cities.filter((c) => c.valid).length;
        const bad = live.bad_areas || {};
        const rc = data.rank_compare || {};
        const docMatched = m.priority_total - m.unmatched;

        const statusPie = foldForPie(mp.by_location_match_status || [], 6);
        const regionBar = (mp.by_region || []).map((r) => ({ name: r.name, Rows: r.value }));

        return (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
              <KpiCard label="Location master rows" value={fmt(live.total)} sub={`report: ${fmt(m.location_master_total)} → ${fmt(m.updated_location_master)}`} />
              <KpiCard label="States" value={fmt(live.states?.count)} sub={`report after sync: ${ss.total_after_sync}`} accent={SERIES[3]} />
              <KpiCard label="14 new city records" value={`${validCities} / ${cities.length || 14}`} status={validCities === (cities.length || 14) ? "good" : "warning"} sub="valid now (id, name, City, level 3, right state)" />
              <KpiCard label="Incorrect Area names" value={fmt(bad.incorrect_total)} status={bad.incorrect_total ? "critical" : "good"} sub={`report found ${fmt(ar.incorrect_total)}, fixed ${ar.corrected}`} />
              <KpiCard
                label="Priority rows mapped"
                value={mp.found ? fmtPct(mp.location_id_pct) : "—"}
                sub={mp.found ? `${fmt(mp.location_id_filled)} of ${fmt(mp.total)} have a location_id` : `report: ${fmt(docMatched)} of ${fmt(m.priority_total)}`}
                accent={SERIES[2]}
              />
            </div>

            {/* ── Location Master Data Matching ── */}
            <ChartCard title="Location Master Data Matching" subtitle={m.title} className="mb-6">
              {!mp.found && <div className="mb-3"><NotLoaded table="master_priority" /></div>}
              <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                <CompareTable
                  filename="location_matching_compare"
                  rows={[
                    { label: "Location master - total rows", doc: m.updated_location_master, live: live.total, note: `before matching: ${fmt(m.location_master_total)}` },
                    { label: "Location master - countries", doc: m.countries, live: typeCount("country") },
                    { label: "Location master - states", doc: ss.total_after_sync, live: live.states?.count, note: `35 before the state sync, 5 added` },
                    { label: "Location master - cities", doc: m.cities, live: typeCount("city"), note: "report number is before the 14 new cities" },
                    { label: "Master priority - rows", doc: m.priority_total, live: mp.found ? mp.total : null },
                    { label: "Rows with a location_id", doc: docMatched, live: mp.found ? mp.location_id_filled : null, note: `exact City+State ${fmt(m.exact_city_state)} + exact City ${fmt(m.exact_city)}` },
                    { label: "Rows still unmatched", doc: m.unmatched, live: mp.found ? mp.unmatched : null },
                    { label: "Unmatched with no City and no State", doc: m.unmatched_no_city_state, live: mp.found ? mp.no_city_state : null, note: "cannot be matched automatically" },
                  ]}
                />
                <div>
                  <Typography className="mb-2 text-sm font-semibold text-blue-gray-800">How a city is matched (in this order)</Typography>
                  <ol className="list-decimal space-y-1 pl-5 text-sm text-blue-gray-800">
                    {(data.city_match_order || []).map(([name, text]) => (
                      <li key={name}>
                        <span className="font-semibold">{name}</span> - <span className="text-gray-700">{text}</span>
                      </li>
                    ))}
                  </ol>
                  <Typography className="mt-3 text-xs text-gray-600">
                    Aliases: {(data.aliases || []).map(([a, b]) => `${a} → ${b}`).join(" · ")}. Area-level records are never reused as cities (their parents can point to unrelated cities).
                  </Typography>
                  {mp.found && statusPie.length > 0 && (
                    <div className="mt-4">
                      <Typography className="mb-1 text-sm font-semibold text-blue-gray-800">Match status (live, {mp.table})</Typography>
                      <SimplePie data={statusPie} stack height={200} />
                    </div>
                  )}
                </div>
              </div>
            </ChartCard>

            {/* ── 14 new cities ── */}
            <ChartCard
              title="The 14 new city records"
              subtitle="Created by the matching work. Checked live: the id exists, the name is right, type = City, level = 3, and the parent is the right state (the report's Step 4)."
              className="mb-6"
            >
              <DataTable
                columns={[
                  { key: "city", label: "City", render: (r) => <span className="font-semibold">{r.city}</span> },
                  { key: "state", label: "State (report)" },
                  { key: "id", label: "New ID", align: "right" },
                  {
                    key: "valid",
                    label: "Result",
                    filterValue: (r) => (r.valid ? "Valid" : r.found ? "Has issues" : "Not found"),
                    csv: (r) => (r.valid ? "Valid" : r.found ? "Has issues" : "Not found"),
                    render: (r) => <StatusBadge status={r.valid ? "good" : r.found ? "warning" : "critical"} label={r.valid ? "Valid" : r.found ? "Has issues" : "Not found"} />,
                  },
                  { key: "issues", label: "Issues", filterValue: (r) => r.issues.join("; "), csv: (r) => r.issues.join("; "), render: (r) => <span className="block max-w-xs whitespace-normal text-xs">{r.issues.join("; ") || "—"}</span> },
                  { key: "live_type", label: "Type (live)", render: (r) => r.live_type ?? "—" },
                  { key: "live_level", label: "Level (live)", align: "right", render: (r) => r.live_level ?? "—" },
                  { key: "live_parent", label: "Parent (live)", render: (r) => r.live_parent ?? "—" },
                  {
                    key: "other",
                    label: "Other City records with this name",
                    filterValue: (r) => r.other_city_records.join(", "),
                    csv: (r) => r.other_city_records.join(", "),
                    render: (r) => <span className="text-xs">{r.other_city_records.join(", ") || "—"}</span>,
                  },
                ]}
                rows={cities}
                filename="new_city_records_check"
                maxHeight={560}
              />
            </ChartCard>

            {/* ── State sync ── */}
            <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
              <ChartCard title="State match - states added" subtitle={`${ss.title}: ${ss.original_states} states + ${ss.added_states} added = ${ss.total_after_sync}`}>
                <ul className="space-y-2">
                  {(live.states_added || []).map((s) => (
                    <li key={s.state} className="flex items-center gap-2 text-sm">
                      {s.found ? <CheckCircleIcon className="h-5 w-5" style={{ color: STATUS.good.color }} /> : <XCircleIcon className="h-5 w-5" style={{ color: STATUS.critical.color }} />}
                      <span className="text-blue-gray-900">{s.state}</span>
                      <span className="ml-auto text-xs text-gray-600">{s.found ? "in location_master" : "not in location_master yet"}</span>
                    </li>
                  ))}
                </ul>
                <Typography className="mt-3 text-xs text-gray-600">Live: {fmt(live.states?.count)} State rows in location_master. Names are compared ignoring case and "&" vs "and".</Typography>
              </ChartCard>

              {/* ── Regions ── */}
              <ChartCard title="Missing regions" subtitle={rg.title}>
                {!mp.found && <div className="mb-3"><NotLoaded table="master_priority" /></div>}
                <CompareTable
                  filename="missing_regions_compare"
                  rows={[
                    { label: "Rows with a region", doc: rg.filled, live: mp.found ? mp.region_filled ?? null : null },
                    { label: "Region filled %", doc: rg.total ? Math.round((rg.filled * 10000) / rg.total) / 100 : null, live: mp.found ? mp.region_pct ?? null : null, pct: true },
                    { label: "Total rows", doc: rg.total, live: mp.found ? mp.total : null },
                  ]}
                />
                {regionBar.length > 0 && (
                  <div className="mt-3">
                    <SimpleBar data={regionBar} bars={[{ key: "Rows", color: SERIES[0] }]} height={200} showValues />
                  </div>
                )}
                <Typography className="mt-2 text-xs text-gray-700">
                  Fixed in the report: {rg.location_master_rows_fixed} location_master rows, {rg.brand_rows_fixed} brand-tagging rows; {rg.nraipur_rows_reverted} Raipur rows reverted after the "Nraipur" catch. {rg.recommendation}
                </Typography>
              </ChartCard>
            </div>

            {/* ── Missing area ── */}
            <ChartCard title="Missing / incorrect Area names" subtitle={`${ar.title}. Live check: Area names with no letters, or the same as their own City, State or Country.`} className="mb-6">
              <div className="mb-4 grid grid-cols-1 gap-6 xl:grid-cols-2">
                <CompareTable
                  filename="area_names_compare"
                  rows={[
                    { label: "Area rows", doc: ar.area_rows, live: bad.area_rows },
                    { label: "Name looks like a code / number", doc: ar.digit_names, live: bad.no_letters, note: "report: 'mostly digits'; live: no letters at all" },
                    { label: "Same name as its City / State / Country", doc: ar.duplicate_parent_names, live: bad.same_as_parent },
                    { label: "Incorrect Area rows", doc: ar.incorrect_total, live: bad.incorrect_total, note: `report corrected ${ar.corrected}, left ${fmt(ar.unresolved)}` },
                    { label: "Cities affected", doc: ar.cities_affected, live: bad.cities_affected },
                  ]}
                />
                <SimpleBar
                  data={[
                    { name: "No letters", Report: ar.digit_names, Live: bad.no_letters },
                    { name: "Same as parent", Report: ar.duplicate_parent_names, Live: bad.same_as_parent },
                  ]}
                  bars={[
                    { key: "Report", color: SERIES[1] },
                    { key: "Live", color: SERIES[0] },
                  ]}
                  height={240}
                  showValues
                />
              </div>
              <Typography className="mb-2 text-sm font-semibold text-blue-gray-800">Incorrect Area rows now (up to 5,000)</Typography>
              <DataTable
                columns={[
                  { key: "id", label: "ID", align: "right" },
                  { key: "name", label: "Area name", render: (r) => <span className="font-semibold">{r.name}</span> },
                  { key: "city", label: "City" },
                  { key: "state", label: "State" },
                  { key: "reason", label: "Why it is flagged" },
                ]}
                rows={live.bad_area_rows || []}
                filename="incorrect_area_names"
                maxHeight={460}
                emptyText="No incorrect Area names found."
              />
            </ChartCard>

            {/* ── Cities to investigate ── */}
            <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
              <ChartCard title="Cities requiring further investigation" subtitle="Unmatched master priority records per city - report vs live">
                {!mp.found && <div className="mb-3"><NotLoaded table="master_priority" /></div>}
                <DataTable
                  columns={[
                    { key: "city", label: "City", render: (r) => <span className="font-semibold">{r.city}</span> },
                    { key: "doc", label: "Unmatched (report)", align: "right", render: (r) => fmt(r.doc) },
                    { key: "live", label: "Unmatched (live)", align: "right", render: (r) => (r.live === null ? "—" : fmt(r.live)) },
                  ]}
                  rows={mp.cities_to_investigate || (data.cities_to_investigate_doc || []).map(([city, doc]) => ({ city, doc, live: null }))}
                  filename="cities_to_investigate"
                  maxHeight={420}
                />
              </ChartCard>

              {/* ── 04 ranking ── */}
              <ChartCard
                title="Location Master Data Report - ranking"
                subtitle="Report numbers vs the live location_master ranking"
                right={
                  <Link to={reportPath("/ranking")} className="whitespace-nowrap text-xs font-semibold text-blue-700 hover:underline">
                    Ranking Report →
                  </Link>
                }
              >
                {rc.doc_note && (
                  <div className="mb-3 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
                    <ExclamationTriangleIcon className="mt-0.5 h-4 w-4 flex-none text-amber-700" />
                    <Typography className="text-xs text-amber-900">{rc.doc_note}</Typography>
                  </div>
                )}
                <CompareTable
                  filename="location_rank_compare"
                  rows={[
                    ...(rc.by_rank || []).map((r) => ({ label: r.name, doc: r.doc, live: r.live })),
                    { label: "Total", doc: rc.doc_total, live: rc.live_total },
                    ...(rc.by_type_rank1 || []).map((r) => ({ label: `${r.name} at Rank 1`, doc: r.doc, live: r.live })),
                  ]}
                />
              </ChartCard>
            </div>

            <ChartCard title="Known limits (Missing Regions report)">
              <ul className="list-disc space-y-1 pl-5 text-sm text-blue-gray-800">
                {(rg.limits || []).map((l) => (
                  <li key={l}>{l}</li>
                ))}
              </ul>
            </ChartCard>
          </>
        );
      }}
    </ReportLayout>
  );
}

export default LocationMatchingReport;
