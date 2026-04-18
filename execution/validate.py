"""Strict and soft validation for extracted directors, committees, and company data.

Strict validators return a list of error messages. Non-empty list = block the DB write.
Soft validators return a list of warning messages. Logged to stderr and persisted to
extraction_runs.error_message — never block a DB write.
"""

from config.normalization import EXCHANGE_TO_MIC, infer_currency_from_country


class ExtractionValidationError(Exception):
    """Raised when extracted data fails blocking validation (schema or strict)."""

    def __init__(self, task: str, errors: list[str]):
        self.task = task
        self.errors = errors
        preview = "; ".join(errors[:3])
        if len(errors) > 3:
            preview += f"; ...+{len(errors) - 3} more"
        super().__init__(f"{task}: {preview}")


VALID_BOARD_ROLES = {"Chairman", "Vice Chairman", "Member"}
VALID_DIRECTOR_TYPES = {"Executive", "Non-Executive", "Independent"}
VALID_GENDERS = {"Male", "Female", "not-available"}
VALID_ETHNICITIES = {"Arab", "Asian", "Western", "Other"}
VALID_LOCAL_EXPAT = {"Local", "Expat", ""}
VALID_COMMITTEE_NAMES = {
    "Audit Committee", "Nomination Committee", "Remuneration Committee",
    "Nomination and Remuneration Committee", "Risk Committee",
    "Executive Committee", "Investment Committee", "Governance Committee", "Other",
}
VALID_COMMITTEE_ROLES = {"Chair", "Vice Chair", "Member", "Secretary", "Other"}
VALID_SECTORS = {
    "Energy", "Materials", "Industrials", "Consumer Discretionary", "Consumer Staples",
    "Health Care", "Financials", "Information Technology", "Communication Services",
    "Utilities", "Real Estate", "Conglomerates & Holding Companies",
    "Sovereign Wealth & Government",
}
KNOWN_EXCHANGES = set(EXCHANGE_TO_MIC.values()) | {
    "NYSE", "NASDAQ", "LSE", "HKEX", "Euronext", "TSX", "ASX", "SGX", "BSE", "NSE",
}
ABBREVIATED_NATIONALITIES = {
    "Saudi", "UAE", "UK", "US", "USA", "KSA",
    "Emirati", "Egyptian", "Kuwaiti", "Qatari",
    "Bahraini", "Omani", "Iraqi", "Lebanese", "Jordanian",
}


# ---------------------------------------------------------------------------
# Directors
# ---------------------------------------------------------------------------

def validate_directors_strict(directors: list[dict]) -> list[str]:
    """Return blocking error messages. Empty list = OK to write."""
    errors = []
    for i, d in enumerate(directors):
        name = d.get("director_name", "")
        prefix = f"[{i}] {name!r}"

        if not name.strip():
            errors.append(f"[{i}] director_name is empty")

        role = d.get("board_role")
        if role not in VALID_BOARD_ROLES:
            errors.append(f"{prefix}: board_role={role!r} not in {VALID_BOARD_ROLES}")

        dtype = d.get("director_type")
        if dtype not in VALID_DIRECTOR_TYPES:
            errors.append(f"{prefix}: director_type={dtype!r} not in {VALID_DIRECTOR_TYPES}")

        gender = d.get("gender")
        if gender not in VALID_GENDERS:
            errors.append(f"{prefix}: gender={gender!r} not in {VALID_GENDERS}")

        # Negative remuneration check
        for field in ("retainer_fee", "attendance_allowance", "benefits_in_kind",
                      "expense_allowance", "assembly_fee", "director_board_committee_fee",
                      "variable_remuneration", "other_remuneration", "total_fee"):
            val = d.get(field, 0) or 0
            if val < 0:
                errors.append(f"{prefix}: {field}={val} is negative")

    return errors


def validate_directors_soft(directors: list[dict]) -> list[str]:
    """Return non-blocking warning messages."""
    warnings = []
    for i, d in enumerate(directors):
        name = d.get("director_name", "")
        prefix = f"[{i}] {name!r}"

        # Fee arithmetic: total_fee should match sum of components (±1.0 tolerance)
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
        if total > 0 and components > 0 and abs(components - total) > 1.0:
            warnings.append(
                f"{prefix}: total_fee={total} != sum_of_components={components:.2f} "
                f"(delta={abs(components - total):.2f})"
            )

        nat = d.get("nationality", "")
        if nat in ABBREVIATED_NATIONALITIES:
            warnings.append(f"{prefix}: nationality={nat!r} is abbreviated (use full descriptor)")

        if not d.get("skills", "").strip():
            warnings.append(f"{prefix}: skills is empty")

        ethnicity = d.get("ethnicity", "")
        if ethnicity not in VALID_ETHNICITIES:
            warnings.append(f"{prefix}: ethnicity={ethnicity!r} not in {VALID_ETHNICITIES}")

        local_expat = d.get("local_expat", "")
        if local_expat not in VALID_LOCAL_EXPAT:
            warnings.append(f"{prefix}: local_expat={local_expat!r} not in {VALID_LOCAL_EXPAT}")

        var_rem = d.get("variable_remuneration", 0) or 0
        if var_rem > 0 and not d.get("variable_remuneration_description", "").strip():
            warnings.append(f"{prefix}: variable_remuneration={var_rem} but description is empty")

        other_rem = d.get("other_remuneration", 0) or 0
        if other_rem > 0 and not d.get("other_remuneration_description", "").strip():
            warnings.append(f"{prefix}: other_remuneration={other_rem} but description is empty")

    return warnings


