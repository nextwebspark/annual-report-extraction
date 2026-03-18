"""Evaluation metrics for extraction quality.

All functions check internal consistency (no ground truth required).
Scores are between 0.0 and 1.0 (higher = better).
"""


def fee_arithmetic_correctness(extracted: list[dict]) -> float:
    """Fraction of directors where total_fee == sum of components (within +/-1)."""
    correct = 0
    for d in extracted:
        components = sum([
            d.get("retainer_fee", 0) or 0,
            d.get("attendance_allowance", 0) or 0,
            d.get("director_board_committee_fee", 0) or 0,
            d.get("expense_allowance", 0) or 0,
            d.get("assembly_fee", 0) or 0,
            d.get("benefits_in_kind", 0) or 0,
            d.get("variable_remuneration", 0) or 0,
            d.get("other_remuneration", 0) or 0,
        ])
        total = d.get("total_fee", 0) or 0
        if abs(components - total) <= 1.0:
            correct += 1
    return correct / len(extracted) if extracted else 1.0


def committee_fee_arithmetic(committees: list[dict]) -> float:
    """Fraction of committee records where total_fee == retainer + allowances (+/-1)."""
    correct = 0
    for c in committees:
        retainer = c.get("committee_retainer_fee", 0) or 0
        allowances = c.get("committee_allowances", 0) or 0
        total = c.get("committee_total_fee", 0) or 0
        if abs((retainer + allowances) - total) <= 1.0:
            correct += 1
    return correct / len(committees) if committees else 1.0


def committee_name_crossref_rate(directors: list[dict], committees: list[dict]) -> float:
    """Fraction of committee member_names that exactly match a director_name."""
    director_names = {d["director_name"] for d in directors}
    matched = sum(1 for c in committees if c["member_name"] in director_names)
    return matched / len(committees) if committees else 1.0


def nationality_format_correctness(records: list[dict],
                                   field: str = "nationality") -> float:
    """Fraction of records using full country name (not abbreviated)."""
    abbreviated = {"Saudi", "UAE", "UK", "US", "USA", "KSA", "Emirati"}
    correct = sum(1 for r in records if r.get(field) not in abbreviated)
    return correct / len(records) if records else 1.0


def run_validation_summary(directors: list[dict], committees: list[dict]) -> dict:
    """Run all validations and return a summary dict."""
    return {
        "director_count": len(directors),
        "committee_membership_count": len(committees),
        "director_fee_arithmetic": fee_arithmetic_correctness(directors),
        "committee_fee_arithmetic": committee_fee_arithmetic(committees),
        "name_crossref_rate": committee_name_crossref_rate(directors, committees),
        "nationality_format_directors": nationality_format_correctness(directors),
        "nationality_format_committees": nationality_format_correctness(committees, field="nationality"),
    }
