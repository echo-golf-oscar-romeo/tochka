"use client";

/**
 * Inline chart for chat result rows.
 *
 * Detects two patterns that come back from spatial SQL frequently:
 *   1. (label_string, value_number) — render a horizontal bar.
 *   2. (x_number, y_number)         — render a scatter.
 *
 * Anything else is skipped; the SQL + table fallback below handles those.
 */

import type { ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Row = Record<string, unknown>;

interface Props {
  rows: Row[];
  columns: string[];
}

const ACCENT_500 = "#4657fa";
const ACCENT_200 = "#b9c2ff";
const INK = "#0b1020";
const MUTED = "#5c6470";

const COORD_COL_NAMES = new Set([
  "lat", "latitude", "y", "lng", "lon", "long", "longitude", "x",
  "Lat", "Latitude", "Lng", "Lon", "Longitude",
]);


export default function ChatChart({ rows, columns }: Props): ReactNode {
  if (!rows || rows.length < 2) return null;
  const cols = columns ?? Object.keys(rows[0] ?? {});

  // Drop coordinate columns from chart consideration — the chat map already
  // shows them and they'd dominate any numeric chart.
  const chartCols = cols.filter((c) => !COORD_COL_NAMES.has(c));
  if (chartCols.length < 2) return null;

  const types = chartCols.map((c) => columnType(rows, c));
  const stringCols = chartCols.filter((c, i) => types[i] === "string");
  const numberCols = chartCols.filter((c, i) => types[i] === "number");

  // Bar: 1 string label + 1 numeric value
  if (stringCols.length >= 1 && numberCols.length >= 1) {
    const labelCol = stringCols[0];
    const valueCol = numberCols[0];
    const data = rows.slice(0, 25).map((r) => ({
      label: truncate(String(r[labelCol] ?? ""), 28),
      value: Number(r[valueCol]) || 0,
    }));
    const sorted = [...data].sort((a, b) => b.value - a.value);
    return (
      <div className="mt-1 border border-border rounded bg-canvas p-2">
        <div className="text-[10px] uppercase tracking-wider text-muted mb-1 px-1">
          {labelCol} × {valueCol}
        </div>
        <ResponsiveContainer width="100%" height={Math.min(40 + sorted.length * 22, 360)}>
          <BarChart data={sorted} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
            <CartesianGrid horizontal={false} stroke="#f1f5f9" />
            <XAxis type="number" tick={{ fill: MUTED, fontSize: 10 }} stroke="#e7eaee" />
            <YAxis
              dataKey="label"
              type="category"
              tick={{ fill: INK, fontSize: 10 }}
              stroke="#e7eaee"
              width={110}
              interval={0}
            />
            <Tooltip
              contentStyle={{ borderRadius: 6, borderColor: "#e7eaee", fontSize: 11 }}
              labelStyle={{ color: INK, fontWeight: 600 }}
            />
            <Bar dataKey="value" radius={[0, 3, 3, 0]} barSize={14}>
              {sorted.map((_, i) => (
                <Cell key={i} fill={i === 0 ? ACCENT_500 : ACCENT_200} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // Scatter: 2 numeric columns
  if (numberCols.length >= 2) {
    const xCol = numberCols[0];
    const yCol = numberCols[1];
    const data = rows.slice(0, 200).map((r) => ({
      x: Number(r[xCol]) || 0,
      y: Number(r[yCol]) || 0,
    }));
    return (
      <div className="mt-1 border border-border rounded bg-canvas p-2">
        <div className="text-[10px] uppercase tracking-wider text-muted mb-1 px-1">
          {xCol} × {yCol}
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <ScatterChart margin={{ left: 8, right: 16, top: 8, bottom: 4 }}>
            <CartesianGrid stroke="#f1f5f9" />
            <XAxis
              dataKey="x"
              type="number"
              name={xCol}
              tick={{ fill: MUTED, fontSize: 10 }}
              stroke="#e7eaee"
            />
            <YAxis
              dataKey="y"
              type="number"
              name={yCol}
              tick={{ fill: MUTED, fontSize: 10 }}
              stroke="#e7eaee"
            />
            <Tooltip
              cursor={{ stroke: "#b9c2ff", strokeDasharray: "3 3" }}
              contentStyle={{ borderRadius: 6, borderColor: "#e7eaee", fontSize: 11 }}
            />
            <Scatter data={data} fill={ACCENT_500} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return null;
}


function columnType(rows: Row[], col: string): "number" | "string" | "mixed" {
  let numCount = 0;
  let strCount = 0;
  for (const r of rows.slice(0, 20)) {
    const v = r[col];
    if (v === null || v === undefined) continue;
    if (typeof v === "number" || (!Number.isNaN(parseFloat(String(v))) && String(v).match(/^-?\d/))) numCount++;
    else strCount++;
  }
  if (numCount && !strCount) return "number";
  if (strCount && !numCount) return "string";
  return "mixed";
}


function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
}