# ---------------------------------------------------------------------------
# Committees
# ---------------------------------------------------------------------------

def validate_committees_strict(committees: list[dict]) -> list[str]:
    """Return blocking error messages. Empty list = OK to write."""
    errors = []
    for i, c in enumerate(committees):
        name = c.get("member_name", "")
        committee = c.get("committee_name", "")
        prefix = f"[{i}] {name!r} ({committee})"

        if not name.strip():
            errors.append(f"[{i}] member_name is empty")

        if not committee.strip():
            errors.append(f"[{i}] {name!r}: committee_name is empty")

        gender = c.get("gender")
        if gender not in VALID_GENDERS:
            errors.append(f"{prefix}: gender={gender!r} not in {VALID_GENDERS}")

        # Negative check
        for field in ("committee_retainer_fee", "committee_allowances", "committee_total_fee"):
            val = c.get(field, 0) or 0
            if val < 0:
                errors.append(f"{prefix}: {field}={val} is negative")

    return errors


def validate_committees_soft(committees: list[dict]) -> list[str]:
    """Return non-blocking warning messages."""
    warnings = []
    for i, c in enumerate(committees):
        name = c.get("member_name", "")
        committee = c.get("committee_name", "")
        prefix = f"[{i}] {name!r}"

        # Fee arithmetic: committee_total_fee should match retainer + allowances (±1.0 tolerance)
        retainer = c.get("committee_retainer_fee", 0) or 0
        allowances = c.get("committee_allowances", 0) or 0
        total = c.get("committee_total_fee", 0) or 0
        component_sum = retainer + allowances
        if total > 0 and component_sum > 0 and abs(component_sum - total) > 1.0:
            warnings.append(
                f"{prefix}: committee_total_fee={total} != "
                f"retainer({retainer}) + allowances({allowances}) = {component_sum:.2f} "
                f"(delta={abs(component_sum - total):.2f})"
            )

        nat = c.get("nationality", "")
        if nat in ABBREVIATED_NATIONALITIES:
            warnings.append(f"{prefix}: nationality={nat!r} is abbreviated (use full descriptor)")

        ethnicity = c.get("ethnicity", "")
        if ethnicity not in VALID_ETHNICITIES:
            warnings.append(f"{prefix}: ethnicity={ethnicity!r} not in {VALID_ETHNICITIES}")

        local_expat = c.get("local_expat", "")
        if local_expat not in VALID_LOCAL_EXPAT:
            warnings.append(f"{prefix}: local_expat={local_expat!r} not in {VALID_LOCAL_EXPAT}")

        if committee and committee not in VALID_COMMITTEE_NAMES:
            warnings.append(f"{prefix}: committee_name={committee!r} not in controlled vocabulary")

        role = c.get("committee_role", "")
        if role not in VALID_COMMITTEE_ROLES:
            warnings.append(f"{prefix}: committee_role={role!r} not in {VALID_COMMITTEE_ROLES}")

    return warnings


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------

def validate_company_warnings(extracted: dict) -> list[str]:
    """Non-blocking quality checks for company extraction."""
    warnings = []
    co = extracted.get("company", {})
    fin = extracted.get("financials", {})

    # Sector / sub_sector
    sector_val = (co.get("sector") or {}).get("value", "")
    sub_sector_val = (co.get("sub_sector") or {}).get("value", "")
    if sector_val and sector_val not in VALID_SECTORS:
        warnings.append(f"sector={sector_val!r} not in allowed list")
    if sector_val and not sub_sector_val:
        warnings.append("sub_sector is empty but sector is set")

    # Exchange — warn if non-null value is not a recognised code
    exchange_val = (co.get("exchange") or {}).get("value")
    if exchange_val and exchange_val not in KNOWN_EXCHANGES:
        warnings.append(f"exchange={exchange_val!r} not a recognised MIC/exchange code")

    # Currency vs country mismatch
    country_val = (co.get("country") or {}).get("value")
    expected_currency = infer_currency_from_country(country_val)
    if expected_currency:
        for field in ("revenue", "profit_net"):
            stated = (fin.get(field) or {}).get("currency")
            if stated and stated != expected_currency:
                warnings.append(
                    f"{field}.currency={stated!r} does not match expected "
                    f"{expected_currency!r} for country={country_val!r}"
                )

    return warnings
