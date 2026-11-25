import { useState, useEffect, useCallback } from "react";
import { Typography } from "@material-tailwind/react";

const FALLBACK_KPIS = [
  { label: "Total Staged Businesses", value: "8.5M", accent: "border-blue-500" },
  { label: "Tier 1 Clean", value: "405k", accent: "border-emerald-500" },
  { label: "Geo-Mapped", value: "382k", accent: "border-violet-500" },
  { label: "Live Production Ready", value: "65k", accent: "border-amber-500" },
];

const SCRAPER_FLEET = [
  { name: "News", schedule: "Every 45 minutes" },
  { name: "Zepto / Blinkit", schedule: "Daily 2 AM" },
  { name: "Zomato Menus", schedule: "Tue / Thu, 3 AM" },
  { name: "GDrive Sync", schedule: "Sunday, 1 AM" },
];

export default function CommandCenter() {
  const [kpis, setKpis] = useState(FALLBACK_KPIS);
  const [apiOnline, setApiOnline] = useState(false);

  const fetchPipelineStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/pipeline-status");
      if (res.ok) {
        const data = await res.json();
        setApiOnline(true);
        if (data && data.stages) {
          setKpis([
            { label: "Total Staged Businesses", value: (data.stages.raw_ingest ?? "8.5M").toLocaleString(), accent: "border-blue-500" },
            { label: "Tier 1 Clean", value: (data.stages.tier1_clean ?? "405k").toLocaleString(), accent: "border-emerald-500" },
            { label: "Geo-Mapped", value: (data.stages.geo_mapped ?? "382k").toLocaleString(), accent: "border-violet-500" },
            { label: "Live Production Ready", value: (data.stages.live_ready ?? "65k").toLocaleString(), accent: "border-amber-500" },
          ]);
        }
      }
    } catch {
      setApiOnline(false);
    }
  }, []);

  useEffect(() => {
    fetchPipelineStatus();
    const interval = setInterval(fetchPipelineStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchPipelineStatus]);

  return (
    <main className="min-h-screen bg-blue-gray-50/50 p-4 md:p-6">
      <header className="mb-8">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-blue-600">
          Executive Overview
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-blue-gray-900">
          Manager Command Center
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-blue-gray-600">
          Consolidated view of data readiness, platform health, and scheduled
          scraper activity.
          {!apiOnline && (
            <span className="ml-2 text-amber-600 font-medium">
              (Showing reference values — backend API not connected yet)
            </span>
          )}
        </p>
      </header>

      {/* KPI Row */}
      <section className="mb-8">
        <h2 className="mb-4 text-sm font-bold uppercase tracking-wider text-blue-gray-500">
          Pipeline KPIs
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {kpis.map((kpi) => (
            <article
              key={kpi.label}
              className={`rounded-xl border border-blue-gray-100 border-l-4 ${kpi.accent} bg-white p-5 shadow-sm`}
            >
              <p className="text-sm font-medium text-blue-gray-600">{kpi.label}</p>
              <p className="mt-3 text-3xl font-bold tabular-nums text-blue-gray-900">
                {kpi.value}
              </p>
            </article>
          ))}
        </div>
      </section>

      {/* System Health */}
      <section className="mb-8">
        <h2 className="mb-4 text-sm font-bold uppercase tracking-wider text-blue-gray-500">
          System Health
        </h2>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {[
            { name: "PostgreSQL Pool", detail: "Active / max connections" },
            { name: "Celery Workers", detail: "Heartbeat status" },
            { name: "Redis Cache", detail: "Cache hit rate" },
          ].map((sys) => (
            <article
              key={sys.name}
              className="rounded-xl border border-blue-gray-100 bg-white p-5 shadow-sm"
            >
              <div className="flex items-start justify-between">
                <h3 className="font-semibold text-blue-gray-900">{sys.name}</h3>
                <span className="rounded-full bg-blue-gray-50 px-2.5 py-1 text-xs font-semibold text-blue-gray-600">
                  Pending API
                </span>
              </div>
              <p className="mt-4 text-2xl font-bold text-blue-gray-800">—</p>
              <p className="mt-1 text-sm text-blue-gray-500">{sys.detail}</p>
            </article>
          ))}
        </div>
      </section>

      {/* Scraper Fleet */}
      <section>
        <h2 className="mb-4 text-sm font-bold uppercase tracking-wider text-blue-gray-500">
          Scraper Fleet Schedule
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {SCRAPER_FLEET.map((s) => (
            <article
              key={s.name}
              className="rounded-xl border border-blue-gray-100 bg-white p-5 shadow-sm"
            >
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-blue-gray-900">{s.name}</h3>
                <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700">
                  Scheduled
                </span>
              </div>
              <p className="mt-4 text-xs font-bold uppercase tracking-wider text-blue-gray-500">
                Schedule
              </p>
              <p className="mt-1 text-sm font-medium text-blue-gray-800">
                {s.schedule}
              </p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
