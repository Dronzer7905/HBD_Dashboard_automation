import { useState, useEffect, useCallback } from "react";

const SCRAPERS = [
  { id: "news", name: "Local News", schedule: "Every 45 min", queue: "fast_news", task: "BG-1.3" },
  { id: "quick-commerce", name: "Zepto / Blinkit", schedule: "Daily 2 AM", queue: "quick_commerce", task: "BG-1.5" },
  { id: "zomato", name: "Zomato Menus", schedule: "Tue/Thu 3 AM", queue: "quick_commerce", task: "BG-1.6" },
  { id: "gdrive", name: "GDrive / S3 Sync", schedule: "Sunday 1 AM", queue: "heavy_ingestion", task: "BG-1.7" },
];

export default function ScraperScheduler() {
  const [scrapers, setScrapers] = useState(
    SCRAPERS.map((s) => ({ ...s, status: "scheduled", lastRun: "—" }))
  );
  const [apiOnline, setApiOnline] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/schedulers/status");
      if (res.ok) {
        const data = await res.json();
        setApiOnline(true);
        // Merge live data with defaults
      }
    } catch {
      setApiOnline(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  return (
    <main className="min-h-screen bg-blue-gray-50/50 p-4 md:p-6">
      <header className="mb-8">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-blue-600">
          Guided Data Ingestion
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-blue-gray-900">
          Scraper Scheduler & Monitor
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-blue-gray-600">
          Monitor and manually trigger background scraping workers.
          {!apiOnline && (
            <span className="ml-2 text-amber-600 font-medium">
              (Waiting for BG-1.13 scheduler APIs)
            </span>
          )}
        </p>
      </header>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        {scrapers.map((s) => (
          <article
            key={s.id}
            className="rounded-xl border border-blue-gray-100 bg-white p-5 shadow-sm"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-blue-gray-900">{s.name}</h3>
              <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-700">
                {s.status}
              </span>
            </div>

            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-blue-gray-500">Schedule</span>
                <span className="font-medium text-blue-gray-800">{s.schedule}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-blue-gray-500">Queue</span>
                <span className="font-mono text-xs text-blue-gray-600">{s.queue}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-blue-gray-500">Last Run</span>
                <span className="text-blue-gray-700">{s.lastRun}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-blue-gray-500">Backend Task</span>
                <span className="font-mono text-xs text-blue-500">{s.task}</span>
              </div>
            </div>

            <div className="mt-4 flex gap-2">
              <button
                className="flex-1 rounded-lg border border-blue-gray-200 py-1.5 text-xs font-medium text-blue-gray-700 hover:bg-blue-gray-50 disabled:opacity-40"
                disabled={!apiOnline}
                title="Requires BG-1.13 API"
              >
                Trigger Now
              </button>
              <button
                className="flex-1 rounded-lg border border-blue-gray-200 py-1.5 text-xs font-medium text-blue-gray-700 hover:bg-blue-gray-50 disabled:opacity-40"
                disabled={!apiOnline}
                title="Requires BG-1.13 API"
              >
                Pause
              </button>
            </div>
          </article>
        ))}
      </div>
    </main>
  );
}
