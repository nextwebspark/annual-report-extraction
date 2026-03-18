"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

const COLORS = [
  "#3b82f6", "#10b981", "#f59e0b", "#f43f5e",
  "#8b5cf6", "#06b6d4", "#f97316", "#6366f1",
];

interface Props {
  data: { name: string; value: number }[];
  title: string;
  showNegative?: boolean;
}

export default function RevenueChart({ data, title, showNegative }: Props) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <h3 className="font-semibold mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={350}>
        <BarChart data={data} layout="vertical" margin={{ left: 10, right: 30 }}>
          <XAxis
            type="number"
            tickFormatter={(v) => {
              const abs = Math.abs(v);
              if (abs >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
              if (abs >= 1e6) return `${(v / 1e6).toFixed(0)}M`;
              return v.toLocaleString();
            }}
            tick={{ fill: "#94a3b8", fontSize: 12 }}
            axisLine={{ stroke: "#334155" }}
            tickLine={{ stroke: "#334155" }}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={180}
            tick={{ fill: "#cbd5e1", fontSize: 11 }}
            axisLine={{ stroke: "#334155" }}
            tickLine={false}
          />
          <Tooltip
            formatter={(v) => [
              `SAR ${Number(v).toLocaleString()}`,
              "Amount",
            ]}
            contentStyle={{
              backgroundColor: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "8px",
              color: "#e2e8f0",
            }}
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {data.map((_, i) => (
              <Cell
                key={i}
                fill={
                  showNegative && data[i].value < 0
                    ? "#f43f5e"
                    : COLORS[i % COLORS.length]
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
