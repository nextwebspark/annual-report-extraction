"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

interface Props {
  data: {
    name: string;
    retainer_fee: number;
    benefits_in_kind: number;
    attendance_allowance: number;
    expense_allowance: number;
    committee_fee: number;
    variable: number;
    other: number;
  }[];
}

const FEE_COMPONENTS = [
  { key: "retainer_fee", label: "Retainer", color: "#3b82f6" },
  { key: "benefits_in_kind", label: "Benefits", color: "#10b981" },
  { key: "attendance_allowance", label: "Attendance", color: "#f59e0b" },
  { key: "expense_allowance", label: "Expense", color: "#f43f5e" },
  { key: "committee_fee", label: "Committee", color: "#8b5cf6" },
  { key: "variable", label: "Variable", color: "#06b6d4" },
  { key: "other", label: "Other", color: "#f97316" },
];

export default function CompensationChart({ data }: Props) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <h3 className="font-semibold mb-4">Compensation Breakdown by Company</h3>
      <ResponsiveContainer width="100%" height={400}>
        <BarChart data={data} margin={{ left: 10, right: 30 }}>
          <XAxis
            dataKey="name"
            tick={{ fill: "#94a3b8", fontSize: 10 }}
            axisLine={{ stroke: "#334155" }}
            tickLine={{ stroke: "#334155" }}
            angle={-20}
            textAnchor="end"
            height={80}
          />
          <YAxis
            tickFormatter={(v) =>
              v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : v.toLocaleString()
            }
            tick={{ fill: "#94a3b8", fontSize: 12 }}
            axisLine={{ stroke: "#334155" }}
            tickLine={{ stroke: "#334155" }}
          />
          <Tooltip
            formatter={(v, name) => [
              `SAR ${Number(v).toLocaleString()}`,
              String(name),
            ]}
            contentStyle={{
              backgroundColor: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "8px",
              color: "#e2e8f0",
            }}
          />
          <Legend wrapperStyle={{ color: "#94a3b8", fontSize: 12 }} />
          {FEE_COMPONENTS.map((fc) => (
            <Bar
              key={fc.key}
              dataKey={fc.key}
              name={fc.label}
              stackId="fees"
              fill={fc.color}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
