import React from "react";
import { Typography } from "@material-tailwind/react";
import {
  useReport, ReportLayout, KpiCard, ChartCard, DataTable, SimpleBar, SimplePie, foldForPie,
  SERIES, fmt, fmtPct,
} from "../HBD Reports/common/reportKit";

/** Data Enrichment - all six product tables in one report. */
export function AllProductTables() {
  const report = useReport("/data-enrichment/all-tables");
  return (
    <ReportLayout
      title="Data Enrichment - All Product Tables"
      subtitle="Everything about the six product tables in one place: how many rows each has, what columns they hold, which marketplace the products came from, the category tree and the filled attributes."
      report={report}
    >
      {(data) => {
        const c = data.counts || {};
        const tables = data.tables || [];
        const platforms = data.platforms?.platforms || [];
        const levels = data.categories?.levels || [];
        const attrs = data.attributes?.by_attribute || [];

        const tableColumns = [
          { key: "label", label: "Table", render: (r) => (
            <div>
              <div className="font-semibold">{r.label}</div>
              <div className="font-mono text-xs text-gray-600">{r.table}</div>
            </div>
          ), csv: (r) => r.table },
          { key: "purpose", label: "What it holds", render: (r) => <span className="block max-w-xs whitespace-normal text-xs">{r.purpose}</span> },
          { key: "rows", label: "Rows", align: "right", render: (r) => fmt(r.rows) },
          { key: "columns_count", label: "Columns", align: "right" },
          {
            key: "columns",
            label: "Column names",
            render: (r) => <span className="block max-w-md whitespace-normal font-mono text-[11px] text-gray-700">{(r.columns || []).map((x) => x.name).join(", ")}</span>,
            csv: (r) => (r.columns || []).map((x) => x.name).join(" | "),
          },
        ];

        return (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-6">
              {tables.map((t, i) => (
                <KpiCard key={t.table} label={t.label} value={fmt(t.rows)} sub={t.table} accent={SERIES[i % SERIES.length]} />
              ))}
            </div>

            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <KpiCard label="Products with an affiliate link" value={fmtPct(data.affiliate_share_pct, 2)} sub="affiliate_products ÷ product_catalogue" />
              <KpiCard label="Attribute values per product" value={data.avg_attributes_per_product ?? "—"} sub="product_attributes ÷ page_products" accent={SERIES[4]} />
              <KpiCard
                label="Products with a category"
                value={fmtPct(c.page_products ? (platforms.reduce((s, p) => s + p.with_category, 0) * 100) / c.page_products : null)}
                sub="page_products with category_id"
                accent={SERIES[2]}
              />
            </div>

            <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
              <ChartCard title="Rows per table" subtitle="Live row count of each product table">
                <SimpleBar
                  data={tables.map((t) => ({ name: t.label, Rows: t.rows }))}
                  bars={[{ key: "Rows", color: SERIES[0] }]}
                  horizontal
                  showValues
                  height={280}
                  yWidth={150}
                />
              </ChartCard>
              <ChartCard title="Products by marketplace" subtitle="page_products by source (from the slug prefix)">
                <SimplePie data={foldForPie(platforms, 6, "platform", "total")} />
              </ChartCard>
              <ChartCard title="Category tree" subtitle="page_product_categories per level">
                <SimpleBar
                  data={levels.map((l) => ({ name: `Level ${l.category_level}`, "Has parent": l.has_parent, "Missing parent": l.missing_parent }))}
                  bars={[
                    { key: "Has parent", color: SERIES[0] },
                    { key: "Missing parent", color: SERIES[1] },
                  ]}
                  stacked
                  height={260}
                />
              </ChartCard>
              <ChartCard title="Filled attributes" subtitle="Real values stored per attribute type">
                <SimplePie data={attrs.map((a) => ({ name: a.attribute_name, value: a.total_values }))} />
              </ChartCard>
            </div>

            <ChartCard title="Table details" subtitle="Every product table with its columns">
              <DataTable columns={tableColumns} rows={tables} filename="product_tables" maxHeight={560} />
              <Typography className="mt-3 text-xs text-gray-600">
                Row counts differ a lot on purpose: product_catalogue has one row per product, product_attributes_master one row per
                attribute definition, and product_attributes one row per product per filled attribute.
              </Typography>
            </ChartCard>
          </>
        );
      }}
    </ReportLayout>
  );
}

export default AllProductTables;
