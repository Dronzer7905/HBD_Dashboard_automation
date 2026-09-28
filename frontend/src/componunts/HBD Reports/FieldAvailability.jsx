import React, { useState } from "react";
import { Typography } from "@material-tailwind/react";
import {
  useReport, ReportLayout, KpiCard, ChartCard, DataTable, StatusBadge, SimplePie, SimpleBar, FillBar,
  STATUS, SERIES, fmt, fmtPct,
} from "./common/reportKit";

const CLASS_STATUS = {
  Available: "good",
  "Partially Available": "warning",
  "Not Available": "critical",
};

/** Master Table - column-by-column data availability (Coverage Report section 9). Works for any table. */
export function FieldAvailability() {
  const [table, setTable] = useState("master_table");
  const [filter, setFilter] = useState("All");
  const report = useReport("/hbd-reports/field-availability", { table });

  const picker = report.data?.tables?.length ? (
    <select
      value={table}
      onChange={(e) => {
        setTable(e.target.value);
        setFilter("All");
      }}
      className="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm"
      aria-label="Table"
    >
      {report.data.tables.map((t) => (
        <option key={t} value={t}>
          {t}
        </option>
      ))}
    </select>
  ) : null;

  return (
    <ReportLayout
      title="Field Availability"
      subtitle="For every column of the selected table: how many records have a real value. Blank, NULL and placeholder values like 0 / 'null' count as missing (0 is kept as a real value for yes/no flag columns such as isBestSeller)."
      report={report}
      actions={picker}
    >
      {(data) => {
        if (!data.found) {
          return <Typography className="text-sm text-red-700">Table "{data.table}" was not found.</Typography>;
        }
        const cols = data.columns || [];
        const counts = ["Available", "Partially Available", "Not Available"].map((k) => ({
          name: k,
          value: cols.filter((c) => c.classification === k).length,
          color: STATUS[CLASS_STATUS[k]].color,
        }));
        const shown = filter === "All" ? cols : cols.filter((c) => c.classification === filter);
        const th = data.thresholds || {};

        const columns = [
          { key: "column", label: "Field", render: (r) => <span className="font-mono text-xs">{r.column}</span> },
          { key: "data_type", label: "Type", render: (r) => <span className="text-xs text-gray-600">{r.data_type}{r.is_flag ? " · flag" : ""}</span> },
          { key: "filled", label: "Filled", align: "right", render: (r) => fmt(r.filled) },
          { key: "total", label: "Total", align: "right", render: (r) => fmt(r.total) },
          { key: "pct", label: "%", render: (r) => <FillBar value={r.pct} color={STATUS[CLASS_STATUS[r.classification]]?.color || SERIES[0]} />, csv: (r) => r.pct },
          {
            key: "classification",
            label: "Classification",
            render: (r) => <StatusBadge status={CLASS_STATUS[r.classification] || "warning"} label={r.classification} />,
          },
        ];

        const byPct = [...cols].sort((a, b) => (b.pct ?? -1) - (a.pct ?? -1));

        return (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <KpiCard label="Records checked" value={fmt(data.total_rows)} sub={`table ${data.table}`} />
              <KpiCard label="Available fields" value={`${counts[0].value} / ${cols.length}`} status="good" sub={`filled in ≥ ${th.available_pct}% of records`} />
              <KpiCard label="Partially available" value={counts[1].value} status="warning" sub={`${th.partial_pct}-${th.available_pct}% filled`} />
              <KpiCard label="Not available" value={counts[2].value} status="critical" sub="needs scraping / enrichment" />
            </div>

            <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
              <ChartCard title="Fields by availability" subtitle={`${cols.length} columns in ${data.table}`}>
                <SimplePie data={counts} stack valueFormatter={(v) => `${v} fields`} />
              </ChartCard>
              <ChartCard title="Fill % by field" subtitle="Every column, highest first" className="xl:col-span-2">
                <div className="max-h-[420px] overflow-y-auto pr-2">
                  <SimpleBar
                    data={byPct.map((c) => ({ name: c.column, "Fill %": c.pct ?? 0 }))}
                    bars={[{ key: "Fill %", color: SERIES[0] }]}
                    horizontal
                    showValues
                    valueFormatter={(v) => fmtPct(v)}
                    height={Math.max(260, byPct.length * 22)}
                    yWidth={170}
                  />
                </div>
              </ChartCard>
            </div>

            <ChartCard title="Column-by-column results" subtitle="Click a column header to sort; use the filter to show one class">
              <DataTable
                columns={columns}
                rows={shown}
                searchable
                searchKeys={["column", "data_type", "classification"]}
                filename={`field_availability_${data.table}`}
                maxHeight={600}
                toolbar={
                  <select value={filter} onChange={(e) => setFilter(e.target.value)} className="rounded-md border border-gray-300 bg-white px-2 py-2 text-sm">
                    {["All", "Available", "Partially Available", "Not Available"].map((o) => (
                      <option key={o}>{o}</option>
                    ))}
                  </select>
                }
              />
            </ChartCard>
          </>
        );
      }}
    </ReportLayout>
  );
}

export default FieldAvailability;
