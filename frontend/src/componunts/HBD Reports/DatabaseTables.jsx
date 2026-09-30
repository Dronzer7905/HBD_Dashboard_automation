import React, { useState } from "react";
import {
  Button, Typography, Dialog, DialogHeader, DialogBody, DialogFooter,
} from "@material-tailwind/react";
import { PencilSquareIcon } from "@heroicons/react/24/solid";
import {
  useReport, ReportLayout, KpiCard, ChartCard, DataTable, SimpleBar, SimplePie, StatusBadge, FillBar,
  SERIES, STATUS, fmt, fmtPct,
} from "./common/reportKit";
import api from "../../utils/Api";

// Final status -> colour + icon (never colour alone)
const STATUS_KIND = {
  Complete: "good",
  Partial: "warning",
  "In progress": "warning",
  Empty: "critical",
  "Not started": "critical",
};
const STATUS_ORDER = ["Complete", "Partial", "In progress", "Not started", "Empty", "Unknown"];

const summarize = (tables) =>
  STATUS_ORDER.map((st) => ({ name: st, value: tables.filter((t) => t.status === st).length })).filter((s) => s.value > 0);

function SheetTag() {
  return (
    <span className="ml-0.5 rounded bg-amber-50 px-1 py-px text-[10px] font-semibold uppercase text-amber-800" title="From the Data Enrichment team's sheet">
      sheet
    </span>
  );
}

function StatusCell({ row }) {
  const kind = STATUS_KIND[row.status];
  return (
    <div className="min-w-[110px]">
      {kind ? (
        <StatusBadge status={kind} label={row.status} />
      ) : (
        <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-700">{row.status}</span>
      )}
      <div className="mt-0.5 text-[11px] text-gray-600">
        {row.team_status ? `set by team · auto: ${row.auto_status}` : "auto from data"}
      </div>
    </div>
  );
}

