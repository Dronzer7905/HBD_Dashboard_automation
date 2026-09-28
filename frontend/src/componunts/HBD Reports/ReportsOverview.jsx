import React from "react";
import { Link } from "react-router-dom";
import { Typography } from "@material-tailwind/react";
import { ArrowRightIcon } from "@heroicons/react/24/solid";
import {
  useReport, Section, KpiCard, ChartCard, SimpleBar, SimplePie, foldForPie, LiveStamp, RefreshButton,
  SERIES, RANK_RAMP, OTHER_GRAY, fmt, fmtPct, reportPath,
} from "./common/reportKit";

const STAGE_SHORT = { scrap: "1. Scrap", clean: "2. Clean", merge: "3. Merge", match: "4. Match", ready: "5. Ready" };

const REPORT_INDEX = [
  { path: "/hbd", title: "HBD Report", text: "5-stage data journey with live counts, cleaning tiers, targets vs progress." },
  { path: "/count", title: "Count Report", text: "Master vs data coverage per field (Dashboard_count sheet) + pending vs completed." },
  { path: "/ranking", title: "Ranking Report", text: "Location type × rank (Ranking_Count sheet), top cities and categories." },
  { path: "/field-availability", title: "Master Table Fields", text: "Which of the master table's columns actually have data." },
  { path: "/hierarchy", title: "Hierarchy Check", text: "Parent-child health of locations and category trees." },
  { path: "/db-tables", title: "Database Tables", text: "Every table with group, columns and record count (dashboard db new sheet)." },
  { path: "/data-enrichment/all-tables", title: "Data Enrichment", text: "All six product tables in one place, then categories, marketplaces and attributes." },
];

function OpenLink({ to, label = "Open report" }) {
  return (
    <Link to={reportPath(to)} className="inline-flex items-center gap-1 text-xs font-semibold text-blue-700 hover:underline">
      {label} <ArrowRightIcon className="h-3.5 w-3.5" />
    </Link>
  );
}

