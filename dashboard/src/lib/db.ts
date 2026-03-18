import Database from "better-sqlite3";
import { createClient, SupabaseClient } from "@supabase/supabase-js";
import path from "path";
import { parseJsonColumn } from "./json-helpers";
import {
  Company,
  CompanyWithFacts,
  Director,
  DirectorWithCompany,
  CommitteeMember,
  CommitteeMemberWithCompany,
  FinancialField,
  JsonField,
} from "./types";

const JSON_COMPANY_COLS = [
  "company_name",
  "exchange",
  "country",
  "industry",
] as const;
const JSON_FACT_COLS = [
  "revenue",
  "profit_net",
  "market_capitalisation",
  "employees",
] as const;

// --------------- SQLite Data Source ---------------

function getSqliteDb(): Database.Database {
  const dbPath = path.resolve(process.cwd(), "..", "data", "test.db");
  const db = new Database(dbPath, { readonly: true });
  return db;
}

function parseCompanyRow(row: Record<string, unknown>): Record<string, unknown> {
  const parsed = { ...row };
  for (const col of JSON_COMPANY_COLS) {
    parsed[col] = parseJsonColumn<JsonField<string>>(row[col] as string);
  }
  for (const col of JSON_FACT_COLS) {
    if (col in row && row[col] != null) {
      parsed[col] = parseJsonColumn<FinancialField>(row[col] as string);
    }
  }
  return parsed;
}

export function getAllCompaniesWithFacts(): CompanyWithFacts[] {
  if (getDataSource() === "supabase") return supabaseGetAllCompaniesWithFacts();
  const db = getSqliteDb();
  const rows = db.prepare(`
    SELECT c.*, cf.id as fact_id, cf.year, cf.revenue, cf.profit_net,
           cf.market_capitalisation, cf.employees
    FROM companies c
    LEFT JOIN company_facts cf ON c.id = cf.company_id
    ORDER BY c.company_code
  `).all() as Record<string, unknown>[];
  db.close();
  return rows.map((r) => parseCompanyRow(r) as unknown as CompanyWithFacts);
}

export function getCompanyById(id: number): CompanyWithFacts | null {
  if (getDataSource() === "supabase") return supabaseGetCompanyById(id);
  const db = getSqliteDb();
  const row = db.prepare(`
    SELECT c.*, cf.id as fact_id, cf.year, cf.revenue, cf.profit_net,
           cf.market_capitalisation, cf.employees
    FROM companies c
    LEFT JOIN company_facts cf ON c.id = cf.company_id
    WHERE c.id = ?
  `).get(id) as Record<string, unknown> | undefined;
  db.close();
  if (!row) return null;
  return parseCompanyRow(row) as unknown as CompanyWithFacts;
}

export function getDirectorsByFactId(factId: number): Director[] {
  if (getDataSource() === "supabase") return supabaseGetDirectorsByFactId(factId);
  const db = getSqliteDb();
  const rows = db.prepare(`
    SELECT * FROM board_directors WHERE fact_id = ? ORDER BY total_fee DESC
  `).all(factId) as Director[];
  db.close();
  return rows;
}

export function getCommitteesByFactId(factId: number): CommitteeMember[] {
  if (getDataSource() === "supabase") return supabaseGetCommitteesByFactId(factId);
  const db = getSqliteDb();
  const rows = db.prepare(`
    SELECT * FROM board_committees WHERE fact_id = ? ORDER BY committee_name, committee_total_fee DESC
  `).all(factId) as CommitteeMember[];
  db.close();
  return rows;
}

export function getAllDirectors(): DirectorWithCompany[] {
  if (getDataSource() === "supabase") return supabaseGetAllDirectors();
  const db = getSqliteDb();
  const rows = db.prepare(`
    SELECT bd.*, c.company_name, c.id as company_id, cf.year
    FROM board_directors bd
    JOIN company_facts cf ON bd.fact_id = cf.id
    JOIN companies c ON cf.company_id = c.id
    ORDER BY bd.total_fee DESC
  `).all() as Record<string, unknown>[];
  db.close();
  return rows.map((r) => {
    const parsed = { ...r };
    parsed.company_name = parseJsonColumn<JsonField<string>>(r.company_name as string)?.value ?? "";
    return parsed as unknown as DirectorWithCompany;
  });
}

