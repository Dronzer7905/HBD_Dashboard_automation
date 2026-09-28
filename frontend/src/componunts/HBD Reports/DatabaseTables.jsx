import React, { useState } from "react";
import { Button, Typography } from "@material-tailwind/react";
import {
  useReport, ReportLayout, KpiCard, ChartCard, DataTable, SimpleBar, SimplePie, foldForPie,
  SERIES, fmt,
} from "./common/reportKit";

/** Every table in the database - the "dashboard db new" sheet, live (Coverage Report section 11). */
export function DatabaseTables() {
  const [exact, setExact] = useState(false);
  const [group, setGroup] = useState("All");
  const report = useReport("/hbd-reports/db-tables", { exact });

  const exactToggle = (
    <Button
      size="sm"
      variant={exact ? "filled" : "outlined"}
      color="blue-gray"
      onClick={() => setExact((e) => !e)}
      title="Exact COUNT(*) on every table - slower on big tables"
    >
      {exact ? "Exact counts: ON" : "Exact counts: OFF"}
    </Button>
  );

  return (
    <ReportLayout
      title="Database Tables"
      subtitle="Every table in the database with its group, subgroup, columns and number of records - the 'dashboard db new' sheet, generated live. Groups come from the team's sheet; new tables are grouped automatically by name."
      report={report}
      actions={exactToggle}
    >
      {(data) => {
        const tables = data.tables || [];
        const groups = data.groups || [];
        const shown = group === "All" ? tables : tables.filter((t) => t.group === group);
        const t = data.totals || {};

        const columns = [
          { key: "group", label: "Group" },
          { key: "subgroup", label: "Subgroup", render: (r) => r.subgroup || "" },
          { key: "table", label: "Table name", render: (r) => <span className="font-mono text-xs font-semibold">{r.table}</span> },
          {
            key: "detail",
            label: "Detail",
            render: (r) => (
              <span className="block max-w-md whitespace-normal text-xs text-gray-700" title={(r.columns || []).join(", ")}>
                {r.detail}
              </span>
            ),
          },
          {
            key: "rows",
            label: "No. of data",
            align: "right",
            render: (r) => (
              <span>
                {r.count_type === "estimate" ? "~" : ""}
                {fmt(r.rows)}
              </span>
            ),
          },
          {
            key: "remarks",
            label: "Remarks",
            render: (r) => <span className={`text-xs ${r.rows === 0 ? "font-semibold text-amber-800" : "text-gray-600"}`}>{r.remarks}</span>,
          },
        ];

        return (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <KpiCard label="Tables" value={fmt(t.tables)} sub={`${groups.length} groups`} />
              <KpiCard label="Total records" value={fmt(t.rows)} sub={t.approximate_counts ? `${t.approximate_counts} big tables use fast estimates` : "all exact counts"} accent={SERIES[2]} />
              <KpiCard label="Empty tables" value={fmt(t.empty_tables)} status={t.empty_tables ? "warning" : "good"} sub="no rows yet" />
              <KpiCard label="Largest group" value={groups[0]?.group || "—"} sub={groups[0] ? `${fmt(groups[0].rows)} records` : ""} accent={SERIES[1]} />
            </div>

            <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
              <ChartCard title="Records by group" subtitle="Total rows in each group of tables">
                <SimpleBar
                  data={groups.map((g) => ({ name: g.group, Records: g.rows }))}
                  bars={[{ key: "Records", color: SERIES[0] }]}
                  horizontal
                  showValues
                  valueFormatter={fmt}
                  height={Math.max(260, groups.length * 34)}
                  yWidth={150}
                />
              </ChartCard>
              <ChartCard title="Tables per group" subtitle="How many tables each group has">
                <SimplePie data={foldForPie(groups, 6, "group", "tables")} valueFormatter={(v) => `${v} tables`} />
              </ChartCard>
            </div>

            <ChartCard title="All tables" subtitle="~ means an approximate count from database statistics (turn on Exact counts for precise numbers)">
              <DataTable
                columns={columns}
                rows={shown}
                searchable
                searchKeys={["group", "subgroup", "table", "detail", "remarks"]}
                filename="database_tables"
                maxHeight={680}
                toolbar={
                  <select value={group} onChange={(e) => setGroup(e.target.value)} className="rounded-md border border-gray-300 bg-white px-2 py-2 text-sm" aria-label="Group">
                    <option>All</option>
                    {groups.map((g) => (
                      <option key={g.group} value={g.group}>
                        {g.group} ({g.tables})
                      </option>
                    ))}
                  </select>
                }
              />
              <Typography className="mt-3 text-xs text-gray-600">
                Hover a Detail cell to see every column name. The CSV download includes the full row list with the filter applied.
              </Typography>
            </ChartCard>
          </>
        );
      }}
    </ReportLayout>
  );
}

export default DatabaseTables;
