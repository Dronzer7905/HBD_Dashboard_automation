import React from "react";
import { Typography } from "@material-tailwind/react";
import { ExclamationTriangleIcon } from "@heroicons/react/24/solid";
import {
  useReport, ReportLayout, KpiCard, ChartCard, DataTable, SimpleBar, SimplePie, StatusBadge, FillBar, foldForPie,
  SERIES, fmt, fmtPct,
} from "../HBD Reports/common/reportKit";

const pctOf = (fields, key) => fields.find((f) => f.key === key)?.fill_pct;

function DocTables({ doc }) {
  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
      <ChartCard title="Category vocabulary" subtitle="Used when the URL has no category marker - first match wins, in this order">
        <DataTable
          columns={[
            { key: "category", label: "Category returned", render: (r) => <span className="font-semibold">{r.category}</span> },
            { key: "terms", label: "Recognition terms" },
          ]}
          rows={doc.category_vocab}
          filename="url_category_vocabulary"
          maxHeight={320}
        />
      </ChartCard>
      <ChartCard title="Limits, risks and recommended improvements" subtitle="Section 9 of the document">
        <DataTable
          columns={[
            { key: "observation", label: "Observation", render: (r) => <span className="block max-w-[180px] whitespace-normal font-semibold">{r.observation}</span> },
            { key: "why", label: "Why it matters", render: (r) => <span className="block max-w-xs whitespace-normal text-xs">{r.why}</span> },
            { key: "improvement", label: "Recommended improvement", render: (r) => <span className="block max-w-xs whitespace-normal text-xs">{r.improvement}</span> },
          ]}
          rows={doc.limits}
          filename="url_extraction_limits"
          maxHeight={420}
        />
      </ChartCard>
    </div>
  );
}

