import React from "react";
import {
  useReport, ReportLayout, KpiCard, ChartCard, DataTable, SimpleBar, SimplePie,
  SERIES, fmt, fmtPct,
} from "../HBD Reports/common/reportKit";

/** Data Enrichment - product attributes (Brand, MRP, Selling Price, Rating). */
export function AttributesEnrichmentReport() {
  const report = useReport("/data-enrichment/attributes");
  return (
    <ReportLayout
      title="Data Enrichment - Product Attributes"
      subtitle="Attribute definitions per category (product_attributes_master) and the real values filled in for products (product_attributes). Only real values from the source data are stored - empty ones are skipped."
      report={report}
    >
      {(data) => {
        const attrs = data.by_attribute || [];
        const total = data.total_attribute_values || 0;
        const columns = [
          { key: "attribute_name", label: "Attribute", render: (r) => <span className="font-semibold">{r.attribute_name}</span> },
          { key: "definitions", label: "Categories using it", align: "right", render: (r) => fmt(r.definitions) },
          { key: "total_values", label: "Filled values", align: "right", render: (r) => fmt(r.total_values) },
          { key: "share", label: "Share", align: "right", render: (r) => fmtPct(total ? (r.total_values * 100) / total : null), csv: (r) => (total ? ((r.total_values * 100) / total).toFixed(2) : "") },
        ];
        return (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <KpiCard label="Attribute definitions" value={fmt(data.total_attribute_definitions)} sub="product_attributes_master" />
              <KpiCard label="Filled values" value={fmt(total)} sub="product_attributes" accent={SERIES[2]} />
              <KpiCard label="Attribute types" value={attrs.length} sub={attrs.map((a) => a.attribute_name).join(", ")} accent={SERIES[4]} />
            </div>
            <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
              <ChartCard title="Filled values by attribute">
                <SimpleBar data={attrs.map((a) => ({ name: a.attribute_name, Values: a.total_values }))} bars={[{ key: "Values", color: SERIES[0] }]} showValues height={300} />
              </ChartCard>
              <ChartCard title="Share of filled values">
                <SimplePie data={attrs.map((a) => ({ name: a.attribute_name, value: a.total_values }))} />
              </ChartCard>
            </div>
            <ChartCard title="Attribute details">
              <DataTable columns={columns} rows={attrs} filename="product_attributes" />
            </ChartCard>
          </>
        );
      }}
    </ReportLayout>
  );
}

export default AttributesEnrichmentReport;
