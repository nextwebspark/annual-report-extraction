"""Strict and soft validation for extracted directors and committees data.

Strict validators return a list of error messages. Non-empty list = block the DB write.
Soft validators return a list of warning messages. Logged to stderr but never block.
"""

VALID_BOARD_ROLES = {"Chairman", "Vice Chairman", "Member"}
VALID_DIRECTOR_TYPES = {"Executive", "Non-Executive", "Independent"}
VALID_GENDERS = {"Male", "Female", "not-available"}
ABBREVIATED_NATIONALITIES = {"Saudi", "UAE", "UK", "US", "USA", "KSA", "Emirati"}


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
            errors.append(
                f"{prefix}: total_fee={total} != sum_of_components={components:.2f} "
                f"(delta={abs(components - total):.2f})"
            )

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

        nat = d.get("nationality", "")
        if nat in ABBREVIATED_NATIONALITIES:
            warnings.append(f"{prefix}: nationality={nat!r} is abbreviated (use full country name)")

        if not d.get("skills", "").strip():
            warnings.append(f"{prefix}: skills is empty")

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

        # Fee arithmetic: committee_total_fee should match retainer + allowances
        retainer = c.get("committee_retainer_fee", 0) or 0
        allowances = c.get("committee_allowances", 0) or 0
        total = c.get("committee_total_fee", 0) or 0
        component_sum = retainer + allowances
        if total > 0 and component_sum > 0 and abs(component_sum - total) > 1.0:
            errors.append(
                f"{prefix}: committee_total_fee={total} != "
                f"retainer({retainer}) + allowances({allowances}) = {component_sum:.2f}"
            )

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
        prefix = f"[{i}] {name!r}"

        nat = c.get("nationality", "")
        if nat in ABBREVIATED_NATIONALITIES:
            warnings.append(f"{prefix}: nationality={nat!r} is abbreviated (use full country name)")

    return warnings
