"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { uploadCsv } from "@/lib/api";

export default function Upload() {
  const router = useRouter();
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setBusy(true);
    setError(null);
    try {
      const network = await uploadCsv(file);
      router.push(`/analyze?network=${network.id}`);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className={`border-2 border-dashed rounded-lg p-12 text-center transition ${
        dragging ? "border-accent bg-accent/5" : "border-muted/40"
      }`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        const f = e.dataTransfer.files?.[0];
        if (f) handleFile(f);
      }}
    >
      {busy ? (
        <p className="text-muted">Uploading…</p>
      ) : (
        <>
          <p className="text-lg mb-3">Drop a CSV here</p>
          <p className="text-sm text-muted mb-6">
            Required columns: <code>name</code> and either <code>lat,lng</code> or <code>address</code>.
          </p>
          <label className="inline-block cursor-pointer rounded bg-accent text-white px-4 py-2 text-sm">
            Choose file
            <input
              type="file"
              accept=".csv,.tsv"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFile(f);
              }}
            />
          </label>
        </>
      )}
      {error && <p className="mt-4 text-sm text-warn">{error}</p>}
    </div>
  );
}
