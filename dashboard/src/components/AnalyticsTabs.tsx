"use client";

import { useState } from "react";
import RevenueChart from "./charts/RevenueChart";
import PieChartCard from "./charts/PieChartCard";
import CompensationChart from "./charts/CompensationChart";
import CommitteeFeeChart from "./charts/CommitteeFeeChart";
import { formatCurrency } from "@/lib/json-helpers";

interface AnalyticsData {
  revenueData: { name: string; value: number }[];
  profitData: { name: string; value: number }[];
  nationalityData: { name: string; value: number }[];
  genderData: { name: string; value: number }[];
  directorTypeData: { name: string; value: number }[];
  compensationData: {
    name: string;
    retainer_fee: number;
    benefits_in_kind: number;
    attendance_allowance: number;
    expense_allowance: number;
    committee_fee: number;
    variable: number;
    other: number;
  }[];
  committeeFeeData: { name: string; totalFees: number; members: number }[];
  topDirectors: {
    name: string;
    company: string;
    totalFee: number;
    role: string;
  }[];
  stats: {
    totalDirectors: number;
    avgMeetings: number;
    avgCompensation: number;
  };
}

const TABS = [
  "Financial Comparison",
  "Board Composition",
  "Committee Analysis",
  "Compensation",
];

export default function AnalyticsTabs({ data }: { data: AnalyticsData }) {
  const [activeTab, setActiveTab] = useState(0);

  return (
    <div>
      <div className="flex gap-1 mb-6 bg-slate-900 border border-slate-800 rounded-lg p-1 w-fit">
        {TABS.map((tab, i) => (
          <button
            key={tab}
            onClick={() => setActiveTab(i)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === i
                ? "bg-blue-600 text-white"
                : "text-slate-400 hover:text-white hover:bg-slate-800"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {activeTab === 0 && (
        <div className="grid grid-cols-1 gap-6">
          <RevenueChart data={data.revenueData} title="Revenue Comparison (SAR)" />
          <RevenueChart
            data={data.profitData}
            title="Net Profit Comparison (SAR)"
            showNegative
          />
        </div>
      )}

      {activeTab === 1 && (
        <div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 text-center">
              <p className="text-sm text-slate-400">Total Directors</p>
              <p className="text-3xl font-bold text-blue-400">
                {data.stats.totalDirectors}
              </p>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 text-center">
              <p className="text-sm text-slate-400">Avg Meetings Attended</p>
              <p className="text-3xl font-bold text-emerald-400">
                {data.stats.avgMeetings.toFixed(1)}
              </p>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 text-center">
              <p className="text-sm text-slate-400">Avg Compensation</p>
              <p className="text-3xl font-bold text-amber-400">
                {formatCurrency(data.stats.avgCompensation)}
              </p>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <PieChartCard
              data={data.nationalityData}
              title="Nationality Breakdown"
            />
            <PieChartCard
              data={data.genderData}
              title="Gender Diversity"
            />
            <PieChartCard
              data={data.directorTypeData}
              title="Director Types"
            />
          </div>
        </div>
      )}

      {activeTab === 2 && (
        <div className="space-y-6">
          <CommitteeFeeChart data={data.committeeFeeData} />
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-800">
              <h3 className="font-semibold">Committee Membership Summary</h3>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 border-b border-slate-800">
                  <th className="px-5 py-3 font-medium">Committee</th>
                  <th className="px-5 py-3 font-medium text-right">Members</th>
                  <th className="px-5 py-3 font-medium text-right">
                    Total Fees (SAR)
                  </th>
                  <th className="px-5 py-3 font-medium text-right">
                    Avg Fee per Member
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.committeeFeeData.map((c) => (
                  <tr
                    key={c.name}
                    className="border-b border-slate-800/50 hover:bg-slate-800/30"
                  >
                    <td className="px-5 py-3 font-medium">{c.name}</td>
                    <td className="px-5 py-3 text-right font-mono">
                      {c.members}
                    </td>
                    <td className="px-5 py-3 text-right font-mono">
                      {formatCurrency(c.totalFees)}
                    </td>
                    <td className="px-5 py-3 text-right font-mono">
                      {c.members > 0
                        ? formatCurrency(c.totalFees / c.members)
                        : "N/A"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 3 && (
        <div className="space-y-6">
          <CompensationChart data={data.compensationData} />
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-800">
              <h3 className="font-semibold">Top 10 Highest-Paid Directors</h3>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 border-b border-slate-800">
                  <th className="px-5 py-3 font-medium">#</th>
                  <th className="px-5 py-3 font-medium">Director</th>
                  <th className="px-5 py-3 font-medium">Company</th>
                  <th className="px-5 py-3 font-medium">Role</th>
                  <th className="px-5 py-3 font-medium text-right">
                    Total Fee
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.topDirectors.slice(0, 10).map((d, i) => (
                  <tr
                    key={`${d.name}-${d.company}`}
                    className="border-b border-slate-800/50 hover:bg-slate-800/30"
                  >
                    <td className="px-5 py-3 text-slate-500">{i + 1}</td>
                    <td className="px-5 py-3 font-medium">{d.name}</td>
                    <td className="px-5 py-3 text-slate-400">{d.company}</td>
                    <td className="px-5 py-3 text-slate-400">{d.role}</td>
                    <td className="px-5 py-3 text-right font-mono font-semibold">
                      {formatCurrency(d.totalFee)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
