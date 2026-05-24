"use client";

import { useState } from "react";
import { uploadCsv, type UploadResponse } from "@/lib/api";

interface Props {
  onUploaded: (network: UploadResponse) => void;
  onClose: () => void;
}

export default function UploadDialog({ onUploaded, onClose }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  async function handle(file: File) {
    setBusy(true);
    setError(null);
    try {
      const net = await uploadCsv(file);
      onUploaded(net);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-ink/30 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-canvas rounded-lg shadow-soft w-[30rem] max-w-[92vw] p-6 border border-border"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-3">
          <div>
            <h2 className="text-lg font-semibold">Upload your network</h2>
            <p className="text-xs text-muted mt-1 leading-relaxed">
              CSV with <code className="text-ink">name</code> + <code className="text-ink">(lat,lng)</code> or <code className="text-ink">address</code>.
              Optional: <code className="text-ink">capacity</code>, <code className="text-ink">actual_volume</code>{" "}
              (aliases: <code className="text-ink">visitors</code>, <code className="text-ink">traffic</code>, <code className="text-ink">utilization</code>).
            </p>
          </div>
          <button onClick={onClose} className="text-muted hover:text-ink px-2" aria-label="Close">
            ✕
          </button>
        </div>

        <div
          className={`border-2 border-dashed rounded p-8 text-center transition ${
            dragging ? "border-accent-500 bg-accent-50" : "border-border"
          }`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const f = e.dataTransfer.files?.[0];
            if (f) handle(f);
          }}
        >
          {busy ? (
            <p className="text-muted text-sm">Uploading…</p>
          ) : (
            <>
              <p className="text-sm mb-3 text-ink">Drop a CSV here</p>
              <label className="inline-block cursor-pointer rounded bg-accent-500 hover:bg-accent-600 text-white px-4 py-2 text-sm">
                Choose file
                <input
                  type="file"
                  accept=".csv,.tsv"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handle(f);
                  }}
                />
              </label>
            </>
          )}
        </div>

        {error && <p className="mt-3 text-xs text-accent-700">{error}</p>}
      </div>
    </div>
  );
}
