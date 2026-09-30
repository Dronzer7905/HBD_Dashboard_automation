import React from "react";
import { Link } from "react-router-dom";
import { Typography } from "@material-tailwind/react";
import { ArrowRightIcon } from "@heroicons/react/24/solid";
import {
  useReport, ReportLayout, KpiCard, ChartCard, DataTable, SimpleBar, SimplePie, DrillLink, detailPath, reportPath,
  RANK_RAMP, OTHER_GRAY, SERIES, fmt, fmtPct,
} from "./common/reportKit";

// pivot column -> rank filter of the Detail Report
const rankParam = (col) => (col === "Unranked" ? "none" : col === "Rank 6+" ? "6+" : (/Rank (\d+)/.exec(col) || [])[1]);

function FullListLink({ to, label = "Full list", href }) {
  return (
    <Link to={href ? reportPath(href) : detailPath(to)} className="inline-flex flex-none items-center gap-1 whitespace-nowrap text-xs font-semibold text-blue-700 hover:underline">
      {label} <ArrowRightIcon className="h-3.5 w-3.5" />
    </Link>
  );
}

const rankColor = (name) => {
  const m = /Rank (\d)/.exec(name || "");
  if (m && Number(m[1]) >= 1 && Number(m[1]) <= 5 && !/\+/.test(name)) return RANK_RAMP[Number(m[1]) - 1];
  if (name === "Unranked") return "#898781";
  return OTHER_GRAY;
};

function RankListCard({ title, subtitle, block, itemLabel, list }) {
  if (!block) {
    return (
      <ChartCard title={title} subtitle={subtitle}>
        <Typography className="text-sm text-gray-600">Table not found in this database.</Typography>
      </ChartCard>
    );
  }
  const rows = block.by_rank || [];
  const chart = rows.map((r) => ({ name: r.rank === null ? "Unranked" : `Rank ${r.rank}`, [itemLabel]: r.items, "With data": r.with_data }));
  const rp = (r) => (r.rank === null ? "none" : r.rank);
  const columns = [
    { key: "rank", label: "Rank", render: (r) => <DrillLink to={{ list, rank: rp(r) }}>{r.rank === null ? "Unranked" : `Rank ${r.rank}`}</DrillLink>, csv: (r) => (r.rank === null ? "Unranked" : `Rank ${r.rank}`) },
    { key: "items", label: itemLabel, align: "right", render: (r) => <DrillLink to={{ list, rank: rp(r) }}>{fmt(r.items)}</DrillLink> },
    { key: "with_data", label: "With real data", align: "right", render: (r) => <DrillLink to={{ list, rank: rp(r), status: "has_data" }}>{fmt(r.with_data)}</DrillLink> },
    { key: "with_data_pct", label: "Coverage", align: "right", render: (r) => fmtPct(r.with_data_pct) },
    { key: "businesses", label: "Businesses", align: "right", render: (r) => fmt(r.businesses) },
  ];
  return (
    <ChartCard
      title={title}
      subtitle={`${subtitle} · ${fmt(block.total_items)} ${itemLabel.toLowerCase()} in ${block.table}. Click a number to see the list.`}
      right={<FullListLink to={{ list }} label={`All ${fmt(block.total_items)} ${itemLabel.toLowerCase()}`} />}
    >
      <SimpleBar
        data={chart}
        bars={[
          { key: itemLabel, label: itemLabel, color: SERIES[0] },
          { key: "With data", label: "With real data (business_count > 0)", color: SERIES[2] },
        ]}
        height={240}
      />
      <div className="mt-4">
        <DataTable columns={columns} rows={rows} filename={`${block.table}_by_rank`} maxHeight={280} />
      </div>
      {block.top?.length > 0 && (
        <div className="mt-5">
          <Typography className="mb-2 text-sm font-semibold text-blue-gray-800">Top 10 by business count</Typography>
          <SimpleBar
            data={block.top.map((t) => ({ name: `${t.name} (R${t.rank ?? "-"})`, Businesses: t.businesses }))}
            bars={[{ key: "Businesses", color: SERIES[0] }]}
            horizontal
            showValues
            height={Math.max(220, block.top.length * 28)}
            yWidth={170}
          />
        </div>
      )}
    </ChartCard>
  );
}

