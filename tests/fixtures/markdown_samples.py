"""Short inline markdown samples for use in tests.

These are intentionally minimal — they only need to be passable strings
to the extraction functions (which mock the LLM call anyway).
"""

SAMPLE_MARKDOWN = """
# Acme Corp Annual Report 2023

## Company Overview
Acme Corp (NYSE: ACME) is a technology company headquartered in the United States.

## Financial Highlights
- Revenue: $5,000,000
- Net Profit: $1,000,000
- Employees: 5,000

## Board of Directors

| Name | Role | Type | Total Fee |
|------|------|------|-----------|
| Alice Smith | Chairman | Non-Executive | 200,000 |
| Bob Jones | Member | Independent | 105,000 |

## Board Committees

### Audit Committee
| Member | Role | Fee |
|--------|------|-----|
| Alice Smith | Chairman | 50,000 |
| Bob Jones | Member | 30,000 |
"""
