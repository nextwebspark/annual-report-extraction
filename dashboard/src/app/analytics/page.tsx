import {
  getAllCompaniesWithFactsAsync,
  getAllDirectorsAsync,
  getAllCommitteesAsync,
} from "@/lib/db";
import { getNormalizedRevenue } from "@/lib/json-helpers";
import AnalyticsTabs from "@/components/AnalyticsTabs";

export const dynamic = "force-dynamic";

function countBy<T>(items: T[], key: (item: T) => string): { name: string; value: number }[] {
  const counts: Record<string, number> = {};
  for (const item of items) {
    const k = key(item) || "Unknown";
    counts[k] = (counts[k] || 0) + 1;
  }
  return Object.entries(counts)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);
}

export default async function AnalyticsPage() {
  const [companies, directors, committees] = await Promise.all([
    getAllCompaniesWithFactsAsync(),
    getAllDirectorsAsync(),
    getAllCommitteesAsync(),
  ]);

  // Financial comparison data
  const revenueData = companies
    .map((c) => ({
      name: c.company_name?.value?.replace(/\s+Company.*$/, "").substring(0, 30) ?? "Unknown",
      value: getNormalizedRevenue(c.revenue) ?? 0,
    }))
    .filter((d) => d.value > 0)
    .sort((a, b) => b.value - a.value);

  const profitData = companies
    .map((c) => ({
      name: c.company_name?.value?.replace(/\s+Company.*$/, "").substring(0, 30) ?? "Unknown",
      value: getNormalizedRevenue(c.profit_net) ?? 0,
    }))
    .sort((a, b) => b.value - a.value);

  // Board composition
  const nationalityData = countBy(directors, (d) => d.nationality);
  const genderData = countBy(directors, (d) => d.gender);
  const directorTypeData = countBy(directors, (d) => d.director_type);

  // Committee analysis
  const committeeAgg: Record<string, { totalFees: number; members: number }> = {};
  for (const cm of committees) {
    const name = cm.committee_name || "Other";
    if (!committeeAgg[name]) committeeAgg[name] = { totalFees: 0, members: 0 };
    committeeAgg[name].totalFees += cm.committee_total_fee || 0;
    committeeAgg[name].members += 1;
  }
  const committeeFeeData = Object.entries(committeeAgg)
    .map(([name, v]) => ({ name, ...v }))
    .sort((a, b) => b.totalFees - a.totalFees);

  // Compensation breakdown by company
  const compByCompany: Record<
    string,
    {
      retainer_fee: number;
      benefits_in_kind: number;
      attendance_allowance: number;
      expense_allowance: number;
      committee_fee: number;
      variable: number;
      other: number;
    }
  > = {};

  for (const d of directors) {
    const name = (d.company_name ?? "Unknown").substring(0, 25);
    if (!compByCompany[name]) {
      compByCompany[name] = {
        retainer_fee: 0,
        benefits_in_kind: 0,
        attendance_allowance: 0,
        expense_allowance: 0,
        committee_fee: 0,
        variable: 0,
        other: 0,
      };
    }
    const c = compByCompany[name];
    c.retainer_fee += d.retainer_fee || 0;
    c.benefits_in_kind += d.benefits_in_kind || 0;
    c.attendance_allowance += d.attendance_allowance || 0;
    c.expense_allowance += d.expense_allowance || 0;
    c.committee_fee += d.director_board_committee_fee || 0;
    c.variable += d.variable_remuneration || 0;
    c.other += d.other_remuneration || 0;
  }
  const compensationData = Object.entries(compByCompany).map(([name, fees]) => ({
    name,
    ...fees,
  }));

  // Top directors
  const topDirectors = directors.slice(0, 10).map((d) => ({
    name: d.director_name,
    company: (d.company_name ?? "Unknown").substring(0, 30),
    totalFee: d.total_fee,
    role: d.board_role,
  }));

  // Stats
  const totalMeetings = directors.reduce(
    (s, d) => s + (d.board_meetings_attended || 0),
    0
  );
  const totalComp = directors.reduce((s, d) => s + (d.total_fee || 0), 0);
  const stats = {
    totalDirectors: directors.length,
    avgMeetings: directors.length > 0 ? totalMeetings / directors.length : 0,
    avgCompensation: directors.length > 0 ? totalComp / directors.length : 0,
  };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Analytics</h1>
      <AnalyticsTabs
        data={{
          revenueData,
          profitData,
          nationalityData,
          genderData,
          directorTypeData,
          compensationData,
          committeeFeeData,
          topDirectors,
          stats,
        }}
      />
    </div>
  );
}