export function getAllCommittees(): CommitteeMemberWithCompany[] {
  if (getDataSource() === "supabase") return supabaseGetAllCommittees();
  const db = getSqliteDb();
  const rows = db.prepare(`
    SELECT bc.*, c.company_name, c.id as company_id, cf.year
    FROM board_committees bc
    JOIN company_facts cf ON bc.fact_id = cf.id
    JOIN companies c ON cf.company_id = c.id
    ORDER BY bc.committee_name, bc.committee_total_fee DESC
  `).all() as Record<string, unknown>[];
  db.close();
  return rows.map((r) => {
    const parsed = { ...r };
    parsed.company_name = parseJsonColumn<JsonField<string>>(r.company_name as string)?.value ?? "";
    return parsed as unknown as CommitteeMemberWithCompany;
  });
}

export function getSummaryStats(): {
  totalCompanies: number;
  totalDirectors: number;
  totalCommittees: number;
  avgConfidence: number;
} {
  if (getDataSource() === "supabase") return supabaseGetSummaryStats();
  const db = getSqliteDb();
  const companies = (db.prepare("SELECT COUNT(*) as c FROM companies").get() as { c: number }).c;
  const directors = (db.prepare("SELECT COUNT(*) as c FROM board_directors").get() as { c: number }).c;
  const committees = (db.prepare("SELECT COUNT(*) as c FROM board_committees").get() as { c: number }).c;

  const revenueRows = db.prepare("SELECT revenue FROM company_facts").all() as { revenue: string }[];
  let totalConf = 0;
  let confCount = 0;
  for (const row of revenueRows) {
    const parsed = parseJsonColumn<FinancialField>(row.revenue);
    if (parsed) {
      totalConf += parsed.confidence;
      confCount++;
    }
  }
  db.close();

  return {
    totalCompanies: companies,
    totalDirectors: directors,
    totalCommittees: committees,
    avgConfidence: confCount > 0 ? totalConf / confCount : 0,
  };
}

// --------------- Supabase Data Source ---------------

function getSupabaseClient(): SupabaseClient {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_ANON_KEY;
  if (!url || !key) {
    throw new Error("SUPABASE_URL and SUPABASE_ANON_KEY must be set when DATA_SOURCE=supabase");
  }
  return createClient(url, key);
}

function supabaseParseCompany(row: Record<string, unknown>): Record<string, unknown> {
  // Supabase returns JSONB as objects already, no parsing needed
  return row;
}

function supabaseGetAllCompaniesWithFacts(): CompanyWithFacts[] {
  // This is synchronous wrapper - for Server Components we need sync access
  // In practice, Supabase calls are async. We use a cache or handle at the page level.
  throw new Error("Use async supabase functions via getDataAsync()");
}

function supabaseGetCompanyById(_id: number): CompanyWithFacts | null {
  throw new Error("Use async supabase functions via getDataAsync()");
}

function supabaseGetDirectorsByFactId(_factId: number): Director[] {
  throw new Error("Use async supabase functions via getDataAsync()");
}

function supabaseGetCommitteesByFactId(_factId: number): CommitteeMember[] {
  throw new Error("Use async supabase functions via getDataAsync()");
}

function supabaseGetAllDirectors(): DirectorWithCompany[] {
  throw new Error("Use async supabase functions via getDataAsync()");
}

function supabaseGetAllCommittees(): CommitteeMemberWithCompany[] {
  throw new Error("Use async supabase functions via getDataAsync()");
}

function supabaseGetSummaryStats(): {
  totalCompanies: number;
  totalDirectors: number;
  totalCommittees: number;
  avgConfidence: number;
} {
  throw new Error("Use async supabase functions via getDataAsync()");
}

// Async Supabase queries for Server Components
export async function getAllCompaniesWithFactsAsync(): Promise<CompanyWithFacts[]> {
  if (getDataSource() !== "supabase") return getAllCompaniesWithFacts();

  const supabase = getSupabaseClient();
  const { data: companies } = await supabase.from("companies").select("*");
  const { data: facts } = await supabase.from("company_facts").select("*");

  if (!companies) return [];
  return companies.map((c) => {
    const fact = facts?.find((f: Record<string, unknown>) => f.company_id === c.id);
    return {
      ...supabaseParseCompany(c),
      fact_id: fact?.id ?? null,
      year: fact?.year ?? null,
      revenue: fact?.revenue ?? null,
      profit_net: fact?.profit_net ?? null,
      market_capitalisation: fact?.market_capitalisation ?? null,
      employees: fact?.employees ?? null,
    } as unknown as CompanyWithFacts;
  });
}

