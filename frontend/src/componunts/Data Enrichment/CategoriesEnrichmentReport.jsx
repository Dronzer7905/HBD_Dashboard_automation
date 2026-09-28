import React from "react";
import {
  useReport, ReportLayout, KpiCard, ChartCard, DataTable, SimpleBar, SimplePie, FillBar,
  SERIES, fmt,
} from "../HBD Reports/common/reportKit";

/** Data Enrichment - page_product_categories hierarchy report. */
export function CategoriesEnrichmentReport() {
  const report = useReport("/data-enrichment/categories");
  return (
    <ReportLayout
      title="Data Enrichment - Categories"
      subtitle="The product category tree (page_product_categories): how many categories sit at each level, and how many are correctly linked to a parent."
      report={report}
    >
      {(data) => {
        const levels = data.levels || [];
        const top = levels.length ? Math.min(...levels.map((l) => l.category_level)) : null;
        const missingBelowTop = levels.filter((l) => l.category_level !== top).reduce((s, l) => s + l.missing_parent, 0);
        const columns = [
          { key: "category_level", label: "Level", render: (r) => `Level ${r.category_level}${r.category_level === top ? " (top)" : ""}` },
          { key: "total", label: "Categories", align: "right", render: (r) => fmt(r.total) },
          { key: "has_parent", label: "Has parent", align: "right", render: (r) => fmt(r.has_parent) },
          {
            key: "missing_parent",
            label: "Missing parent",
            align: "right",
            render: (r) => <span className={r.missing_parent > 0 && r.category_level !== top ? "font-semibold text-red-700" : ""}>{fmt(r.missing_parent)}</span>,
          },
          { key: "linked", label: "Linked %", render: (r) => <FillBar value={r.total ? (r.has_parent * 100) / r.total : 0} />, csv: (r) => (r.total ? ((r.has_parent * 100) / r.total).toFixed(2) : "") },
        ];
        return (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <KpiCard label="Categories" value={fmt(data.total_categories)} sub={`${levels.length} levels`} />
              <KpiCard label="Top-level categories" value={fmt(levels.find((l) => l.category_level === top)?.total)} accent={SERIES[2]} />
              <KpiCard label="Missing a parent (below top level)" value={fmt(missingBelowTop)} status={missingBelowTop ? "warning" : "good"} sub="parent ID blank in the source Category Master" />
            </div>
            <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
              <ChartCard title="Categories per level" subtitle="Stacked: linked to a parent vs not" className="xl:col-span-2">
                <SimpleBar
                  data={levels.map((l) => ({ name: `Level ${l.category_level}`, "Has parent": l.has_parent, "Missing parent": l.missing_parent }))}
                  bars={[
                    { key: "Has parent", color: SERIES[0] },
                    { key: "Missing parent", color: SERIES[1] },
                  ]}
                  stacked
                  height={320}
                />
              </ChartCard>
              <ChartCard title="Share by level">
                <SimplePie data={levels.map((l) => ({ name: `Level ${l.category_level}`, value: l.total }))} />
              </ChartCard>
            </div>
            <ChartCard title="Parent-link health by level">
              <DataTable columns={columns} rows={levels} filename="category_levels" />
            </ChartCard>
          </>
        );
      }}
    </ReportLayout>
  );
}

export default CategoriesEnrichmentReport;
