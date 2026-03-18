"""Canonical LLM response fixtures used across unit tests.

All fields match the exact structure expected by extraction scripts and
are compatible with the SQLite DB schema.
"""

COMPANY_LLM_RESPONSE = {
    "company": {
        "company_name": {"value": "Acme Corp", "confidence": 0.99, "source": "cover page"},
        "exchange": {"value": "NYSE", "confidence": 0.99, "source": "cover page"},
        "country": {"value": "United States", "confidence": 0.99, "source": "cover page"},
        "industry": {"value": "Technology", "confidence": 0.99, "source": "cover page"},
        "source_document_url": "https://example.com/annual-report.pdf",
    },
    "financials": {
        "year": 2023,
        "revenue": {
            "value": 5000000,
            "currency": "USD",
            "confidence": 0.95,
            "source": "income statement",
            "unit_stated": "actual",
        },
        "profit_net": {
            "value": 1000000,
            "currency": "USD",
            "confidence": 0.95,
            "source": "income statement",
            "unit_stated": "actual",
        },
        "market_capitalisation": {
            "value": 50000000,
            "currency": "USD",
            "confidence": 0.9,
            "source": "cover page",
            "unit_stated": "actual",
        },
        "employees": {
            "value": 5000,
            "confidence": 0.9,
            "source": "annual report",
        },
    },
}

# Second company response — same company, different revenue (for upsert update tests)
COMPANY_LLM_RESPONSE_V2 = {
    **COMPANY_LLM_RESPONSE,
    "financials": {
        **COMPANY_LLM_RESPONSE["financials"],
        "revenue": {
            "value": 6000000,
            "currency": "USD",
            "confidence": 0.95,
            "source": "income statement",
            "unit_stated": "actual",
        },
    },
}

DIRECTORS_LLM_RESPONSE = [
    {
        "director_name": "Alice Smith",
        "nationality": "British",
        "ethnicity": "White",
        "local_expat": "expat",
        "gender": "Female",
        "age": 55,
        "board_role": "Chairman",
        "director_type": "Non-Executive",
        "skills": "Finance, Strategy",
        "board_meetings_attended": 6,
        "retainer_fee": 200000,
        "benefits_in_kind": 0,
        "attendance_allowance": 0,
        "expense_allowance": 0,
        "assembly_fee": 0,
        "director_board_committee_fee": 0,
        "variable_remuneration": 0,
        "variable_remuneration_description": "",
        "other_remuneration": 0,
        "other_remuneration_description": "",
        "total_fee": 200000,
    },
    {
        "director_name": "Bob Jones",
        "nationality": "Canadian",
        "ethnicity": "White",
        "local_expat": "expat",
        "gender": "Male",
        "age": 48,
        "board_role": "Member",
        "director_type": "Independent",
        "skills": "Audit, Risk",
        "board_meetings_attended": 5,
        "retainer_fee": 100000,
        "benefits_in_kind": 0,
        "attendance_allowance": 5000,
        "expense_allowance": 0,
        "assembly_fee": 0,
        "director_board_committee_fee": 0,
        "variable_remuneration": 0,
        "variable_remuneration_description": "",
        "other_remuneration": 0,
        "other_remuneration_description": "",
        "total_fee": 105000,
    },
]

COMMITTEES_LLM_RESPONSE = [
    {
        "member_name": "Alice Smith",
        "committee_name": "Audit Committee",
        "committee_role": "Chairman",
        "nationality": "British",
        "ethnicity": "White",
        "local_expat": "expat",
        "gender": "Female",
        "age": 55,
        "committee_meetings_attended": 4,
        "committee_retainer_fee": 50000,
        "committee_allowances": 0,
        "committee_total_fee": 50000,
    },
    {
        "member_name": "Bob Jones",
        "committee_name": "Audit Committee",
        "committee_role": "Member",
        "nationality": "Canadian",
        "ethnicity": "White",
        "local_expat": "expat",
        "gender": "Male",
        "age": 48,
        "committee_meetings_attended": 4,
        "committee_retainer_fee": 30000,
        "committee_allowances": 0,
        "committee_total_fee": 30000,
    },
]
