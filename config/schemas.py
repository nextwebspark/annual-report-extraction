"""JSON schemas for validating LLM extraction outputs. Source of truth for all field definitions.

Each *_SCHEMA defines the structure used for jsonschema.validate() after the LLM responds.
The *_PROMPT_SCHEMA variants wrap the DB schemas with extraction_metadata for the LLM prompt.
schema_to_example() converts any schema into a representative JSON example string that can be
injected into prompts, ensuring prompts always stay in sync with the schema definitions here.
"""

import json


# ---------------------------------------------------------------------------
# Helper: convert a JSON Schema into a representative example JSON string
# ---------------------------------------------------------------------------

def _example_value(prop: dict):
    """Generate a representative example value from a JSON Schema property definition."""
    t = prop.get("type", "string")
    # Handle union types like ["number", "null"]
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), t[0])

    if t == "string":
        if "enum" in prop:
            return prop["enum"][0]
        return ""
    if t == "integer":
        return 0
    if t == "number":
        return 0.0
    if t == "boolean":
        return False
    if t == "array":
        items = prop.get("items", {})
        if not items:
            return []
        if items.get("type") == "object":
            return [_example_object(items)]
        return [_example_value(items)]
    if t == "object":
        return _example_object(prop)
    return None


def _example_object(schema: dict) -> dict:
    """Generate an example object from a JSON Schema object definition."""
    if schema.get("type") != "object" or "properties" not in schema:
        return {}
    result = {}
    for key, prop in schema["properties"].items():
        result[key] = _example_value(prop)
    return result


def schema_to_example(schema: dict, indent: int = 2) -> str:
    """Convert a JSON Schema to a formatted example JSON string for prompt injection.

    Handles top-level objects and arrays. Uses double-brace escaping so the result
    is safe to embed in Python format-strings (prompts use {markdown} etc.).
    """
    t = schema.get("type", "object")
    if t == "array":
        items = schema.get("items", {})
        example = [_example_object(items)]
    elif t == "object":
        example = _example_object(schema)
    else:
        example = {}

    raw = json.dumps(example, indent=indent)
    # Escape braces for Python .format() compatibility: { → {{ and } → }}
    return raw.replace("{", "{{").replace("}", "}}")


# ---------------------------------------------------------------------------
# Company — DB-level schema (used for post-LLM validation)
# ---------------------------------------------------------------------------

COMPANY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Company Profile and Financial Extraction",
    "type": "object",
    "properties": {
        "company": {
            "type": "object",
            "properties": {
                "company_name": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string", "minLength": 1},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "source": {"type": "string"},
                    },
                    "required": ["value", "confidence"],
                    "additionalProperties": False,
                },
                "exchange": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "source": {"type": "string"},
                    },
                    "required": ["value", "confidence"],
                    "additionalProperties": False,
                },
                "country": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string", "minLength": 1},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "source": {"type": "string"},
                    },
                    "required": ["value", "confidence"],
                    "additionalProperties": False,
                },
                "industry": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "source": {"type": "string"},
                    },
                    "required": ["value", "confidence"],
                    "additionalProperties": False,
                },
                "source_document_url": {"type": "string"},
            },
            "required": ["company_name", "exchange", "country", "industry"],
            "additionalProperties": False,
        },
        "financials": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "minimum": 1900, "maximum": 2100},
                "revenue": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number", "minimum": 0},
                        "currency": {"type": "string", "pattern": "^[A-Z]{3}$"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "source": {"type": "string"},
                        "unit_stated": {
                            "type": "string",
                            "enum": ["actual", "thousands", "millions", "billions"],
                        },
                    },
                    "required": ["value", "currency", "confidence"],
                    "additionalProperties": False,
                },
                "profit_net": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "number"},
                        "currency": {"type": "string", "pattern": "^[A-Z]{3}$"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "source": {"type": "string"},
                        "unit_stated": {
                            "type": "string",
                            "enum": ["actual", "thousands", "millions", "billions"],
                        },
                    },
                    "required": ["value", "currency", "confidence"],
                    "additionalProperties": False,
                },
                "market_capitalisation": {
                    "type": "object",
                    "properties": {
                        "value": {"type": ["number", "null"], "minimum": 0},
                        "currency": {"type": ["string", "null"], "pattern": "^[A-Z]{3}$"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "source": {"type": "string"},
                        "unit_stated": {
                            "type": "string",
                            "enum": ["actual", "thousands", "millions", "billions"],
                        },
                    },
                    "required": ["value", "confidence"],
                    "additionalProperties": False,
                },
                "employees": {
                    "type": "object",
                    "properties": {
                        "value": {"type": ["integer", "null"], "minimum": 0},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "source": {"type": "string"},
                    },
                    "required": ["value", "confidence"],
                    "additionalProperties": False,
                },
            },
            "required": ["year", "revenue", "profit_net"],
            "additionalProperties": False,
        },
        "extraction_metadata": {
            "type": "object",
            "properties": {
                "extracted_at": {"type": "string"},
                "document_type": {
                    "type": "string",
                    "enum": [
                        "annual_report",
                        "10-K",
                        "10-Q",
                        "financial_statements",
                        "prospectus",
                        "investor_presentation",
                        "other",
                    ],
                },
                "fiscal_year_end": {"type": "string"},
                "fiscal_year_ambiguous": {"type": "boolean"},
                "reporting_standard": {
                    "type": "string",
                    "enum": ["IFRS", "US GAAP", "local GAAP", "other"],
                },
                "figures_restated": {"type": "boolean"},
                "figures_consolidated": {"type": "boolean"},
                "document_sections_found": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "extraction_notes": {"type": "string"},
                "conflicts": {
                    "type": "array",
                    "items": {"type": "object"},
                },
            },
            "additionalProperties": False,
        },
    },
    "required": ["company", "financials"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Directors — DB-level item schema (used for post-LLM validation on the array)
# ---------------------------------------------------------------------------

_DIRECTOR_ITEM = {
    "type": "object",
    "properties": {
        "fact_id": {"type": "integer"},
        "director_name": {"type": "string"},
        "nationality": {"type": "string"},
        "ethnicity": {"type": "string"},
        "local_expat": {"type": "string"},
        "gender": {"type": "string", "enum": ["Male", "Female", "not-available"]},
        "age": {"type": "integer", "minimum": 0},
        "board_role": {"type": "string"},
        "director_type": {"type": "string"},
        "skills": {"type": "string"},
        "board_meetings_attended": {"type": "integer", "minimum": 0},
        "retainer_fee": {"type": "number", "minimum": 0},
        "benefits_in_kind": {"type": "number", "minimum": 0},
        "attendance_allowance": {"type": "number", "minimum": 0},
        "expense_allowance": {"type": "number", "minimum": 0},
        "assembly_fee": {"type": "number", "minimum": 0},
        "director_board_committee_fee": {"type": "number", "minimum": 0},
        "variable_remuneration": {"type": "number", "minimum": 0},
        "variable_remuneration_description": {"type": "string"},
        "other_remuneration": {"type": "number", "minimum": 0},
        "other_remuneration_description": {"type": "string"},
        "total_fee": {"type": "number", "minimum": 0},
    },
    "required": [
        "fact_id",
        "director_name",
        "nationality",
        "ethnicity",
        "local_expat",
        "gender",
        "age",
        "board_role",
        "director_type",
        "skills",
        "board_meetings_attended",
        "retainer_fee",
        "benefits_in_kind",
        "attendance_allowance",
        "expense_allowance",
        "assembly_fee",
        "director_board_committee_fee",
        "variable_remuneration",
        "variable_remuneration_description",
        "other_remuneration",
        "other_remuneration_description",
        "total_fee",
    ],
    "additionalProperties": False,
}

DIRECTORS_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Board Directors Table Schema",
    "type": "array",
    "items": _DIRECTOR_ITEM,
}

