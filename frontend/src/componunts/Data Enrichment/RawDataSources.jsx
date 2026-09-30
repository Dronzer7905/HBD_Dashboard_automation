import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Button, Typography } from "@material-tailwind/react";
import {
  useReport, ReportLayout, KpiCard, ChartCard, DataTable, SimpleBar, SimplePie, StatusBadge, FillBar,
  SERIES, STATUS, OTHER_GRAY, fmt, reportPath,
} from "../HBD Reports/common/reportKit";

const STATUS_KIND = { Complete: "good", Partial: "warning", "In progress": "warning", Empty: "critical", "Not started": "critical", "Not in database": "critical" };

/** The Data Enrichment team's "Data enrichment tables" sheet, checked live against the database. */
export function RawDataSources() {
  const [exact, setExact] = useState(false);
  const report = useReport("/data-enrichment/raw-sources", { exact });
  const toggle = (
    <Button size="sm" variant={exact ? "filled" : "outlined"} color="blue-gray" onClick={() => setExact((e) => !e)} title="Exact COUNT(*) on every table - slower on big tables">
      {exact ? "Exact counts: ON" : "Exact counts: OFF"}
    </Button>
  );

  return (
    <ReportLayout
      title="Data Enrichment - Raw Data Sources"
      subtitle="Every table in the team's Data Enrichment sheet (group, subgroup, detail, count, done by, remarks) next to what is really in the database right now: live rows, how full the columns are, coordinates, and whether the count matches the sheet."
      report={report}
      actions={toggle}
    >
      {(data) => {
        const rows = data.sources || [];
        const t = data.totals || {};
        const inDb = rows.filter((r) => r.in_db);
        const statusPie = (data.status_summary || []).map((s) => ({
          ...s,
          color: s.name === "Not in database" ? "#898781" : STATUS[STATUS_KIND[s.name]]?.color || OTHER_GRAY,
        }));
        const sizeChart = [...inDb]
          .filter((r) => r.rows)
          .sort((a, b) => b.rows - a.rows)
          .slice(0, 15)
          .map((r) => ({ name: r.table, "Live rows": r.rows, "Sheet count": r.sheet_count || 0 }));
        const people = (data.people || []).map((p) => ({ name: p.name, "In database": p.in_db, "Not in database": p.tables - p.in_db }));

        const columns = [
          { key: "group", label: "Group" },
          { key: "subgroup", label: "Subgroup" },
          {
            key: "table",
            label: "Table name",
            render: (r) => (
              <span className="font-mono text-xs font-semibold">
                {r.table}
                {r.db_table && r.db_table !== r.table && <span className="block font-normal text-gray-500">in {r.db_table}</span>}
              </span>
            ),
          },
          { key: "detail", label: "Detail", render: (r) => <span className="block min-w-[260px] max-w-sm whitespace-normal text-xs">{r.detail || "—"}</span> },
          { key: "sheet_count", label: "No. of data (sheet)", align: "right", render: (r) => (r.sheet_count === null ? "—" : fmt(r.sheet_count)) },
          {
            key: "rows",
            label: "Live rows",
            align: "right",
            render: (r) => (r.in_db ? `${r.count_type === "estimate" ? "~" : ""}${fmt(r.rows)}` : <span className="text-red-700">not in DB</span>),
          },
          {
            key: "diff",
            label: "Live − sheet",
            align: "right",
            render: (r) =>
              r.diff === undefined || r.diff === null ? "—" : (
                <span style={{ color: r.matches_sheet ? STATUS.good.text : STATUS.critical.text }}>
                  {r.matches_sheet ? "✓ " : ""}
                  {r.diff > 0 ? "+" : ""}
                  {fmt(r.diff)}
                </span>
              ),
          },
          { key: "fill_pct", label: "Columns filled", render: (r) => (r.fill_pct === null ? "—" : <FillBar value={r.fill_pct} color={STATUS[STATUS_KIND[r.auto_status]]?.color || SERIES[0]} />) },
          {
            key: "geo",
            label: "Lat / Long",
            filterValue: (r) => (!r.in_db ? "" : r.geo_columns.length ? "Yes" : "No"),
            csv: (r) => r.geo_columns.join(" "),
            render: (r) => (!r.in_db ? "—" : r.geo_columns.length ? <span title={r.geo_columns.join(", ")}>Yes</span> : "No"),
          },
          {
            key: "status",
            label: "Status",
            render: (r) =>
              STATUS_KIND[r.status] ? <StatusBadge status={STATUS_KIND[r.status]} label={r.status} /> : <span className="text-xs">{r.status}</span>,
          },
          {
            key: "done_by",
            label: "Done by",
            filterValue: (r) => r.team_done_by || r.done_by,
            csv: (r) => r.team_done_by || r.done_by,
            render: (r) => r.team_done_by || r.done_by || <span className="text-gray-400">—</span>,
          },
          {
            key: "remarks",
            label: "Remarks",
            filterValue: (r) => r.team_remarks || r.sheet_remarks,
            csv: (r) => r.team_remarks || r.sheet_remarks,
            render: (r) => <span className="block min-w-[240px] max-w-sm whitespace-normal text-xs">{r.team_remarks || r.sheet_remarks || "—"}</span>,
          },
          {
            key: "notes",
            label: "Checks",
            filterValue: (r) => (r.notes.length ? r.notes.join("; ") : "OK"),
            csv: (r) => r.notes.join("; "),
            render: (r) =>
              r.notes.length ? (
                <ul className="min-w-[200px] max-w-xs list-disc space-y-0.5 whitespace-normal pl-4 text-xs text-amber-900">
                  {r.notes.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              ) : (
                <span className="text-xs text-gray-500">OK</span>
              ),
          },
          { key: "columns_count", label: "Columns", align: "right", hidden: true },
          { key: "db_table", label: "Table in database", hidden: true },
        ];

        return (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
              <KpiCard label="Tables in the sheet" value={fmt(t.in_sheet)} sub={t.not_in_sheet ? `+${t.not_in_sheet} raw table(s) in DB not in the sheet` : "raw + product groups"} />
              <KpiCard label="Found in database" value={`${fmt(t.in_db)}`} status={t.missing ? "warning" : "good"} sub={`${fmt(t.missing)} not in the database`} />
              <KpiCard label="Live records" value={fmt(t.rows)} sub={`sheet says ${fmt(t.sheet_rows)}`} accent={SERIES[2]} />
              <KpiCard label="With Lat / Long" value={fmt(t.with_geo)} sub="tables that can go on a map" accent={SERIES[3]} />
              <KpiCard label="Count differs from sheet" value={fmt(t.differs)} status={t.differs ? "critical" : "good"} sub="live rows ≠ sheet number" />
            </div>

            <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
              <ChartCard title="Status" subtitle={`Complete = columns ≥ ${data.complete_fill_pct}% filled (first ${fmt(data.sample_rows)} rows)`}>
                <SimplePie data={statusPie} stack valueFormatter={(v) => `${v} table${v === 1 ? "" : "s"}`} />
              </ChartCard>
              <ChartCard title="Largest tables - live vs sheet" subtitle="Top 15 by live rows" className="xl:col-span-2">
                <SimpleBar
                  data={sizeChart}
                  bars={[
                    { key: "Live rows", color: SERIES[0] },
                    { key: "Sheet count", color: SERIES[1] },
                  ]}
                  horizontal
                  height={Math.max(260, sizeChart.length * 34)}
                  yWidth={190}
                />
              </ChartCard>
            </div>

            <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
              <ChartCard title="Tables by person" subtitle="Done by, from the sheet (or the team's Edit)" className="xl:col-span-2">
                <SimpleBar
                  data={people}
                  bars={[
                    { key: "In database", color: SERIES[2] },
                    { key: "Not in database", color: STATUS.critical.color },
                  ]}
                  stacked
                  height={Math.max(220, people.length * 36)}
                  horizontal
                  yWidth={90}
                />
              </ChartCard>
              <ChartCard title="Groups in the sheet">
                <ul className="space-y-2">
                  {(data.groups || []).map((g) => (
                    <li key={g.group} className="flex items-baseline justify-between gap-2 border-b border-blue-gray-50 pb-1.5 text-sm">
                      <span className="font-semibold capitalize text-blue-gray-900">{g.group}</span>
                      <span className="text-right text-xs text-gray-700">
                        {g.tables ? `${g.in_db}/${g.tables} tables in DB · ${fmt(g.rows)} rows` : g.note}
                      </span>
                    </li>
                  ))}
                </ul>
                <Typography className="mt-3 text-xs text-gray-600">Reading from: {data.database}</Typography>
              </ChartCard>
            </div>

            <ChartCard
              title="All sources"
              subtitle="Filter any column. To set a table's status, done by or remarks, use Edit on the Database Tables page - it shows here too."
              right={
                <Link to={reportPath("/db-tables")} className="whitespace-nowrap text-xs font-semibold text-blue-700 hover:underline">
                  Database Tables →
                </Link>
              }
            >
              <DataTable columns={columns} rows={rows} filename="data_enrichment_raw_sources" searchable maxHeight={760} />
              <Typography className="mt-2 text-xs text-gray-600">
                ~ = approximate count from database statistics (turn on Exact counts for precise numbers).
              </Typography>
            </ChartCard>
          </>
        );
      }}
    </ReportLayout>
  );
}

export default RawDataSources;
