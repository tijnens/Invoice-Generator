from conftest import find_client
from util import load_client_database


def test_csv_loads_clients(clients):
    assert len(clients["clients"]) == 3
    emma = find_client(clients, "Emma de Vries")
    assert emma.invoice_id == "CL001"
    assert emma.rate == 100.0
    assert emma.address == "Teststraat 1"


def test_invoice_addressee_loaded(clients):
    assert find_client(clients, "Sophie Bakker").invoice_addressee == "Administratie Sophie"


def test_duplicate_first_names_case_insensitive(client_csv, sample_rows):
    sample_rows.append({**sample_rows[0], "first name": "EMMA", "last name": "Jansen", "id": "CL004"})
    data = load_client_database(str(client_csv(sample_rows)))
    assert data["duplicate_first_names"] == {"emma de vries", "emma jansen"}


def test_bellen_surname_is_indexed(clients):
    assert clients["bellen_last_names"] == {"milan bellen"}
