import openpyxl
import pytest
from pathlib import Path
from devengers_engine.parsers.extractor import FileExtractor


def test_excel_extractor(tmp_path: Path):
    excel_file = tmp_path / "test_contacts.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Attendees"

    # Headers with varying column names
    ws.append(["Candidate Name", "Email Address", "College", "Role"])
    ws.append(["Kishan Sharma", "kishan@devengers.org", "Tech University", "Lead"])
    ws.append(["Tony Stark", "tony@starkindustries.com", "MIT", "Engineer"])
    ws.append(["Duplicate User", "kishan@devengers.org", "Tech University", "Duplicate"]) # duplicate email
    ws.append(["Invalid Record", "not-an-email", "None", "None"]) # invalid
    ws.append(["", "", "", ""]) # empty row
    wb.save(excel_file)

    contacts, warnings = FileExtractor.extract_from_excel(excel_file)
    assert len(contacts) == 2
    assert contacts[0]["email"] == "kishan@devengers.org"
    assert contacts[0]["name"] == "Kishan Sharma"
    assert contacts[0]["first_name"] == "Kishan"
    assert contacts[0]["extra_data"]["college"] == "Tech University"
    assert contacts[1]["email"] == "tony@starkindustries.com"
    assert len(warnings) >= 2  # duplicate warning & invalid warning


def test_csv_extractor(tmp_path: Path):
    csv_file = tmp_path / "test_contacts.csv"
    csv_content = """Name,Email,Team
Peter Parker,peter@dailybugle.com,Web
Miles Morales,miles@spider.org,Brooklyn
Bruce Wayne,bruce@waynecorp.com,Gotham
"""
    csv_file.write_text(csv_content, encoding="utf-8")

    contacts, warnings = FileExtractor.extract_from_csv(csv_file)
    assert len(contacts) == 3
    assert contacts[0]["email"] == "peter@dailybugle.com"
    assert contacts[0]["first_name"] == "Peter"
    assert contacts[0]["extra_data"]["team"] == "Web"


def test_csv_semicolon_delimited(tmp_path: Path):
    csv_file = tmp_path / "semicolon.csv"
    csv_content = "Participant;Contact Email;City\nClark Kent;clark@planet.com;Metropolis\n"
    csv_file.write_text(csv_content, encoding="utf-8")

    contacts, warnings = FileExtractor.extract_from_csv(csv_file)
    assert len(contacts) == 1
    assert contacts[0]["email"] == "clark@planet.com"
    assert contacts[0]["name"] == "Clark Kent"
