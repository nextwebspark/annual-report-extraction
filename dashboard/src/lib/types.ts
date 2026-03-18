export interface JsonField<T = string> {
  value: T;
  confidence: number;
  source?: string;
}

export interface FinancialField {
  value: number | null;
  currency: string | null;
  confidence: number;
  source?: string;
  unit_stated?: string;
}

export interface Company {
  id: number;
  company_name: JsonField<string>;
  company_code: string;
  exchange: JsonField<string>;
  country: JsonField<string>;
  industry: JsonField<string>;
  created_at: string;
}

export interface CompanyFact {
  id: number;
  company_id: number;
  year: number;
  revenue: FinancialField;
  profit_net: FinancialField;
  market_capitalisation: FinancialField | null;
  employees: JsonField<number | null> | null;
  created_at: string;
}

export interface CompanyWithFacts extends Company {
  fact_id: number | null;
  year: number | null;
  revenue: FinancialField | null;
  profit_net: FinancialField | null;
  market_capitalisation: FinancialField | null;
  employees: JsonField<number | null> | null;
}

export interface Director {
  id: number;
  fact_id: number;
  director_name: string;
  nationality: string;
  gender: string;
  age: number;
  board_role: string;
  director_type: string;
  skills: string;
  board_meetings_attended: number;
  retainer_fee: number;
  benefits_in_kind: number;
  attendance_allowance: number;
  expense_allowance: number;
  director_board_committee_fee: number;
  variable_remuneration: number;
  variable_remuneration_description: string;
  other_remuneration: number;
  other_remuneration_description: string;
  total_fee: number;
}

export interface DirectorWithCompany extends Director {
  company_name: string;
  company_id: number;
  year: number;
}

export interface CommitteeMember {
  id: number;
  fact_id: number;
  member_name: string;
  nationality: string;
  gender: string;
  age: number;
  committee_name: string;
  committee_role: string;
  committee_meetings_attended: number;
  committee_retainer_fee: number;
  committee_allowances: number;
  committee_total_fee: number;
}

export interface CommitteeMemberWithCompany extends CommitteeMember {
  company_name: string;
  company_id: number;
  year: number;
}