export async function getCompanyByIdAsync(id: number): Promise<CompanyWithFacts | null> {
  if (getDataSource() !== "supabase") return getCompanyById(id);

  const supabase = getSupabaseClient();
  const { data: company } = await supabase.from("companies").select("*").eq("id", id).single();
  if (!company) return null;
  const { data: fact } = await supabase.from("company_facts").select("*").eq("company_id", id).single();

  return {
    ...company,
    fact_id: fact?.id ?? null,
    year: fact?.year ?? null,
    revenue: fact?.revenue ?? null,
    profit_net: fact?.profit_net ?? null,
    market_capitalisation: fact?.market_capitalisation ?? null,
    employees: fact?.employees ?? null,
  } as unknown as CompanyWithFacts;
}

export async function getDirectorsByFactIdAsync(factId: number): Promise<Director[]> {
  if (getDataSource() !== "supabase") return getDirectorsByFactId(factId);

  const supabase = getSupabaseClient();
  const { data } = await supabase
    .from("board_directors")
    .select("*")
    .eq("fact_id", factId)
    .order("total_fee", { ascending: false });
  return (data ?? []) as Director[];
}

export async function getCommitteesByFactIdAsync(factId: number): Promise<CommitteeMember[]> {
  if (getDataSource() !== "supabase") return getCommitteesByFactId(factId);

  const supabase = getSupabaseClient();
  const { data } = await supabase
    .from("board_committees")
    .select("*")
    .eq("fact_id", factId)
    .order("committee_name");
  return (data ?? []) as CommitteeMember[];
}

export async function getAllDirectorsAsync(): Promise<DirectorWithCompany[]> {
  if (getDataSource() !== "supabase") return getAllDirectors();

  const supabase = getSupabaseClient();
  const { data: directors } = await supabase.from("board_directors").select("*").order("total_fee", { ascending: false });
  const { data: facts } = await supabase.from("company_facts").select("id, company_id, year");
  const { data: companies } = await supabase.from("companies").select("id, company_name");

  if (!directors) return [];
  return directors.map((d) => {
    const fact = facts?.find((f: Record<string, unknown>) => f.id === d.fact_id);
    const company = companies?.find((c: Record<string, unknown>) => c.id === fact?.company_id);
    const name = company?.company_name;
    return {
      ...d,
      company_name: typeof name === "object" && name ? (name as JsonField<string>).value : name ?? "",
      company_id: fact?.company_id ?? 0,
      year: fact?.year ?? 0,
    } as DirectorWithCompany;
  });
}

export async function getAllCommitteesAsync(): Promise<CommitteeMemberWithCompany[]> {
  if (getDataSource() !== "supabase") return getAllCommittees();

  const supabase = getSupabaseClient();
  const { data: committees } = await supabase.from("board_committees").select("*").order("committee_name");
  const { data: facts } = await supabase.from("company_facts").select("id, company_id, year");
  const { data: companies } = await supabase.from("companies").select("id, company_name");

  if (!committees) return [];
  return committees.map((cm) => {
    const fact = facts?.find((f: Record<string, unknown>) => f.id === cm.fact_id);
    const company = companies?.find((c: Record<string, unknown>) => c.id === fact?.company_id);
    const name = company?.company_name;
    return {
      ...cm,
      company_name: typeof name === "object" && name ? (name as JsonField<string>).value : name ?? "",
      company_id: fact?.company_id ?? 0,
      year: fact?.year ?? 0,
    } as CommitteeMemberWithCompany;
  });
}

export async function getSummaryStatsAsync(): Promise<{
  totalCompanies: number;
  totalDirectors: number;
  totalCommittees: number;
  avgConfidence: number;
}> {
  if (getDataSource() !== "supabase") return getSummaryStats();

  const supabase = getSupabaseClient();
  const [{ count: c1 }, { count: c2 }, { count: c3 }] = await Promise.all([
    supabase.from("companies").select("*", { count: "exact", head: true }),
    supabase.from("board_directors").select("*", { count: "exact", head: true }),
    supabase.from("board_committees").select("*", { count: "exact", head: true }),
  ]);

  const { data: facts } = await supabase.from("company_facts").select("revenue");
  let totalConf = 0;
  let confCount = 0;
  for (const row of facts ?? []) {
    const rev = row.revenue as FinancialField | null;
    if (rev) {
      totalConf += rev.confidence;
      confCount++;
    }
  }

  return {
    totalCompanies: c1 ?? 0,
    totalDirectors: c2 ?? 0,
    totalCommittees: c3 ?? 0,
    avgConfidence: confCount > 0 ? totalConf / confCount : 0,
  };
}

// --------------- Data Source Switch ---------------

export function getDataSource(): "sqlite" | "supabase" {
  return process.env.DATA_SOURCE === "supabase" ? "supabase" : "sqlite";
}