# Wrapper schema used in prompts (includes extraction_metadata)
DIRECTORS_PROMPT_SCHEMA = {
    "type": "object",
    "properties": {
        "directors": {
            "type": "array",
            "items": _DIRECTOR_ITEM,
        },
        "extraction_metadata": {
            "type": "object",
            "properties": {
                "total_directors_extracted": {"type": "integer"},
                "past_directors_excluded": {"type": "integer"},
                "mid_year_joiners_included": {"type": "integer"},
                "total_board_meetings_held": {"type": "integer"},
                "meeting_count_verified": {"type": "boolean"},
                "currency": {"type": "string"},
                "extraction_notes": {"type": "string"},
                "conflicts": {"type": "array", "items": {"type": "object"}},
            },
            "additionalProperties": False,
        },
    },
    "required": ["directors", "extraction_metadata"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Committees — DB-level item schema (used for post-LLM validation on the array)
# ---------------------------------------------------------------------------

_COMMITTEE_ITEM = {
    "type": "object",
    "properties": {
        "fact_id": {"type": "integer"},
        "member_name": {"type": "string"},
        "nationality": {"type": "string"},
        "ethnicity": {"type": "string"},
        "local_expat": {"type": "string"},
        "gender": {"type": "string", "enum": ["Male", "Female", "not-available"]},
        "age": {"type": "integer", "minimum": 0},
        "committee_name": {"type": "string"},
        "committee_role": {"type": "string"},
        "committee_meetings_attended": {"type": "integer", "minimum": 0},
        "committee_retainer_fee": {"type": "number", "minimum": 0},
        "committee_allowances": {"type": "number", "minimum": 0},
        "committee_total_fee": {"type": "number", "minimum": 0},
    },
    "required": [
        "fact_id",
        "member_name",
        "nationality",
        "ethnicity",
        "local_expat",
        "gender",
        "age",
        "committee_name",
        "committee_role",
        "committee_meetings_attended",
        "committee_retainer_fee",
        "committee_allowances",
        "committee_total_fee",
    ],
    "additionalProperties": False,
}

COMMITTEES_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Board Committees Table Schema",
    "type": "array",
    "items": _COMMITTEE_ITEM,
}

# Wrapper schema used in prompts (includes extraction_metadata)
COMMITTEES_PROMPT_SCHEMA = {
    "type": "object",
    "properties": {
        "committee_memberships": {
            "type": "array",
            "items": _COMMITTEE_ITEM,
        },
        "extraction_metadata": {
            "type": "object",
            "properties": {
                "total_memberships_extracted": {"type": "integer"},
                "past_members_excluded": {"type": "integer"},
                "mid_year_joiners_included": {"type": "integer"},
                "non_board_members_included": {"type": "integer"},
                "committees_found": {"type": "array", "items": {"type": "string"}},
                "currency": {"type": "string"},
                "extraction_notes": {"type": "string"},
                "conflicts": {"type": "array", "items": {"type": "object"}},
            },
            "additionalProperties": False,
        },
    },
    "required": ["committee_memberships", "extraction_metadata"],
    "additionalProperties": False,
}
