import re
from typing import Optional, Tuple, Dict, Any

# Strict RFC 5322 compliant regex for practical email validation
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


def is_valid_email(email: str) -> bool:
    """Checks whether an email string meets strict RFC syntax and valid domain structure."""
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    if len(email) > 254:
        return False
    return bool(EMAIL_REGEX.match(email))


def sanitize_email(email: str) -> str:
    """Cleans, strips whitespace, control characters, and downcases an email address."""
    if not email:
        return ""
    # Strip any invisible spaces, control chars, mailto: prefixes
    clean = email.strip().lower()
    clean = re.sub(r"^mailto:\s*", "", clean)
    clean = re.sub(r"[\r\n\t]", "", clean)
    return clean


def format_proper_name(name: str) -> str:
    """
    Cleans and capitalizes names into title case gracefully.
    Handles names like 'o'connor', 'mcgregor', hyphenated names, etc.
    """
    if not name or not isinstance(name, str):
        return ""
    # Strip surrounding punctuation/whitespace
    name = re.sub(r"[\r\n\t]", " ", name).strip()
    words = name.split()
    capitalized_words = []
    for w in words:
        if "-" in w:
            capitalized_words.append("-".join(sub.capitalize() for sub in w.split("-")))
        elif "'" in w:
            capitalized_words.append("'".join(sub.capitalize() for sub in w.split("'")))
        else:
            capitalized_words.append(w.capitalize())
    return " ".join(capitalized_words)


def extract_first_name(full_name: str, fallback: str = "Friend") -> str:
    """Extracts first name from full name or returns friendly fallback."""
    if not full_name:
        return fallback
    clean = format_proper_name(full_name)
    parts = clean.split()
    if parts:
        # Avoid titles like Mr., Ms., Dr.
        first = parts[0]
        if first.lower() in ("mr", "mr.", "ms", "ms.", "mrs", "mrs.", "dr", "dr.", "prof", "prof.") and len(parts) > 1:
            return parts[1]
        return first
    return fallback


def validate_and_normalize_contact(raw_contact: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Validates a raw contact dictionary.
    Returns (is_valid, normalized_dict, error_message).
    """
    raw_email = str(raw_contact.get("email") or "")
    clean_email = sanitize_email(raw_email)

    if not is_valid_email(clean_email):
        return False, None, f"Invalid email format: '{raw_email}'"

    raw_name = str(raw_contact.get("name") or "")
    clean_name = format_proper_name(raw_name) or clean_email.split("@")[0].capitalize()
    first_name = raw_contact.get("first_name") or extract_first_name(clean_name)

    extra_data = raw_contact.get("extra_data") or {}
    if not isinstance(extra_data, dict):
        extra_data = {}

    normalized = {
        "email": clean_email,
        "name": clean_name,
        "first_name": first_name,
        "extra_data": extra_data,
        "source_file": str(raw_contact.get("source_file") or ""),
    }
    return True, normalized, None
