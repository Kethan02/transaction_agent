import re


def clean_description(description: str) -> str:
    """Remove statement formatting and likely trailing reference IDs."""
    cleaned = re.sub(r"\s+", " ", description).strip()
    cleaned = re.sub(
        r"^(?:(?:SQ|TST)\s*\*\s*|POS DEBIT\s+|CHECKCARD\s+(?:\d{4}\s+)?)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"(?<!\S)#\d+\b|\bSTORE\s+\d+\b", "", cleaned, flags=re.IGNORECASE)
    # Only treat trailing tokens as reference IDs; mixed codes need both character types.
    cleaned = re.sub(
        r"[\s*]+(?:\d{4,}|(?=[A-Z0-9]*[A-Z])(?=[A-Z0-9]*\d)[A-Z0-9]{6,})\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", cleaned).strip()
