"""Unit tests for execution/validate.py — pure functions, no mocking needed."""

import pytest

from execution.validate import (
    ABBREVIATED_NATIONALITIES,
    validate_committees_strict,
    validate_committees_soft,
    validate_directors_strict,
    validate_directors_soft,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_director(**overrides) -> dict:
    base = {
        "director_name": "Alice Smith",
        "board_role": "Member",
        "director_type": "Non-Executive",
        "gender": "Female",
        "nationality": "British",
        "skills": "Finance",
        "retainer_fee": 100000,
        "attendance_allowance": 0,
        "director_board_committee_fee": 0,
        "expense_allowance": 0,
        "assembly_fee": 0,
        "benefits_in_kind": 0,
        "variable_remuneration": 0,
        "other_remuneration": 0,
        "total_fee": 100000,
    }
    base.update(overrides)
    return base


def make_committee(**overrides) -> dict:
    base = {
        "member_name": "Alice Smith",
        "committee_name": "Audit Committee",
        "gender": "Female",
        "nationality": "British",
        "committee_retainer_fee": 50000,
        "committee_allowances": 0,
        "committee_total_fee": 50000,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# validate_directors_strict
# ---------------------------------------------------------------------------

class TestValidateDirectorsStrict:

    def test_valid_director_returns_no_errors(self):
        assert validate_directors_strict([make_director()]) == []

    def test_empty_list_returns_no_errors(self):
        assert validate_directors_strict([]) == []

    def test_empty_name_is_error(self):
        errors = validate_directors_strict([make_director(director_name="")])
        assert any("director_name is empty" in e for e in errors)

    def test_whitespace_name_is_error(self):
        errors = validate_directors_strict([make_director(director_name="   ")])
        assert any("director_name is empty" in e for e in errors)

    def test_invalid_board_role_is_error(self):
        errors = validate_directors_strict([make_director(board_role="Observer")])
        assert any("board_role" in e for e in errors)

    @pytest.mark.parametrize("role", ["Chairman", "Vice Chairman", "Member"])
    def test_valid_board_roles_accepted(self, role):
        assert validate_directors_strict([make_director(board_role=role)]) == []

    def test_invalid_director_type_is_error(self):
        errors = validate_directors_strict([make_director(director_type="Advisory")])
        assert any("director_type" in e for e in errors)

    @pytest.mark.parametrize("dtype", ["Executive", "Non-Executive", "Independent"])
    def test_valid_director_types_accepted(self, dtype):
        assert validate_directors_strict([make_director(director_type=dtype)]) == []

    def test_invalid_gender_is_error(self):
        errors = validate_directors_strict([make_director(gender="Unknown")])
        assert any("gender" in e for e in errors)

    @pytest.mark.parametrize("gender", ["Male", "Female", "not-available"])
    def test_valid_genders_accepted(self, gender):
        assert validate_directors_strict([make_director(gender=gender)]) == []

    def test_fee_arithmetic_mismatch_exceeding_tolerance_is_error(self):
        # components = 100000, total = 98000, delta = 2000 > 1.0
        errors = validate_directors_strict([make_director(retainer_fee=100000, total_fee=98000)])
        assert any("total_fee" in e and "sum_of_components" in e for e in errors)

    def test_fee_arithmetic_within_tolerance_not_error(self):
        # components = 100001, total = 100000, delta = 1.0 — exactly at boundary
        errors = validate_directors_strict([make_director(retainer_fee=100001, total_fee=100000)])
        assert not any("sum_of_components" in e for e in errors)

    def test_fee_arithmetic_skipped_when_total_zero(self):
        # total=0 skips the check even if components are large
        errors = validate_directors_strict([make_director(retainer_fee=100000, total_fee=0)])
        assert not any("sum_of_components" in e for e in errors)

    def test_fee_arithmetic_skipped_when_components_zero(self):
        # All components=0, total>0 — skips arithmetic check
        errors = validate_directors_strict([make_director(retainer_fee=0, total_fee=100000)])
        assert not any("sum_of_components" in e for e in errors)

    def test_negative_retainer_fee_is_error(self):
        errors = validate_directors_strict([make_director(retainer_fee=-100)])
        assert any("retainer_fee" in e and "negative" in e for e in errors)

    def test_negative_total_fee_is_error(self):
        errors = validate_directors_strict([make_director(total_fee=-50000, retainer_fee=0)])
        assert any("total_fee" in e and "negative" in e for e in errors)

    def test_multiple_directors_accumulate_all_errors(self):
        d1 = make_director(director_name="", board_role="Xyz")
        d2 = make_director(director_type="Xyz", gender="Xyz")
        errors = validate_directors_strict([d1, d2])
        assert len(errors) >= 3

    def test_none_fee_values_treated_as_zero(self):
        # None values use `or 0` guard — no TypeError, no spurious error
        d = make_director(retainer_fee=None, total_fee=None)
        errors = validate_directors_strict([d])
        assert not any("negative" in e for e in errors)
        assert not any("sum_of_components" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_directors_soft
# ---------------------------------------------------------------------------

class TestValidateDirectorsSoft:

    def test_valid_director_returns_no_warnings(self):
        assert validate_directors_soft([make_director()]) == []

    def test_empty_list_returns_no_warnings(self):
        assert validate_directors_soft([]) == []

    @pytest.mark.parametrize("nat", sorted(ABBREVIATED_NATIONALITIES))
    def test_abbreviated_nationality_is_warning(self, nat):
        warnings = validate_directors_soft([make_director(nationality=nat)])
        assert any("nationality" in w and "abbreviated" in w for w in warnings)

    def test_full_nationality_no_warning(self):
        assert validate_directors_soft([make_director(nationality="Saudi Arabian")]) == []

    def test_empty_skills_is_warning(self):
        warnings = validate_directors_soft([make_director(skills="")])
        assert any("skills" in w for w in warnings)

    def test_whitespace_skills_is_warning(self):
        warnings = validate_directors_soft([make_director(skills="   ")])
        assert any("skills" in w for w in warnings)

    def test_populated_skills_no_warning(self):
        assert validate_directors_soft([make_director(skills="Finance, Audit")]) == []


# ---------------------------------------------------------------------------
# validate_committees_strict
# ---------------------------------------------------------------------------

class TestValidateCommitteesStrict:

    def test_valid_committee_returns_no_errors(self):
        assert validate_committees_strict([make_committee()]) == []

    def test_empty_list_returns_no_errors(self):
        assert validate_committees_strict([]) == []

    def test_empty_member_name_is_error(self):
        errors = validate_committees_strict([make_committee(member_name="")])
        assert any("member_name is empty" in e for e in errors)

    def test_whitespace_member_name_is_error(self):
        errors = validate_committees_strict([make_committee(member_name="  ")])
        assert any("member_name is empty" in e for e in errors)

    def test_empty_committee_name_is_error(self):
        errors = validate_committees_strict([make_committee(committee_name="")])
        assert any("committee_name is empty" in e for e in errors)

    def test_invalid_gender_is_error(self):
        errors = validate_committees_strict([make_committee(gender="Unknown")])
        assert any("gender" in e for e in errors)

    @pytest.mark.parametrize("gender", ["Male", "Female", "not-available"])
    def test_valid_genders_accepted(self, gender):
        assert validate_committees_strict([make_committee(gender=gender)]) == []

    def test_fee_arithmetic_mismatch_exceeding_tolerance_is_error(self):
        # retainer=50000, allowances=0, total=47000, delta=3000 > 1.0
        errors = validate_committees_strict([make_committee(
            committee_retainer_fee=50000, committee_allowances=0, committee_total_fee=47000
        )])
        assert any("committee_total_fee" in e for e in errors)

    def test_fee_arithmetic_within_tolerance_not_error(self):
        # retainer=50001, total=50000, delta=1.0 — at boundary
        errors = validate_committees_strict([make_committee(
            committee_retainer_fee=50001, committee_allowances=0, committee_total_fee=50000
        )])
        assert not any("committee_total_fee" in e for e in errors)

    def test_fee_arithmetic_skipped_when_total_zero(self):
        errors = validate_committees_strict([make_committee(
            committee_retainer_fee=50000, committee_total_fee=0
        )])
        assert not any("committee_total_fee" in e for e in errors)

    def test_negative_retainer_fee_is_error(self):
        errors = validate_committees_strict([make_committee(committee_retainer_fee=-100)])
        assert any("committee_retainer_fee" in e and "negative" in e for e in errors)

    def test_negative_total_fee_is_error(self):
        errors = validate_committees_strict([make_committee(
            committee_retainer_fee=0, committee_total_fee=-500
        )])
        assert any("committee_total_fee" in e and "negative" in e for e in errors)

    def test_negative_allowances_is_error(self):
        errors = validate_committees_strict([make_committee(committee_allowances=-200)])
        assert any("committee_allowances" in e and "negative" in e for e in errors)


# ---------------------------------------------------------------------------
# validate_committees_soft
# ---------------------------------------------------------------------------

class TestValidateCommitteesSoft:

    def test_valid_committee_returns_no_warnings(self):
        assert validate_committees_soft([make_committee()]) == []

    def test_empty_list_returns_no_warnings(self):
        assert validate_committees_soft([]) == []

    @pytest.mark.parametrize("nat", sorted(ABBREVIATED_NATIONALITIES))
    def test_abbreviated_nationality_is_warning(self, nat):
        warnings = validate_committees_soft([make_committee(nationality=nat)])
        assert any("nationality" in w and "abbreviated" in w for w in warnings)

    def test_full_nationality_no_warning(self):
        assert validate_committees_soft([make_committee(nationality="Saudi Arabian")]) == []
