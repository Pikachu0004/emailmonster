import csv
import io
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import openpyxl
from pypdf import PdfReader

from devengers_engine.parsers.validator import (
    is_valid_email,
    sanitize_email,
    format_proper_name,
    extract_first_name,
    validate_and_normalize_contact,
)

# Heuristic patterns for column matching
EMAIL_HEADER_PATTERNS = [
    r"e[\s\-_]?mail",
    r"^mail$",
    r"contact[\s\-_]?mail",
    r"email[\s\-_]?id",
    r"email[\s\-_]?address",
    r"attendee[\s\-_]?email",
    r"participant[\s\-_]?email",
    r"user[\s\-_]?email",
    r"mail[\s\-_]?address",
]

NAME_HEADER_PATTERNS = [
    r"^full[\s\-_]?name$",
    r"^name$",
    r"^participant([\s\-_]?name)?$",
    r"^student([\s\-_]?name)?$",
    r"^candidate([\s\-_]?name)?$",
    r"^attendee([\s\-_]?name)?$",
    r"^member([\s\-_]?name)?$",
    r"^contact([\s\-_]?name)?$",
    r"^first[\s\-_]?name$",
    r"name$",
]


class FileExtractor:
    """Universal parser for Excel (.xlsx, .xls), CSV (.csv), and PDF (.pdf)."""

    @classmethod
    def extract_from_file(cls, file_path: str | Path) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Extracts candidate contacts from a file.
        Returns:
            (valid_contacts, extraction_warnings_or_errors)
        """
        path = Path(file_path)
        if not path.exists():
            return [], [f"File not found: {file_path}"]

        ext = path.suffix.lower()
        if ext in (".xlsx", ".xlsm", ".xltx"):
            return cls.extract_from_excel(path)
        elif ext == ".csv":
            return cls.extract_from_csv(path)
        elif ext == ".pdf":
            return cls.extract_from_pdf(path)
        else:
            return [], [f"Unsupported file format '{ext}'. Supported formats: .xlsx, .csv, .pdf"]

    @classmethod
    def extract_from_excel(cls, path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Reads rows from openpyxl workbook, detects columns, and normalizes contacts."""
        warnings: List[str] = []
        contacts: List[Dict[str, Any]] = []

        try:
            wb = openpyxl.load_workbook(filename=str(path), read_only=True, data_only=True)
            sheet = wb.active
            if sheet is None:
                return [], ["Excel workbook contains no active sheets."]

            rows = list(sheet.iter_rows(values_only=True))
            wb.close()

            if not rows:
                return [], ["Excel file is completely empty."]

            # Find header row
            header_row_idx, col_map = cls._detect_columns(rows)
            if col_map["email"] is None:
                return [], ["Could not locate an Email column in the Excel file."]

            seen_emails = set()
            for r_idx in range(header_row_idx + 1, len(rows)):
                row_vals = rows[r_idx]
                if not row_vals or all(v is None or str(v).strip() == "" for v in row_vals):
                    continue

                email_idx = col_map["email"]
                raw_email = str(row_vals[email_idx] or "").strip() if email_idx < len(row_vals) else ""
                clean_email = sanitize_email(raw_email)

                if not is_valid_email(clean_email):
                    if clean_email:
                        warnings.append(f"Row {r_idx+1}: Skipped invalid email '{raw_email}'")
                    continue

                if clean_email in seen_emails:
                    warnings.append(f"Row {r_idx+1}: Skipped duplicate email '{clean_email}'")
                    continue
                seen_emails.add(clean_email)

                # Extract Name
                name_idx = col_map.get("name")
                raw_name = str(row_vals[name_idx] or "").strip() if (name_idx is not None and name_idx < len(row_vals)) else ""
                name = format_proper_name(raw_name) or clean_email.split("@")[0].replace(".", " ").title()
                first_name = extract_first_name(name)

                # Collect extra columns
                extra_data = {}
                headers = [str(h or f"col_{i}") for i, h in enumerate(rows[header_row_idx])]
                for i, val in enumerate(row_vals):
                    if i != email_idx and i != name_idx and i < len(headers) and val is not None:
                        col_name = headers[i].strip().lower().replace(" ", "_")
                        extra_data[col_name] = str(val).strip()

                contacts.append({
                    "email": clean_email,
                    "name": name,
                    "first_name": first_name,
                    "extra_data": extra_data,
                    "source_file": path.name,
                })

        except Exception as e:
            return [], [f"Failed to parse Excel file: {str(e)}"]

        return contacts, warnings

    @classmethod
    def extract_from_csv(cls, path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Reads CSV files with delimiter sniffing and column normalization."""
        warnings: List[str] = []
        contacts: List[Dict[str, Any]] = []

        try:
            # Read first chunk to detect encoding and delimiter
            with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                content = f.read()

            if not content.strip():
                return [], ["CSV file is empty."]

            # Sniff delimiter
            sample = content[:4096]
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
                delimiter = dialect.delimiter
            except Exception:
                delimiter = ","

            reader = csv.reader(io.StringIO(content), delimiter=delimiter)
            rows = [row for row in reader if any(cell.strip() for cell in row)]

            if not rows:
                return [], ["No valid data rows found in CSV."]

            header_row_idx, col_map = cls._detect_columns(rows)
            if col_map["email"] is None:
                return [], ["Could not locate an Email column in the CSV file."]

            seen_emails = set()
            headers = [h.strip() for h in rows[header_row_idx]]

            for r_idx in range(header_row_idx + 1, len(rows)):
                row_vals = rows[r_idx]
                if not row_vals or not any(row_vals):
                    continue

                email_idx = col_map["email"]
                raw_email = row_vals[email_idx].strip() if email_idx < len(row_vals) else ""
                clean_email = sanitize_email(raw_email)

                if not is_valid_email(clean_email):
                    if clean_email:
                        warnings.append(f"Row {r_idx+1}: Skipped invalid email '{raw_email}'")
                    continue

                if clean_email in seen_emails:
                    warnings.append(f"Row {r_idx+1}: Skipped duplicate email '{clean_email}'")
                    continue
                seen_emails.add(clean_email)

                name_idx = col_map.get("name")
                raw_name = row_vals[name_idx].strip() if (name_idx is not None and name_idx < len(row_vals)) else ""
                name = format_proper_name(raw_name) or clean_email.split("@")[0].replace(".", " ").title()
                first_name = extract_first_name(name)

                extra_data = {}
                for i, val in enumerate(row_vals):
                    if i != email_idx and i != name_idx and i < len(headers) and val.strip():
                        col_name = headers[i].strip().lower().replace(" ", "_")
                        extra_data[col_name] = val.strip()

                contacts.append({
                    "email": clean_email,
                    "name": name,
                    "first_name": first_name,
                    "extra_data": extra_data,
                    "source_file": path.name,
                })

        except Exception as e:
            return [], [f"Failed to parse CSV file: {str(e)}"]

        return contacts, warnings

    @classmethod
    def extract_from_pdf(cls, path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Extracts emails and names from PDF documents.
        Handles tabular text as well as natural flow paragraphs.
        """
        warnings: List[str] = []
        contacts: List[Dict[str, Any]] = []

        try:
            reader = PdfReader(str(path))
            full_text = ""
            for idx, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                full_text += f"\n--- Page {idx+1} ---\n" + text

            if not full_text.strip():
                return [], ["No readable text found in PDF (might be a scanned image)."]

            lines = full_text.splitlines()
            seen_emails = set()

            # Regex to find emails within lines
            email_finder = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")

            for line_no, line in enumerate(lines):
                line_str = line.strip()
                if not line_str or line_str.startswith("--- Page"):
                    continue

                matches = email_finder.findall(line_str)
                for raw_email in matches:
                    clean_email = sanitize_email(raw_email)
                    if not is_valid_email(clean_email):
                        continue

                    if clean_email in seen_emails:
                        continue
                    seen_emails.add(clean_email)

                    # Infer name: Remove email from line, take remaining text if reasonable
                    remaining = line_str.replace(raw_email, "").strip()
                    # Strip common separators (commas, pipes, tabs, semicolons, bullets)
                    remaining = re.sub(r"^[\s,\|\t\-\*]+|[\s,\|\t\-\*]+$", "", remaining).strip()

                    # If remaining has letters and isn't too long, use as name
                    words = remaining.split()
                    if words and 1 <= len(words) <= 5 and not any(ch in remaining for ch in ["@", "http", "www"]):
                        name = format_proper_name(" ".join(words))
                    else:
                        # Fallback: Derive friendly name from email username
                        email_prefix = clean_email.split("@")[0]
                        name = format_proper_name(re.sub(r"[._0-9]+", " ", email_prefix)) or "Community Member"

                    first_name = extract_first_name(name)

                    contacts.append({
                        "email": clean_email,
                        "name": name,
                        "first_name": first_name,
                        "extra_data": {"extracted_line": line_str},
                        "source_file": path.name,
                    })

        except Exception as e:
            return [], [f"Failed to parse PDF file: {str(e)}"]

        if not contacts:
            warnings.append("No valid email addresses found in the PDF.")

        return contacts, warnings

    @classmethod
    def _detect_columns(cls, rows: List[Any]) -> Tuple[int, Dict[str, Optional[int]]]:
        """
        Inspects top rows to find header row and map email and name indices.
        Returns: (header_row_index, {'email': idx, 'name': idx})
        """
        col_map: Dict[str, Optional[int]] = {"email": None, "name": None}

        # Check top 5 rows for header candidates
        max_scan = min(5, len(rows))
        for r_idx in range(max_scan):
            row = rows[r_idx]
            if not row:
                continue

            for c_idx, cell in enumerate(row):
                if cell is None:
                    continue
                cell_str = str(cell).strip().lower()

                # Check Email patterns
                if col_map["email"] is None:
                    for pat in EMAIL_HEADER_PATTERNS:
                        if re.search(pat, cell_str):
                            col_map["email"] = c_idx
                            break

                # Check Name patterns
                if col_map["name"] is None:
                    for pat in NAME_HEADER_PATTERNS:
                        if re.search(pat, cell_str):
                            col_map["name"] = c_idx
                            break

            if col_map["email"] is not None:
                return r_idx, col_map

        # Fallback: Scan column data for email values if no header name matched
        for c_idx in range(len(rows[0]) if rows and rows[0] else 0):
            matches = 0
            for r_idx in range(min(10, len(rows))):
                if c_idx < len(rows[r_idx]):
                    val = str(rows[r_idx][c_idx] or "").strip()
                    if is_valid_email(val):
                        matches += 1
            if matches >= 1:
                col_map["email"] = c_idx
                # Guess name column as the preceding column or first column
                col_map["name"] = 0 if c_idx != 0 else (1 if len(rows[0]) > 1 else None)
                return 0, col_map

        return 0, col_map
