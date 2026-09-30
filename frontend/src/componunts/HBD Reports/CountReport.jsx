import React from "react";
import { Typography } from "@material-tailwind/react";
import {
  useReport, ReportLayout, KpiCard, ChartCard, DataTable, StatusBadge, SimpleBar, SimplePie, DrillLink,
  STATUS, SERIES, fmt, fmtPct,
} from "./common/reportKit";

/**
 * Count Report - the "Dashboard_count" sheet, live.
 * Field | Total Master Count | Data Count (distinct) | Coverage % | Remarks
 * plus Matched / Pending (Coverage Report sections 4 and 10).
 */
export function CountReport() {
  const report = useReport("/hbd-reports/count-report");

  return (
    <ReportLayout
      title="Count Report - Master vs Data Coverage"
      subtitle="For every master list: how many entries the master has, how many distinct values really appear in the scraped data, and how many of those match the master. Same layout as the Dashboard_count sheet, calculated live."
      report={report}
    >
      {(data) => {
        const rows = data.rows || [];
        const withMaster = rows.filter((r) => r.master_count);
        const statusCount = ["good", "warning", "critical"].map((s) => ({
          name: STATUS[s].label,
          value: rows.filter((r) => r.status === s).length,
          color: STATUS[s].color,
        }));
        const totalMaster = withMaster.reduce((s, r) => s + (r.master_count || 0), 0);
        const totalMatched = withMaster.reduce((s, r) => s + (r.matched || 0), 0);

        const coverageChart = rows.map((r) => ({
          name: r.label,
          coverage: r.coverage_pct === null ? 0 : Math.min(Number(r.coverage_pct), 150),
          matched: r.match_pct === null ? 0 : Number(r.match_pct),
        }));
        const pendingChart = withMaster.map((r) => {
          const matchedPct = r.match_pct === null ? 0 : Math.min(Number(r.match_pct), 100);
          return { name: r.label, Matched: matchedPct, Pending: Math.max(0, 100 - matchedPct) };
        });

        const columns = [
          {
            key: "label",
            label: "Field",
            render: (r) => (
              <div className="min-w-[150px]">
                <div className="font-semibold">{r.label}</div>
                <div className="mt-0.5 text-[11px] leading-tight text-gray-600">master: {r.master_source || "none"}</div>
                <div className="text-[11px] leading-tight text-gray-600">data: {r.data_source || "—"}</div>
                {(r.other_masters || []).map((m) => (
                  <div key={m.source} className="text-[11px] leading-tight text-gray-500">also {m.source}: {fmt(m.count)}</div>
                ))}
              </div>
            ),
            csv: (r) => r.label,
          },
          {
            key: "master_count",
            label: "Total Master Count",
            align: "right",
            render: (r) => (r.master_count === null ? "Table missing" : <DrillLink to={{ list: r.field }}>{fmt(r.master_count)}</DrillLink>),
          },
          { key: "data_count", label: "Data Count (distinct)", align: "right", render: (r) => fmt(r.data_count) },
          { key: "coverage_pct", label: "Coverage %", align: "right", render: (r) => fmtPct(r.coverage_pct) },
          {
            key: "matched",
            label: "Matched",
            align: "right",
            render: (r) => (r.master_count ? <DrillLink to={{ list: r.field, status: "has_data" }}>{fmt(r.matched)}</DrillLink> : fmt(r.matched)),
          },
          {
            key: "pending",
            label: "Pending",
            align: "right",
            render: (r) => (r.master_count ? <DrillLink to={{ list: r.field, status: "pending" }}>{fmt(r.pending)}</DrillLink> : fmt(r.pending)),
          },
          {
            key: "remarks",
            label: "Remarks",
            render: (r) => (
              <div className="min-w-[220px] max-w-sm">
                <StatusBadge status={r.status} />
                <div className="mt-1 text-xs text-blue-gray-800">{r.remarks}</div>
              </div>
            ),
            csv: (r) => `${STATUS[r.status]?.label}: ${r.remarks}`,
          },
          { key: "master_source", label: "Master source", csv: (r) => r.master_source, hidden: true },
          { key: "data_source", label: "Data source", csv: (r) => r.data_source, hidden: true },
        ];

        return (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <KpiCard label="Fields tracked" value={rows.length} sub="country, state, city, area, categories, pincode" />
              <KpiCard label="Master entries" value={fmt(totalMaster)} sub="sum across master lists that exist" />
              <KpiCard label="Matched to master" value={fmt(totalMatched)} sub={`${fmtPct(totalMaster ? (totalMatched * 100) / totalMaster : null)} of master entries`} accent={SERIES[2]} />
              <KpiCard label="Fields needing work" value={rows.filter((r) => r.status !== "good").length} status="critical" sub="partial / very low coverage or missing master" />
            </div>

            <ChartCard title="Count report" subtitle="Coverage % = Data Count ÷ Total Master Count. Pending = master entries with no matching data yet. Click Master Count, Matched or Pending to see the full list of names." className="mb-6">
              <DataTable columns={columns} rows={rows} filename="count_report" maxHeight={640} />
            </ChartCard>

            <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
              <ChartCard title="Coverage by field" subtitle="Coverage % vs share of master actually matched (capped at 150%)" className="xl:col-span-2">
                <SimpleBar
                  data={coverageChart}
                  bars={[
                    { key: "coverage", label: "Coverage %", color: SERIES[0] },
                    { key: "matched", label: "Matched %", color: SERIES[2] },
                  ]}
                  valueFormatter={(v) => fmtPct(v)}
                  height={320}
                />
              </ChartCard>
              <ChartCard title="Field status" subtitle="How many fields are in each state">
                <SimplePie data={statusCount} stack valueFormatter={(v) => `${v} field${v === 1 ? "" : "s"}`} />
              </ChartCard>
            </div>

            <ChartCard title="Pending vs completed" subtitle="Share of each master list that is matched (done) vs still pending - Coverage Report section 10">
              <SimpleBar
                data={pendingChart}
                bars={[
                  { key: "Matched", label: "Matched %", color: SERIES[0] },
                  { key: "Pending", label: "Pending %", color: SERIES[1] },
                ]}
                stacked
                horizontal
                valueFormatter={(v) => fmtPct(v)}
                height={Math.max(220, pendingChart.length * 44)}
              />
              <Typography className="mt-3 text-xs text-gray-600">
                Matching ignores upper/lower case and extra spaces. A field shows "Table missing" when none of its master tables exist in this database.
              </Typography>
            </ChartCard>
          </>
        );
      }}
    </ReportLayout>
  );
}

export default CountReport;
