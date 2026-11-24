import { useState, useEffect, useCallback } from "react";

const STAGES = [
  { name: "Raw Ingest", key: "raw_ingest", fallback: 8500000, color: "bg-blue-500" },
  { name: "Quality Tiering", key: "tier1_clean", fallback: 405000, color: "bg-indigo-500" },
  { name: "Hyperlocal Geo-Mapped", key: "geo_mapped", fallback: 382000, color: "bg-purple-500" },
  { name: "Catalog & Archetype Mapped", key: "catalog_mapped", fallback: 120000, color: "bg-amber-500" },
  { name: "CityHangaround Live Ready", key: "live_ready", fallback: 65000, color: "bg-green-500" },
];

function fmt(n) {
  if (typeof n === "number") {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(0) + "k";
    return n.toLocaleString();
  }
  return String(n);
}

export default function PipelineStatus() {
  const [stages, setStages] = useState(STAGES.map((s) => ({ ...s, value: s.fallback })));
  const [apiOnline, setApiOnline] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/pipeline-status");
      if (res.ok) {
        const data = await res.json();
        setApiOnline(true);
        if (data && data.stages) {
          setStages(STAGES.map((s) => ({ ...s, value: data.stages[s.key] ?? s.fallback })));
        }
      }
    } catch {
      setApiOnline(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 15000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const maxValue = Math.max(...stages.map((s) => s.value));

  return (
    <main className="min-h-screen bg-blue-gray-50/50 p-4 md:p-6">
      <header className="mb-8">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-blue-600">
          HBD ETL & Pipeline
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-blue-gray-900">
          Pipeline Completion Status
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-blue-gray-600">
          Visual 5-stage funnel showing the lifecycle of city data.
          {!apiOnline && (
            <span className="ml-2 text-amber-600 font-medium">
              (Reference values — waiting for BG-1.13 API)
            </span>
          )}
        </p>
      </header>

      <div className="max-w-4xl space-y-4">
        {stages.map((stage, idx) => {
          const pct = maxValue > 0 ? Math.max(5, (stage.value / maxValue) * 100) : 5;
          return (
            <div key={stage.key} className="rounded-xl border border-blue-gray-100 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-gray-100 text-sm font-bold text-blue-gray-700">
                    {idx + 1}
                  </span>
                  <h3 className="font-semibold text-blue-gray-900">{stage.name}</h3>
                </div>
                <span className="text-lg font-bold tabular-nums text-blue-gray-900">
                  {fmt(stage.value)}
                </span>
              </div>
              <div className="h-4 w-full overflow-hidden rounded-full bg-blue-gray-50">
                <div
                  className={`h-full rounded-full ${stage.color} transition-all duration-700`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </main>
  );
}