function EditStatusDialog({ row, statuses, onClose, onSaved }) {
  const [form, setForm] = useState({
    team_status: row?.team_status || "",
    done_by: row?.done_by || row?.sheet_done_by || "",
    remarks: row?.team_remarks || "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const save = async (body) => {
    setSaving(true);
    setError(null);
    try {
      const res = await api.put(`/hbd-reports/table-status/${encodeURIComponent(row.table)}`, body);
      if (res.data?.status !== "success") throw new Error(res.data?.message || "Save failed");
      onSaved(row.table, res.data.data);
    } catch (e) {
      setError(e?.response?.data?.message || e?.message || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={!!row} handler={onClose} size="sm">
      <DialogHeader className="flex flex-col items-start gap-1">
        <span className="text-lg">Update table status</span>
        <span className="font-mono text-sm font-normal text-gray-700">{row?.table}</span>
      </DialogHeader>
      <DialogBody className="space-y-4">
        <div className="rounded-md bg-blue-gray-50 px-3 py-2 text-sm text-blue-gray-800">
          From the data: <b>{row?.auto_status}</b>
          {row?.fill_pct !== null && row?.fill_pct !== undefined ? ` · ${fmtPct(row.fill_pct)} of columns filled` : ""}
          {` · ${fmt(row?.rows)} rows`}
        </div>
        <label className="block text-sm font-semibold text-blue-gray-800">
          Status
          <select
            value={form.team_status}
            onChange={(e) => setForm({ ...form, team_status: e.target.value })}
            className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-normal"
          >
            <option value="">Automatic (use the data: {row?.auto_status})</option>
            {statuses.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm font-semibold text-blue-gray-800">
          Done by
          <input
            value={form.done_by}
            maxLength={255}
            onChange={(e) => setForm({ ...form, done_by: e.target.value })}
            placeholder="Name of the person who worked on it"
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-normal"
          />
        </label>
        <label className="block text-sm font-semibold text-blue-gray-800">
          Remarks
          <textarea
            value={form.remarks}
            maxLength={2000}
            rows={3}
            onChange={(e) => setForm({ ...form, remarks: e.target.value })}
            placeholder="What's done, what's pending..."
            className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-normal"
          />
        </label>
        {error && <Typography className="text-sm text-red-700">{error}</Typography>}
        <Typography className="text-xs text-gray-600">
          Saved in the database (table <span className="font-mono">hbd_report_table_status</span>). The table's own data is not changed.
        </Typography>
      </DialogBody>
      <DialogFooter className="flex justify-between gap-2">
        <Button
          variant="text"
          color="red"
          disabled={saving || !(row?.team_status || row?.done_by || row?.team_remarks)}
          onClick={() => save({ team_status: "", done_by: "", remarks: "" })}
        >
          Clear
        </Button>
        <div className="flex gap-2">
          <Button variant="text" color="blue-gray" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button color="blue" onClick={() => save(form)} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </Button>
        </div>
      </DialogFooter>
    </Dialog>
  );
}

/** Every table in the database - the "dashboard db new" sheet, live, with completion status. */
export function DatabaseTables() {
  const [exact, setExact] = useState(false);
  const [editing, setEditing] = useState(null);
  const report = useReport("/hbd-reports/db-tables", { exact });

  const onSaved = (table, saved) => {
    report.mutate((data) => {
      const tables = data.tables.map((t) =>
        t.table !== table
          ? t
          : {
              ...t,
              team_status: saved.team_status || null,
              status: saved.team_status || t.auto_status,
              done_by: saved.done_by || "",
              team_remarks: saved.team_remarks || "",
              updated_by: saved.updated_by || "",
              updated_at: saved.updated_at,
            },
      );
      return { ...data, tables, status_summary: summarize(tables) };
    });
    setEditing(null);
  };

  const exactToggle = (
    <Button
      size="sm"
      variant={exact ? "filled" : "outlined"}
      color="blue-gray"
      onClick={() => setExact((e) => !e)}
      title="Exact COUNT(*) on every table - slower on big tables"
    >
      {exact ? "Exact counts: ON" : "Exact counts: OFF"}
    </Button>
  );

  return (
    <ReportLayout
      title="Database Tables"
      subtitle="Every table with its group, columns, number of records and whether it is complete. Status is worked out from the data automatically; click Edit on any row to set the team's own status, who did it, and remarks - it is saved in the database."
      report={report}
      actions={exactToggle}
    >
      {(data) => {
        const tables = data.tables || [];
        const groups = data.groups || [];
        const t = data.totals || {};
        const count = (...names) => tables.filter((x) => names.includes(x.status)).length;
        const statusPie = (data.status_summary || summarize(tables)).map((s) => ({
          ...s,
          color: STATUS[STATUS_KIND[s.name]]?.color || "#b4b2a9",
        }));

        const columns = [
          {
            key: "edit",
            label: "Edit",
            filter: false,
            csv: () => "",
            nowrap: true,
            render: (r) => (
              <Button size="sm" variant="outlined" color="blue" className="flex items-center gap-1 px-2 py-1" onClick={() => setEditing(r)}>
                <PencilSquareIcon className="h-4 w-4" /> Edit
              </Button>
            ),
          },
          { key: "group", label: "Group" },
          { key: "subgroup", label: "Subgroup", render: (r) => r.subgroup || "" },
          { key: "table", label: "Table name", render: (r) => <span className="font-mono text-xs font-semibold">{r.table}</span> },
          {
            key: "rows",
            label: "No. of data",
            align: "right",
            render: (r) => (
              <span title={r.remarks}>
                {r.count_type === "estimate" ? "~" : ""}
                {fmt(r.rows)}
              </span>
            ),
          },
          {
            key: "fill_pct",
            label: "Columns filled",
            render: (r) =>
              r.fill_pct === null || r.fill_pct === undefined ? (
                <span className="text-xs text-gray-500">—</span>
              ) : (
                <div title={`${r.empty_columns ?? 0} completely empty column(s)`}>
                  <FillBar value={r.fill_pct} color={STATUS[STATUS_KIND[r.auto_status]]?.color || SERIES[0]} />
                </div>
              ),
          },
          { key: "status", label: "Status", render: (r) => <StatusCell row={r} /> },
          {
            key: "done_by",
            label: "Done by",
            filterValue: (r) => r.done_by || r.sheet_done_by || "",
            csv: (r) => r.done_by || r.sheet_done_by || "",
            sortValue: (r) => r.done_by || r.sheet_done_by || null,
            render: (r) =>
              r.done_by ? (
                r.done_by
              ) : r.sheet_done_by ? (
                <span title="From the Data Enrichment sheet">
                  {r.sheet_done_by} <SheetTag />
                </span>
              ) : (
                <span className="text-gray-400">—</span>
              ),
          },
          {
            key: "team_remarks",
            label: "Remarks",
            filterValue: (r) => r.team_remarks || r.sheet_remarks || "",
            csv: (r) => r.team_remarks || r.sheet_remarks || "",
            render: (r) => (
              <span className="block max-w-xs whitespace-normal text-xs text-blue-gray-800">
                {r.team_remarks ||
                  (r.sheet_remarks ? (
                    <>
                      {r.sheet_remarks} <SheetTag />
                    </>
                  ) : (
                    <span className="text-gray-400">—</span>
                  ))}
              </span>
            ),
          },
          {
            key: "updated_at",
            label: "Last update",
            render: (r) =>
              r.updated_at ? (
                <span className="text-xs text-gray-700">
                  {new Date(r.updated_at).toLocaleDateString("en-IN")}
                  {r.updated_by ? <span className="block text-gray-500">{r.updated_by}</span> : null}
                </span>
              ) : (
                <span className="text-gray-400">—</span>
              ),
            csv: (r) => (r.updated_at ? `${r.updated_at} ${r.updated_by || ""}`.trim() : ""),
          },
          {
            key: "detail",
            label: "Detail",
            filterValue: (r) => `${r.sheet_detail || ""} ${r.detail || ""}`,
            csv: (r) => r.sheet_detail || r.detail,
            render: (r) => (
              <span className="block max-w-sm whitespace-normal text-xs text-gray-700" title={(r.columns || []).join(", ")}>
                {r.sheet_detail ? (
                  <>
                    {r.sheet_detail} <SheetTag />
                    <span className="mt-0.5 block text-[11px] text-gray-500">{r.detail}</span>
                  </>
                ) : (
                  r.detail
                )}
              </span>
            ),
          },
          { key: "auto_status", label: "Auto status", hidden: true },
          { key: "team_status", label: "Team status", hidden: true },
          { key: "remarks", label: "System note", hidden: true },
        ];

        return (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <KpiCard label="Tables" value={fmt(t.tables)} sub={`${fmt(t.rows)} records in ${groups.length} groups`} />
              <KpiCard label="Complete" value={count("Complete")} status="good" sub={`columns ≥ ${data.complete_fill_pct}% filled, or marked by team`} />
              <KpiCard label="Partial / in progress" value={count("Partial", "In progress")} status="warning" sub="has data, but many blank columns" />
              <KpiCard label="Empty / not started" value={count("Empty", "Not started")} status="critical" sub="no rows yet, or marked by team" />
            </div>

            <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
              <ChartCard title="Tables by status" subtitle="Complete vs not complete (team status wins over the automatic one)">
                <SimplePie data={statusPie} valueFormatter={(v) => `${v} table${v === 1 ? "" : "s"}`} />
              </ChartCard>
              <ChartCard title="Records by group" subtitle="Total rows in each group of tables">
                <SimpleBar
                  data={groups.map((g) => ({ name: g.group, Records: g.rows }))}
                  bars={[{ key: "Records", color: SERIES[0] }]}
                  horizontal
                  showValues
                  valueFormatter={fmt}
                  height={Math.max(260, groups.length * 30)}
                  yWidth={150}
                />
              </ChartCard>
            </div>

            <ChartCard
              title="All tables"
              subtitle={`Use the boxes under each heading to filter any column. "Columns filled" is checked on the first ${fmt(data.sample_rows)} rows of each table. ~ = approximate row count (turn on Exact counts for precise numbers).`}
            >
              <DataTable
                columns={columns}
                rows={tables}
                searchable
                searchKeys={["group", "subgroup", "table", "detail", "sheet_detail", "status", "done_by", "sheet_done_by", "team_remarks", "sheet_remarks"]}
                filename="database_tables"
                maxHeight={720}
              />
            </ChartCard>

            {editing && (
              <EditStatusDialog
                row={editing}
                statuses={data.team_statuses || ["Complete", "In progress", "Not started"]}
                onClose={() => setEditing(null)}
                onSaved={onSaved}
              />
            )}
          </>
        );
      }}
    </ReportLayout>
  );
}

export default DatabaseTables;