/** Ranking report - the "Ranking_Count" sheet plus Coverage Report sections 5 and 6. */
export function RankingReport() {
  const report = useReport("/hbd-reports/ranking");

  return (
    <ReportLayout
      title="Ranking Report"
      subtitle="How location_master records are spread across City Rank 1-5 for every location type (same layout as the Ranking_Count sheet and the Location Master Data Report), plus the Top cities and Top categories rank lists. Rank 1 is the highest priority."
      report={report}
      actions={<FullListLink to={null} label="Compare with the Location Master Data Report" href="/data-enrichment/location-matching" />}
    >
      {(data) => {
        const lr = data.location_rank;
        const rank1 = lr?.totals?.["Rank 1"] ?? 0;
        const ranked2to5 = lr ? ["Rank 2", "Rank 3", "Rank 4", "Rank 5"].reduce((s, k) => s + (lr.totals[k] || 0), 0) : 0;

        const pivotColumns = lr
          ? [
              { key: "location_type", label: "Location Type", render: (r) => <span className="font-semibold">{r.location_type}</span> },
              ...lr.columns.map((c) => ({
                key: c,
                label: c,
                align: "right",
                render: (r) =>
                  r[c] && r.location_type !== "(blank)" ? (
                    <DrillLink to={{ list: "location", type: r.location_type, rank: rankParam(c) }} title={`List these ${fmt(r[c])} ${r.location_type} records`}>
                      {fmt(r[c])}
                    </DrillLink>
                  ) : (
                    fmt(r[c])
                  ),
              })),
              {
                key: "total",
                label: "Total",
                align: "right",
                render: (r) => (
                  <span className="font-semibold">
                    {r.location_type !== "(blank)" ? <DrillLink to={{ list: "location", type: r.location_type }}>{fmt(r.total)}</DrillLink> : fmt(r.total)}
                  </span>
                ),
              },
            ]
          : [];
        const footer = lr
          ? {
              location_type: "Total_Count",
              ...Object.fromEntries(lr.columns.map((c) => [c, lr.totals[c] ? <DrillLink to={{ list: "location", rank: rankParam(c) }}>{fmt(lr.totals[c])}</DrillLink> : fmt(lr.totals[c])])),
              total: <DrillLink to={{ list: "location" }}>{fmt(lr.total_location_master)}</DrillLink>,
            }
          : null;

        return (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <KpiCard label="Total location master" value={fmt(lr?.total_location_master)} sub={lr ? `rank column: ${lr.rank_column}` : "location_master not available"} />
              <KpiCard label="Rank 1 records" value={fmt(rank1)} sub={`${fmtPct(lr?.distribution?.find((d) => d.name === "Rank 1")?.share_pct)} of all records`} accent={RANK_RAMP[0]} />
              <KpiCard label="Rank 2-5 records" value={fmt(ranked2to5)} accent={RANK_RAMP[3]} />
              <KpiCard label="Unranked" value={fmt(lr?.totals?.Unranked)} sub="city_rank is empty" accent={OTHER_GRAY} />
            </div>

            {lr && (
              <>
                <ChartCard
                  title="Location type × rank"
                  subtitle={`Live from ${lr.table}.${lr.rank_column} - bottom row is the total for each rank. Click any number to see the full list (e.g. City → Rank 1 shows every Rank 1 city).`}
                  className="mb-6"
                  right={<FullListLink to={{ list: "location" }} label="All locations" />}
                >
                  <DataTable columns={pivotColumns} rows={lr.rows} footer={footer} filename="ranking_count" maxHeight={460} />
                </ChartCard>

                <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
                  <ChartCard title="Rank distribution" subtitle="Share of all location_master records per rank">
                    <SimplePie data={(lr.distribution || []).map((d) => ({ name: d.name, value: d.value, color: rankColor(d.name) }))} />
                  </ChartCard>
                  <ChartCard title="Records by location type" subtitle="Stacked by rank">
                    <SimpleBar
                      data={lr.rows.map((r) => ({ name: r.location_type, ...Object.fromEntries(lr.columns.map((c) => [c, r[c]])) }))}
                      bars={lr.columns.map((c) => ({ key: c, label: c, color: rankColor(c) }))}
                      stacked
                      horizontal
                      height={Math.max(260, lr.rows.length * 40)}
                      yWidth={90}
                    />
                  </ChartCard>
                </div>
              </>
            )}

            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
              <RankListCard title="Top cities rank" subtitle="Top_cities_rank grouped by city_rank" block={data.city_rank} itemLabel="Cities" list="top_cities" />
              <RankListCard title="Business category rank" subtitle="Top_categories_rank grouped by category_rank" block={data.category_rank} itemLabel="Categories" list="top_categories" />
            </div>
          </>
        );
      }}
    </ReportLayout>
  );
}

export default RankingReport;