/** Everything on one page. Each block loads on its own, so one slow report never blocks the rest. */
export function ReportsOverview() {
  const counts = useReport("/hbd-reports/count-report");
  const tables = useReport("/hbd-reports/db-tables");
  const hbd = useReport("/hbd-reports/hbd");
  const ranking = useReport("/hbd-reports/ranking");
  const products = useReport("/data-enrichment/all-tables");
  const all = [counts, tables, hbd, ranking, products];
  const anyLoading = all.some((r) => r.loading);
  const latest = all.map((r) => r.generatedAt).filter(Boolean).sort().pop();

  return (
    <div className="mb-12 mt-6 px-1 md:px-4">
      <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <Typography variant="h4" color="blue-gray" className="font-bold">
            HBD Reports - Overview
          </Typography>
          <Typography variant="small" className="mt-1 max-w-3xl text-gray-600">
            Live summary of every report: database size, master coverage, ranking, the data pipeline and the product tables.
            Open any card for the full report.
          </Typography>
        </div>
        <div className="flex items-center gap-2">
          <LiveStamp report={{ generatedAt: latest }} />
          <RefreshButton loading={anyLoading} onClick={() => all.forEach((r) => r.reload())} />
        </div>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-6">
        <KpiCard label="Tables" value={tables.data ? fmt(tables.data.totals?.tables) : "…"} sub="in the database" />
        <KpiCard label="Total records" value={tables.data ? fmt(tables.data.totals?.rows) : "…"} sub="all tables" accent={SERIES[2]} />
        <KpiCard label="Listing master" value={hbd.data ? fmt(hbd.data.stages?.find((s) => s.key === "ready")?.metrics?.[0]?.value) : "…"} sub="master_table" accent={SERIES[1]} />
        <KpiCard label="Location master" value={ranking.data ? fmt(ranking.data.location_rank?.total_location_master) : "…"} sub="location_master" accent={RANK_RAMP[0]} />
        <KpiCard label="Product catalogue" value={products.data ? fmt(products.data.counts?.product_catalogue) : "…"} sub="products" accent={SERIES[3]} />
        <KpiCard label="Attribute values" value={products.data ? fmt(products.data.counts?.product_attributes) : "…"} sub="product_attributes" accent={SERIES[4]} />
      </div>

      <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ChartCard title="Master coverage" subtitle="Data Count ÷ Master Count per field" right={<OpenLink to="/count" />}>
          <Section report={counts}>
            {(d) => (
              <SimpleBar
                data={(d.rows || []).map((r) => ({ name: r.label, "Coverage %": r.coverage_pct === null ? 0 : Math.min(r.coverage_pct, 150) }))}
                bars={[{ key: "Coverage %", color: SERIES[0] }]}
                horizontal
                showValues
                valueFormatter={(v) => fmtPct(v)}
                height={280}
              />
            )}
          </Section>
        </ChartCard>

        <ChartCard title="Records by table group" subtitle="Where the data in the database sits" right={<OpenLink to="/db-tables" />}>
          <Section report={tables}>{(d) => <SimplePie data={foldForPie(d.groups, 6, "group", "rows")} />}</Section>
        </ChartCard>

        <ChartCard title="Data pipeline" subtitle="Scrap → Clean → Merge → Match → Ready" right={<OpenLink to="/hbd" />}>
          <Section report={hbd}>
            {(d) => (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-5">
                {(d.stages || []).map((s) => (
                  <div key={s.key} className="rounded-lg border border-blue-gray-100 p-3">
                    <Typography className="text-xs font-semibold text-blue-gray-600">{STAGE_SHORT[s.key] || s.title}</Typography>
                    <Typography className="mt-1 text-lg font-bold text-blue-gray-900">{fmt(s.metrics?.[0]?.value)}</Typography>
                    <Typography className="text-[11px] leading-tight text-gray-600">{s.metrics?.[0]?.label}</Typography>
                  </div>
                ))}
              </div>
            )}
          </Section>
        </ChartCard>

        <ChartCard title="Products by marketplace" subtitle="page_products by source platform" right={<OpenLink to="/data-enrichment/products" />}>
          <Section report={products}>{(d) => <SimplePie data={foldForPie(d.platforms?.platforms || [], 6, "platform", "total")} />}</Section>
        </ChartCard>

        <ChartCard title="Location rank distribution" subtitle="location_master records per City Rank" right={<OpenLink to="/ranking" />}>
          <Section report={ranking}>
            {(d) => (
              <SimplePie
                data={(d.location_rank?.distribution || []).map((x) => {
                  const n = Number((/Rank (\d)$/.exec(x.name) || [])[1]);
                  return { name: x.name, value: x.value, color: n >= 1 && n <= 5 ? RANK_RAMP[n - 1] : OTHER_GRAY };
                })}
              />
            )}
          </Section>
        </ChartCard>

        <ChartCard title="Targets progress" subtitle="Live progress against the HBD documentation targets" right={<OpenLink to="/hbd" />}>
          <Section report={hbd}>
            {(d) => (
              <SimpleBar
                data={(d.targets || []).map((t) => ({ name: t.label, "Progress %": t.progress_pct ?? 0 }))}
                bars={[{ key: "Progress %", color: RANK_RAMP[1] }]}
                horizontal
                showValues
                valueFormatter={(v) => fmtPct(v)}
                height={280}
              />
            )}
          </Section>
        </ChartCard>
      </div>

      <ChartCard title="All reports">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {REPORT_INDEX.map((r) => (
            <Link key={r.path} to={reportPath(r.path)} className="group rounded-lg border border-blue-gray-100 p-4 transition hover:border-blue-400 hover:bg-blue-50/40">
              <Typography className="flex items-center gap-1 text-sm font-bold text-blue-gray-900">
                {r.title}
                <ArrowRightIcon className="h-3.5 w-3.5 opacity-0 transition group-hover:opacity-100" />
              </Typography>
              <Typography className="mt-1 text-xs text-gray-600">{r.text}</Typography>
            </Link>
          ))}
        </div>
      </ChartCard>
    </div>
  );
}

export default ReportsOverview;
