"""Static lookup maps for country → currency and exchange → MIC normalization.

Mirrors the data in supabase-schema/ref_markets.sql. Used in extract_company.py
before DB writes so no Supabase round-trip is needed at runtime.
"""

COUNTRY_TO_CURRENCY: dict[str, str] = {
    "Afghanistan": "AFN",
    "Armenia": "AMD",
    "Azerbaijan": "AZN",
    "Bahrain": "BHD",
    "Cyprus": "EUR",
    "Egypt": "EGP",
    "Georgia": "GEL",
    "Iran": "IRR",
    "Iraq": "IQD",
    "Israel": "ILS",
    "Jordan": "JOD",
    "Kuwait": "KWD",
    "Lebanon": "LBP",
    "Oman": "OMR",
    "Palestine": "ILS",
    "Qatar": "QAR",
    "Saudi Arabia": "SAR",
    "Syria": "SYP",
    "Turkey": "TRY",
    "UAE": "AED",
    "United Arab Emirates": "AED",
    "Yemen": "YER",
}

# Maps exchange labels, common aliases, and MIC codes → canonical MIC
EXCHANGE_TO_MIC: dict[str, str] = {
    "Tadawul": "XSAU",
    "Saudi Stock Exchange": "XSAU",
    "XSAU": "XSAU",
    "Dubai Financial Market": "XDFM",
    "DFM": "XDFM",
    "XDFM": "XDFM",
    "Abu Dhabi Securities Exchange": "XADS",
    "ADX": "XADS",
    "XADS": "XADS",
    "Nasdaq Dubai": "XNDQ",
    "XNDQ": "XNDQ",
    "Boursa Kuwait": "XKUW",
    "Kuwait Stock Exchange": "XKUW",
    "XKUW": "XKUW",
    "Borsa Istanbul": "XIST",
    "XIST": "XIST",
    "Qatar Stock Exchange": "XDSM",
    "Doha Securities Market": "XDSM",
    "XDSM": "XDSM",
    "Bahrain Bourse": "XBAH",
    "Bahrain Stock Exchange": "XBAH",
    "XBAH": "XBAH",
    "Amman Stock Exchange": "XASE",
    "XASE": "XASE",
    "Tel Aviv Stock Exchange": "XTAE",
    "TASE": "XTAE",
    "XTAE": "XTAE",
    "Egyptian Exchange": "XCAI",
    "Cairo and Alexandria Stock Exchange": "XCAI",
    "XCAI": "XCAI",
    "Beirut Stock Exchange": "XBES",
    "XBES": "XBES",
    "Muscat Securities Market": "XMSM",
    "Muscat Stock Exchange": "XMSM",
    "XMSM": "XMSM",
}


def normalize_exchange(value: str | None) -> str | None:
    """Map exchange label or alias → canonical MIC code. Returns input unchanged if unknown."""
    if not value:
        return value
    return EXCHANGE_TO_MIC.get(value.strip(), value)


def infer_currency_from_country(country: str | None) -> str | None:
    """Return the ISO 4217 currency for a country name. Returns None if unknown."""
    if not country:
        return None
    return COUNTRY_TO_CURRENCY.get(country.strip())
