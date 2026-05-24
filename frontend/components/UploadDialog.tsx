"use client";

import { useState } from "react";
import { uploadCsv } from "@/lib/api";

interface Props {
  onUploaded: (networkId: string) => void;
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
      onUploaded(net.id);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-xl w-[28rem] max-w-[90vw] p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-3">
          <div>
            <h2 className="font-serif text-xl">Upload your network</h2>
            <p className="text-xs text-muted mt-1">
              CSV with <code>name</code> + <code>lat,lng</code> or <code>address</code>.
              Optional: <code>capacity</code>, <code>actual_volume</code> (alias: <code>visitors</code>, <code>traffic</code>).
            </p>
          </div>
          <button onClick={onClose} className="text-muted hover:text-ink px-2">✕</button>
        </div>

        <div
          className={`border-2 border-dashed rounded p-8 text-center transition ${
            dragging ? "border-accent bg-accent/5" : "border-muted/30"
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
              <p className="text-sm mb-3">Drop a CSV here</p>
              <label className="inline-block cursor-pointer rounded bg-accent text-white px-4 py-2 text-sm">
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

        {error && <p className="mt-3 text-xs text-warn">{error}</p>}
      </div>
    </div>
  );
}
