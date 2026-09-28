import React from "react";
import { Typography } from "@material-tailwind/react";
import {
  useReport, ReportLayout, KpiCard, ChartCard, DataTable, StatusBadge, SimpleBar,
  SERIES, fmt,
} from "./common/reportKit";

function CheckCard({ check }) {
  if (!check.found || !check.levels) {
    return (
      <ChartCard title={check.label} subtitle={check.table || "not found"}>
        <Typography className="text-sm text-gray-600">{(check.issues || []).join(" ")}</Typography>
      </ChartCard>
    );
  }
  const columns = [
    { key: "level", label: "Level", render: (r) => `${r.level ?? "—"} · ${r.level_name}` },
    { key: "total", label: "Total", align: "right", render: (r) => fmt(r.total) },
    { key: "has_parent", label: "Has parent", align: "right", render: (r) => fmt(r.has_parent) },
    {
      key: "missing_parent",
      label: "Missing parent",
      align: "right",
      render: (r) => (
        <span className={r.missing_parent > 0 && r.level !== check.root_level ? "font-semibold text-red-700" : "text-gray-600"}>
          {fmt(r.missing_parent)}
          {r.level === check.root_level ? " (top level)" : ""}
        </span>
      ),
    },
  ];
  return (
    <ChartCard
      title={check.label}
      subtitle={`${check.table} · ${fmt(check.total)} rows · level column "${check.level_column}"`}
      right={<StatusBadge status={check.status} label={check.status === "good" ? "Healthy" : check.status === "warning" ? "1 issue" : `${check.issues.length} issues`} />}
    >
      {check.issues?.length > 0 ? (
        <ul className="mb-4 list-disc space-y-1 pl-5 text-sm text-blue-gray-800">
          {check.issues.map((i) => (
            <li key={i}>{i}</li>
          ))}
        </ul>
      ) : (
        <Typography className="mb-4 text-sm text-green-800">Every row below the top level has a valid parent. No broken links.</Typography>
      )}
      <SimpleBar
        data={check.levels.map((l) => ({ name: l.level_name, "Has parent": l.has_parent, "Missing parent": l.missing_parent }))}
        bars={[
          { key: "Has parent", color: SERIES[0] },
          { key: "Missing parent", color: SERIES[1] },
        ]}
        stacked
        height={240}
      />
      <div className="mt-4">
        <DataTable columns={columns} rows={check.levels} filename={`hierarchy_${check.table}`} maxHeight={300} />
      </div>
      {check.beyond_expected?.rows > 0 && (
        <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3">
          <Typography className="text-sm font-semibold text-amber-900">
            Rows deeper than level {check.beyond_expected.expected_max_level}: {fmt(check.beyond_expected.rows)}
          </Typography>
          <Typography className="mt-1 text-xs text-amber-900">
            {fmt(check.beyond_expected.numeric_only_names)} have names with no letters (phone / shop numbers). Examples:{" "}
            <span className="font-mono">{(check.beyond_expected.samples || []).join(" · ") || "—"}</span>
          </Typography>
        </div>
      )}
    </ChartCard>
  );
}

/** Parent-child hierarchy health (Coverage Report section 7). */
export function HierarchyReport() {
  const report = useReport("/hbd-reports/hierarchy");
  return (
    <ReportLayout
      title="Hierarchy Check"
      subtitle="Checks the parent-child tree of every master list: rows per level, rows with no parent, links to parents that don't exist, and (for locations) junk rows below the Area level."
      report={report}
    >
      {(data) => {
        const checks = data.checks || [];
        const found = checks.filter((c) => c.found && c.levels);
        return (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <KpiCard label="Lists checked" value={found.length} sub={`of ${checks.length} configured`} />
              <KpiCard label="Healthy" value={found.filter((c) => c.status === "good").length} status="good" />
              <KpiCard label="Rows missing a parent" value={fmt(found.reduce((s, c) => s + (c.non_root_missing_parent || 0), 0))} status="warning" sub="below the top level" />
              <KpiCard label="Broken parent links" value={fmt(found.reduce((s, c) => s + (c.orphans || 0), 0))} status="critical" sub="parent_id points to nothing" />
            </div>
            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
              {checks.map((c) => (
                <CheckCard key={c.key} check={c} />
              ))}
            </div>
          </>
        );
      }}
    </ReportLayout>
  );
}

export default HierarchyReport;
