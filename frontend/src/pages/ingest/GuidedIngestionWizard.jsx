import { useState, useCallback } from "react";

const STEPS = ["Upload File", "Map Columns", "Validate", "Ingest", "Receipt"];

export default function GuidedIngestionWizard() {
  const [step, setStep] = useState(0);
  const [file, setFile] = useState(null);

  return (
    <main className="min-h-screen bg-blue-gray-50/50 p-4 md:p-6">
      <header className="mb-8">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-blue-600">
          Guided Data Ingestion
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-blue-gray-900">
          Bulk Upload Wizard
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-blue-gray-600">
          Safely upload external datasets (CSV, XLSX, TSV) into the staging pipeline.
        </p>
      </header>

      {/* Step Indicator */}
      <div className="mb-8 flex items-center justify-center gap-2">
        {STEPS.map((name, idx) => (
          <div key={name} className="flex items-center gap-2">
            <div
              className={`flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold transition-colors ${
                idx === step
                  ? "bg-blue-600 text-white"
                  : idx < step
                  ? "bg-green-500 text-white"
                  : "bg-blue-gray-100 text-blue-gray-500"
              }`}
            >
              {idx < step ? "✓" : idx + 1}
            </div>
            <span
              className={`hidden text-sm font-medium sm:block ${
                idx === step ? "text-blue-gray-900" : "text-blue-gray-400"
              }`}
            >
              {name}
            </span>
            {idx < STEPS.length - 1 && (
              <div className="hidden h-px w-8 bg-blue-gray-200 sm:block" />
            )}
          </div>
        ))}
      </div>

      {/* Step Content */}
      <div className="mx-auto max-w-3xl rounded-xl border border-blue-gray-100 bg-white p-8 shadow-sm">
        {step === 0 && (
          <div className="text-center">
            <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-2xl border-2 border-dashed border-blue-gray-200 bg-blue-gray-50">
              <svg className="h-10 w-10 text-blue-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            <p className="mt-4 text-lg font-semibold text-blue-gray-800">
              Drag & drop your file here
            </p>
            <p className="mt-1 text-sm text-blue-gray-500">
              Accepts .csv, .xlsx, .tsv up to 1GB
            </p>
            <input
              type="file"
              accept=".csv,.xlsx,.tsv"
              className="mt-4 text-sm"
              onChange={(e) => {
                setFile(e.target.files[0]);
              }}
            />
            <div className="mt-6">
              <button
                disabled={!file}
                onClick={() => setStep(1)}
                className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:opacity-40"
              >
                Continue to Column Mapping →
              </button>
            </div>
            <p className="mt-4 text-xs text-amber-600 font-medium">
              Requires backend API (BG-1.8 / BG-1.9) — full upload flow pending Bhargav's ingestion routes
            </p>
          </div>
        )}

        {step > 0 && (
          <div className="text-center py-12">
            <p className="text-lg font-semibold text-blue-gray-700">
              Step {step + 1}: {STEPS[step]}
            </p>
            <p className="mt-2 text-sm text-blue-gray-500">
              This step requires Bhargav's backend APIs (BG-1.8 to BG-1.10) to be deployed.
            </p>
            <div className="mt-6 flex justify-center gap-3">
              <button
                onClick={() => setStep(step - 1)}
                className="rounded-lg border border-blue-gray-200 px-5 py-2 text-sm font-medium text-blue-gray-700 hover:bg-blue-gray-50"
              >
                ← Back
              </button>
              {step < STEPS.length - 1 && (
                <button
                  onClick={() => setStep(step + 1)}
                  className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700"
                >
                  Next →
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