/** 02 - Dynamic URL Extraction and CSV Enrichment System, with live numbers from url_extraction_master. */
export function UrlExtractionReport() {
  const report = useReport("/data-enrichment/url-extraction");
  return (
    <ReportLayout
      title="Data Enrichment - URL Extraction"
      subtitle="How the Python pipeline turns ranking CSV files into records with city, state, region, category, source and keywords taken from the URL - and, live from url_extraction_master, how much of each field it actually filled."
      report={report}
    >
      {(data) => {
        const doc = data.doc || {};
        const live = data.live || {};
        if (!live.found) {
          return (
            <>
              <div className="mb-6 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
                <ExclamationTriangleIcon className="mt-0.5 h-5 w-5 flex-none text-amber-700" />
                <Typography className="text-sm text-amber-900">
                  The table <span className="font-mono">{doc.table}</span> is not in the database yet, so there are no live numbers.
                  Below is the documented design ({doc.title}, {doc.date}). This page fills in automatically once the table is loaded.
                </Typography>
              </div>
              <ChartCard title="Output fields" subtitle="What each enrichment column is filled with" className="mb-6">
                <DataTable columns={[{ key: "label", label: "Output field" }, { key: "rule", label: "Population rule" }]} rows={doc.fields || []} filename="url_output_fields" />
              </ChartCard>
              <DocTables doc={doc} />
            </>
          );
        }
        const fields = live.fields || [];
        const outFields = fields.filter((f) => (doc.fields || []).some((d) => d.key === f.key));
        const fieldColumns = [
          { key: "label", label: "Field", render: (r) => <span className="font-semibold">{r.label}</span> },
          { key: "rule", label: "Rule (from the document)", render: (r) => <span className="block max-w-sm whitespace-normal text-xs">{r.rule}</span> },
          { key: "exists", label: "Column in table", filterValue: (r) => (r.exists ? "Yes" : "No"), csv: (r) => (r.exists ? "Yes" : "No"), render: (r) => (r.exists ? "Yes" : <span className="text-red-700">Missing</span>) },
          { key: "filled", label: "Rows filled", align: "right", render: (r) => fmt(r.filled) },
          { key: "fill_pct", label: "Fill %", render: (r) => (r.fill_pct === null ? "—" : <FillBar value={r.fill_pct} />) },
        ];
        return (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
              <KpiCard label="Rows" value={fmt(live.total)} sub={live.table} />
              <KpiCard label="CSV files" value={fmt((live.source_files || []).length)} sub="distinct source_file" accent={SERIES[3]} />
              <KpiCard label="City found" value={fmtPct(pctOf(fields, "city"))} sub="of rows" accent={SERIES[0]} />
              <KpiCard label="Category found" value={fmtPct(pctOf(fields, "category"))} sub="of rows" accent={SERIES[2]} />
              <KpiCard label="Source found" value={fmtPct(pctOf(fields, "source"))} sub="of rows" accent={SERIES[1]} />
            </div>

            <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
              <ChartCard title="How much of each output field is filled" subtitle="Blank means the URL gave no evidence (by design)">
                <SimpleBar
                  data={outFields.filter((f) => f.exists).map((f) => ({ name: f.label, "Fill %": f.fill_pct || 0 }))}
                  bars={[{ key: "Fill %", color: SERIES[0] }]}
                  horizontal
                  showValues
                  valueFormatter={(v) => fmtPct(v)}
                  height={Math.max(280, outFields.length * 26)}
                  yWidth={170}
                />
              </ChartCard>
              <ChartCard title="What the document says vs the data" subtitle="Documented behaviour, checked on the live table">
                <DataTable
                  columns={[
                    { key: "check", label: "Documented behaviour", render: (r) => <span className="block max-w-xs whitespace-normal">{r.check}</span> },
                    {
                      key: "holds",
                      label: "Holds?",
                      filterValue: (r) => (r.holds === null ? "Info" : r.holds ? "Yes" : "No"),
                      csv: (r) => (r.holds === null ? "Info" : r.holds ? "Yes" : "No"),
                      render: (r) => (r.holds === null ? <span className="text-xs text-gray-600">Info</span> : <StatusBadge status={r.holds ? "good" : "warning"} label={r.holds ? "Yes" : "No"} />),
                    },
                    { key: "live", label: "Live" },
                  ]}
                  rows={live.checks || []}
                  filename="url_extraction_checks"
                  maxHeight={420}
                />
              </ChartCard>
            </div>

            <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
              <ChartCard title="Top sources" subtitle="Domain taken from the URL">
                <SimpleBar data={(live.top?.source || []).slice(0, 10)} xKey="name" bars={[{ key: "value", label: "Rows", color: SERIES[1] }]} horizontal showValues height={300} yWidth={120} />
              </ChartCard>
              <ChartCard title="Categories" subtitle="Category found in the URL / keyword">
                <SimplePie data={foldForPie(live.top?.category || [], 6)} stack />
              </ChartCard>
              <ChartCard title="Top cities" subtitle="City found in the URL">
                <SimpleBar data={(live.top?.city || []).slice(0, 10)} xKey="name" bars={[{ key: "value", label: "Rows", color: SERIES[0] }]} horizontal showValues height={300} yWidth={110} />
              </ChartCard>
            </div>

            <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
              <ChartCard title="All fields" subtitle="Output fields from the document plus the input keyword metrics" className="xl:col-span-2">
                <DataTable columns={fieldColumns} rows={fields} filename="url_extraction_fields" maxHeight={560} />
              </ChartCard>
              <ChartCard title="CSV files loaded" subtitle="Rows per source_file">
                <DataTable
                  columns={[
                    { key: "name", label: "File" },
                    { key: "value", label: "Rows", align: "right", render: (r) => fmt(r.value) },
                  ]}
                  rows={live.source_files || []}
                  filename="url_extraction_source_files"
                  maxHeight={560}
                />
              </ChartCard>
            </div>

            <DocTables doc={doc} />
          </>
        );
      }}
    </ReportLayout>
  );
}

export default UrlExtractionReport;
