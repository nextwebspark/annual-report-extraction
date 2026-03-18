"""All LLM prompts as named constants. Inject {markdown} before sending to the API."""

from config.prompts.company import COMPANY_EXTRACTION_PROMPT
from config.prompts.directors import DIRECTORS_EXTRACTION_PROMPT
from config.prompts.committees import COMMITTEES_EXTRACTION_PROMPT

__all__ = [
    "COMPANY_EXTRACTION_PROMPT",
    "DIRECTORS_EXTRACTION_PROMPT",
    "COMMITTEES_EXTRACTION_PROMPT",
]
