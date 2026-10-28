"""Shared fixtures using synthetic client records; no private data or Google account needed."""
from pathlib import Path
import sys
import csv
import pytest

# Permit `python -m pytest` and the `pytest` command from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from util import load_client_database

COLUMNS = ["first name", "last name", "address", "postal code", "city", "to", "id", "rate"]


@pytest.fixture
def client_csv(tmp_path):
    """Factory creating an isolated CSV with the exact application headers."""
    def write(rows):
        path = tmp_path / "clients.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        return path
    return write


@pytest.fixture
def sample_rows():
    return [
        {"first name": "Emma", "last name": "de Vries", "address": "Teststraat 1", "postal code": "1234 AB", "city": "Leiden", "to": "", "id": "CL001", "rate": "100"},
        {"first name": "Milan", "last name": "Bellen", "address": "Teststraat 2", "postal code": "1234 CD", "city": "Leiden", "to": "", "id": "CL002", "rate": "105"},
        {"first name": "Sophie", "last name": "Bakker", "address": "Teststraat 3", "postal code": "1234 EF", "city": "Delft", "to": "Administratie Sophie", "id": "CL003", "rate": "110"},
    ]


@pytest.fixture
def clients(client_csv, sample_rows):
    return load_client_database(str(client_csv(sample_rows)))


def find_client(data, name):
    return next(c for c in data["clients"].values() if c.full_name == name)
