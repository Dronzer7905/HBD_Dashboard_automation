import React from "react";
import { Card, CardBody, Typography } from "@material-tailwind/react";
import { ChevronRightIcon } from "@heroicons/react/24/solid";
import {
  useReport, ReportLayout, KpiCard, ChartCard, DataTable, SimpleBar, SimplePie, FillBar,
  SERIES, RANK_RAMP, fmt, fmtPct,
} from "./common/reportKit";

const GLOSSARY = [
  ["Scrap", "automatically collecting data from a website"],
  ["Clean", "fixing formatting and removing junk from raw scraped data"],
  ["Merge", "combining duplicate records that refer to the same real thing into one"],
  ["Matched", "a record successfully verified against our Master data"],
  ["Unmatched", "a record that could not be confidently verified yet, kept aside for review"],
  ["Master Data", "our own trusted reference lists (locations, categories, products)"],
  ["Rank", "the priority order in which locations / categories / products are worked on"],
];

function Pipeline({ stages }) {
  return (
    <div className="mb-6 grid grid-cols-1 gap-3 lg:grid-cols-5">
      {stages.map((s, i) => (
        <div key={s.key} className="relative">
          <Card className="h-full border border-blue-gray-100 shadow-sm">
            <CardBody className="p-4">
              <Typography className="text-sm font-bold text-blue-gray-900">{s.title}</Typography>
              <Typography className="mt-1 text-xs text-gray-600">{s.text}</Typography>
              <div className="mt-3 space-y-2">
                {s.metrics.map((m) => (
                  <div key={m.label} title={`Source: ${m.source}`}>
                    <Typography className="text-lg font-bold leading-tight text-blue-gray-900">{fmt(m.value)}</Typography>
                    <Typography className="text-[11px] leading-tight text-gray-600">{m.label}</Typography>
                  </div>
                ))}
              </div>
            </CardBody>
          </Card>
          {i < stages.length - 1 && (
            <ChevronRightIcon className="absolute -right-3 top-1/2 z-10 hidden h-5 w-5 -translate-y-1/2 rounded-full bg-white text-blue-gray-400 lg:block" />
          )}
        </div>
      ))}
    </div>
  );
}

/** HBD Dashboard documentation, as a live report. */
export function HbdReport() {
  const report = useReport("/hbd-reports/hbd");
  return (
    <ReportLayout
      title="HBD Report"
      subtitle="The HBD Dashboard collects business and product data from many websites, cleans it, checks it against our master lists and shows the usable data on one screen. Each stage below shows the live numbers behind it."
      report={report}
    >
      {(data) => {
        const targets = data.targets || [];
        const tiers = data.tiers || [];
        const ready = data.stages?.find((s) => s.key === "ready");
        const match = data.stages?.find((s) => s.key === "match");

        const targetColumns = [
          { key: "label", label: "Master (Target)", render: (r) => <span className="font-semibold">{r.label}</span> },
          { key: "total_target", label: "Total Target", align: "right", render: (r) => fmt(r.total_target) },
          { key: "rank1_target", label: "Rank 1 Target", align: "right", render: (r) => fmt(r.rank1_target) },
          { key: "achieved", label: "Matched (Done) - live", align: "right", render: (r) => fmt(r.achieved) },
          { key: "pending", label: "Pending (Not Scraped)", align: "right", render: (r) => fmt(r.pending) },
          { key: "progress_pct", label: "Progress", render: (r) => <FillBar value={r.progress_pct} />, csv: (r) => r.progress_pct },
          {
            key: "achieved_source",
            label: "How 'done' is measured",
            render: (r) => <span className="block max-w-xs whitespace-normal text-xs text-gray-600">{r.achieved_source || "—"}</span>,
          },
        ];

        return (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <KpiCard label="Listing master records" value={fmt(ready?.metrics?.[0]?.value)} sub="master_table (ready to use)" />
              <KpiCard label="Product catalogue" value={fmt(ready?.metrics?.[1]?.value)} sub="affiliate / product stream" accent={SERIES[1]} />
              <KpiCard label="Verified (Tier 1)" value={fmt(match?.metrics?.[0]?.value)} sub={`${fmtPct(tiers[0]?.share_pct)} of tiered records`} accent={SERIES[2]} />
              <KpiCard label="Records in cleaning tiers" value={fmt(data.tier_total)} sub="tier 1 to tier 5 tables" accent={SERIES[3]} />
            </div>

            <Typography variant="h6" color="blue-gray" className="mb-3">
              The journey of a piece of data
            </Typography>
            <Pipeline stages={data.stages || []} />

            <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
              <ChartCard title="Cleaning tiers" subtitle="Where every cleaned business record currently sits">
                <SimpleBar
                  data={tiers.map((t) => ({ name: t.name.replace(" - ", ": "), Records: t.value || 0 }))}
                  bars={[{ key: "Records", color: SERIES[0] }]}
                  horizontal
                  showValues
                  height={260}
                  yWidth={190}
                />
              </ChartCard>
              <ChartCard title="Tier share" subtitle="Tier 1 = verified; Tier 2-5 = something missing or duplicated">
                <SimplePie data={tiers.map((t) => ({ name: t.name, value: t.value || 0 }))} />
              </ChartCard>
            </div>

            <ChartCard
              title="Ranking targets vs live progress"
              subtitle="Targets are the goals written in the HBD documentation (Section 4). 'Matched (Done)' is live: distinct values in the scraped data that exist in the master list."
              className="mb-6"
            >
              <DataTable columns={targetColumns} rows={targets} filename="hbd_targets_vs_progress" maxHeight={420} />
              <div className="mt-5">
                <SimpleBar
                  data={targets.map((t) => ({ name: t.label, "Progress %": t.progress_pct ?? 0 }))}
                  bars={[{ key: "Progress %", color: RANK_RAMP[1] }]}
                  horizontal
                  showValues
                  valueFormatter={(v) => fmtPct(v)}
                  height={280}
                  yWidth={140}
                />
              </div>
            </ChartCard>

            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
              <ChartCard title="How to read the targets">
                <Typography className="text-sm text-blue-gray-800">
                  Work is prioritised by Rank: Rank 1 items are the most important and are done first. For each master type the team set a
                  total target and a Rank 1 target. If someone asks "why is City X missing from the dashboard?", the answer is often that it
                  falls under a lower rank and its data collection has not reached it yet - not that something is broken.
                </Typography>
              </ChartCard>
              <ChartCard title="Quick glossary">
                <dl className="space-y-1.5 text-sm">
                  {GLOSSARY.map(([k, v]) => (
                    <div key={k} className="flex gap-2">
                      <dt className="w-28 flex-none font-semibold text-blue-gray-900">{k}</dt>
                      <dd className="text-blue-gray-700">{v}</dd>
                    </div>
                  ))}
                </dl>
              </ChartCard>
            </div>
          </>
        );
      }}
    </ReportLayout>
  );
}

export default HbdReport;
