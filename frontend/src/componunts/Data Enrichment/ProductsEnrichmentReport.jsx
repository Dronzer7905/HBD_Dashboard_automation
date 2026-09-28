import React from "react";
import {
  useReport, ReportLayout, KpiCard, ChartCard, DataTable, SimpleBar, SimplePie, FillBar, foldForPie,
  SERIES, fmt, fmtPct,
} from "../HBD Reports/common/reportKit";

/** Data Enrichment - page_products by source marketplace. */
export function ProductsEnrichmentReport() {
  const report = useReport("/data-enrichment/products-by-platform");
  return (
    <ReportLayout
      title="Data Enrichment - Products by Marketplace"
      subtitle="page_products split by the marketplace each product came from (Amazon, DMart, Flipkart, BigBasket, Blinkit, Zepto, IndiaMART, JioMart), and how many got matched to a category."
      report={report}
    >
      {(data) => {
        const platforms = data.platforms || [];
        const withCat = platforms.reduce((s, p) => s + p.with_category, 0);
        const columns = [
          { key: "platform", label: "Marketplace", render: (r) => <span className="font-semibold">{r.platform}</span> },
          { key: "total", label: "Products", align: "right", render: (r) => fmt(r.total) },
          { key: "with_category", label: "With category", align: "right", render: (r) => fmt(r.with_category) },
          { key: "without_category", label: "Without category", align: "right", render: (r) => fmt(r.without_category) },
          { key: "category_match_pct", label: "Category match", render: (r) => <FillBar value={r.category_match_pct} />, csv: (r) => r.category_match_pct },
        ];
        return (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <KpiCard label="Products" value={fmt(data.total_products)} sub={`${platforms.length} sources`} />
              <KpiCard label="Matched to a category" value={fmt(withCat)} sub={fmtPct(data.total_products ? (withCat * 100) / data.total_products : null)} accent={SERIES[2]} />
              <KpiCard label="No category yet" value={fmt(data.total_products - withCat)} status="warning" sub="category text did not match the tree" />
            </div>
            <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
              <ChartCard title="Products per marketplace" subtitle="Stacked: with vs without a category">
                <SimpleBar
                  data={platforms.map((p) => ({ name: p.platform, "With category": p.with_category, "Without category": p.without_category }))}
                  bars={[
                    { key: "With category", color: SERIES[0] },
                    { key: "Without category", color: SERIES[1] },
                  ]}
                  stacked
                  horizontal
                  height={Math.max(280, platforms.length * 38)}
                  yWidth={100}
                />
              </ChartCard>
              <ChartCard title="Share of products" subtitle="Top 5 marketplaces + the rest">
                <SimplePie data={foldForPie(platforms, 6, "platform", "total")} />
              </ChartCard>
            </div>
            <ChartCard title="Category-match coverage">
              <DataTable columns={columns} rows={platforms} filename="products_by_marketplace" />
            </ChartCard>
          </>
        );
      }}
    </ReportLayout>
  );
}

export default ProductsEnrichmentReport;
