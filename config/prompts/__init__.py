"""All LLM prompts as named constants. System prompts contain instructions; user prompts contain {markdown}."""

from config.prompts.company import COMPANY_SYSTEM_PROMPT, COMPANY_USER_PROMPT
from config.prompts.directors import DIRECTORS_SYSTEM_PROMPT, DIRECTORS_USER_PROMPT
from config.prompts.committees import COMMITTEES_SYSTEM_PROMPT, COMMITTEES_USER_PROMPT

__all__ = [
    "COMPANY_SYSTEM_PROMPT",
    "COMPANY_USER_PROMPT",
    "DIRECTORS_SYSTEM_PROMPT",
    "DIRECTORS_USER_PROMPT",
    "COMMITTEES_SYSTEM_PROMPT",
    "COMMITTEES_USER_PROMPT",
]
