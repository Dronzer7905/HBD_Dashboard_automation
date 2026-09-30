import React from "react";
import { Link } from "react-router-dom";
import { Typography } from "@material-tailwind/react";
import { ArrowRightIcon, ArrowUturnLeftIcon } from "@heroicons/react/24/solid";
import {
  useReport, ReportLayout, KpiCard, ChartCard, DataTable, STATUS, fmt, fmtPct, reportPath,
} from "../HBD Reports/common/reportKit";

const STEP_STATUS = {
  live: { label: "Live data", cls: "bg-green-50 text-green-800 border-green-200" },
  documented: { label: "Documented only", cls: "bg-blue-gray-50 text-blue-gray-700 border-blue-gray-200" },
  not_measured: { label: "No data yet", cls: "bg-amber-50 text-amber-800 border-amber-200" },
};
const PHASE_COLOR = {
  "Collect & Clean": "#2a78d6",
  Ranking: "#1c5cab",
  Mapping: "#1baf7a",
  "Category Hierarchy": "#eda100",
  "Validate & Load": "#eb6834",
  Report: "#104281",
};

const metricText = (m) => (m.format === "pct" ? fmtPct(m.value) : fmt(m.value));

function StepCard({ s }) {
  const st = STEP_STATUS[s.status] || STEP_STATUS.not_measured;
  return (
    <div className="flex h-full flex-col rounded-lg border border-blue-gray-100 bg-white p-3 shadow-sm">
      <div className="flex items-start gap-2">
        <span
          className="flex h-6 w-6 flex-none items-center justify-center rounded-full text-xs font-bold text-white"
          style={{ background: PHASE_COLOR[s.phase] || "#52514e" }}
        >
          {s.no}
        </span>
        <div className="min-w-0">
          <Typography className="text-sm font-bold leading-tight text-blue-gray-900">{s.step}</Typography>
          <Typography className="mt-0.5 text-[11px] leading-snug text-gray-600">{s.description}</Typography>
        </div>
      </div>
      <span className={`mt-2 inline-block self-start rounded-full border px-2 py-0.5 text-[11px] font-semibold ${st.cls}`}>{st.label}</span>
      {s.metrics.length > 0 && (
        <ul className="mt-2 space-y-1">
          {s.metrics.map((m) => (
            <li key={m.label} className="flex items-baseline justify-between gap-2 text-xs">
              <span className="text-gray-700">{m.label}</span>
              <span className="whitespace-nowrap font-semibold tabular-nums" style={{ color: m.status ? STATUS[m.status]?.text : "#263238" }}>
                {metricText(m)}
              </span>
            </li>
          ))}
        </ul>
      )}
      {s.note && <Typography className="mt-2 text-[11px] leading-snug text-gray-600">{s.note}</Typography>}
      {s.link && (
        <Link to={reportPath(s.link)} className="mt-auto inline-flex items-center gap-1 pt-2 text-xs font-semibold text-blue-700 hover:underline">
          Open report <ArrowRightIcon className="h-3.5 w-3.5" />
        </Link>
      )}
    </div>
  );
}

/** 01 - Final Data Enrichment Master Report: the 12 steps, each with live evidence from the database. */
export function EnrichmentProcess() {
  const report = useReport("/data-enrichment/process");
  return (
    <ReportLayout
      title="Data Enrichment - Master Report"
      subtitle="End-to-end process from the marketing CSV to TestDB (PostgreSQL), from the Final Data Enrichment Master Report. Every step shows the live numbers from the database that prove where it stands."
      report={report}
    >
      {(data) => {
        const steps = data.steps || [];
        const live = steps.filter((s) => s.status === "live").length;
        const noData = steps.filter((s) => s.status === "not_measured").length;
        const byNo = Object.fromEntries(steps.map((s) => [s.no, s]));
        const columns = [
          { key: "no", label: "#", align: "right" },
          { key: "step", label: "Step", render: (r) => <span className="font-semibold">{r.step}</span> },
          { key: "phase", label: "Phase" },
          { key: "description", label: "Description", render: (r) => <span className="block max-w-xs whitespace-normal text-xs">{r.description}</span> },
          { key: "status", label: "Status", filterValue: (r) => STEP_STATUS[r.status]?.label, csv: (r) => STEP_STATUS[r.status]?.label, render: (r) => STEP_STATUS[r.status]?.label },
          {
            key: "evidence",
            label: "Live evidence",
            filterValue: (r) => r.metrics.map((m) => `${m.label} ${metricText(m)}`).join("; "),
            csv: (r) => r.metrics.map((m) => `${m.label}: ${metricText(m)}`).join("; "),
            render: (r) => (
              <span className="block max-w-sm whitespace-normal text-xs">
                {r.metrics.length ? r.metrics.map((m) => `${m.label}: ${metricText(m)}`).join(" · ") : "—"}
              </span>
            ),
          },
          { key: "note", label: "Note", render: (r) => <span className="block max-w-xs whitespace-normal text-xs text-gray-700">{r.note || "—"}</span> },
        ];
        return (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <KpiCard label="Process steps" value={steps.length} sub={`${(data.phases || []).length} phases`} />
              <KpiCard label="Steps with live data" value={live} status="good" sub="numbers read from the database now" />
              <KpiCard label="Documented only" value={steps.length - live - noData} accent="#898781" sub="no table records this step" />
              <KpiCard label="Waiting for data" value={noData} status="warning" sub="the table for this step is not loaded yet" />
            </div>

            <ChartCard title="Objective" className="mb-6">
              <Typography className="text-sm text-blue-gray-800">{data.objective}</Typography>
              <Typography className="mt-2 text-sm text-gray-700">{data.overview}</Typography>
            </ChartCard>

            <ChartCard title="End-to-end flow" subtitle="Phases left to right; each card is one step of the report with its live numbers" className="mb-6">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-6">
                {(data.phases || []).map((ph, i) => (
                  <div key={ph.phase} className="flex flex-col gap-3">
                    <div className="flex items-center gap-2">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ background: PHASE_COLOR[ph.phase] }} />
                      <Typography className="text-xs font-bold uppercase tracking-wide text-blue-gray-700">
                        {i + 1}. {ph.phase}
                      </Typography>
                      {i < data.phases.length - 1 && <ArrowRightIcon className="ml-auto hidden h-4 w-4 text-gray-400 xl:block" />}
                    </div>
                    {ph.steps.map((n) => (
                      <StepCard key={n} s={byNo[n]} />
                    ))}
                    {ph.phase === "Validate & Load" && (
                      <div className="flex items-start gap-1.5 rounded-md border border-dashed border-gray-300 p-2 text-[11px] text-gray-600">
                        <ArrowUturnLeftIcon className="h-4 w-4 flex-none" />
                        If validation fails, the data goes back to step 2 (Data clean). The report marks this return path as an assumption.
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </ChartCard>

            <div className="mb-6 grid grid-cols-1 gap-6">
              <ChartCard title="Key points">
                <ul className="list-disc space-y-1.5 pl-5 text-sm text-blue-gray-800">
                  {(data.key_points || []).map((k) => (
                    <li key={k}>{k}</li>
                  ))}
                </ul>
                <Typography className="mt-3 text-xs text-gray-600">Reading from: {data.database}</Typography>
              </ChartCard>
              <ChartCard title="All steps" subtitle="Filter any column">
                <DataTable columns={columns} rows={steps} filename="data_enrichment_process" maxHeight={520} />
              </ChartCard>
            </div>
          </>
        );
      }}
    </ReportLayout>
  );
}

export default EnrichmentProcess;
