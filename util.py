import csv
import webbrowser
import uuid
import pandas as pd

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import chardet


def read_datasheet(file_path: str) -> pd.DataFrame:
    """Accepts an .xlsx file, or a comma-separated .csv file, or a semicolon-separated .csv file."""
    if file_path.endswith('.xlsx'):  # If it's an xlsx file, no hassle. Read and return.
        df = pd.read_excel(file_path, dtype=str)
    else:  # Otherwise, do some detection of encoding and delimiters to safely read the file
        # Read a small portion of the file to detect encoding
        with open(file_path, 'rb') as file:
            detected_encoding = chardet.detect(file.read(10000))  # Read first 10KB
        encoding = detected_encoding['encoding']
        # Now read file with detected encoding, and try to detect the delimiter
        with open(file_path, 'r', encoding=encoding) as file:
            sample = file.read(1024)
            dialect = csv.Sniffer().sniff(str(sample))
            suspected_delimiter = dialect.delimiter
        delims = {suspected_delimiter, ',', ';'}
        for delimiter in delims:
            df = pd.read_csv(file_path, delimiter=delimiter, dtype=str, encoding=encoding, quotechar='"')
            if 'first name' in df.columns:  # Sanity check to see if we read with the right delimiter
                break
    df = df.fillna('')
    return df


def load_client_database(file_path):
    """Loads the csv at file_path into a Dict with client names as keys and a {address: ADDRESS, rate: RATE}
    dictionary as values. I.e. it maps each client name to their address and hourly rate.
    """
    client_data = {
        'clients': {},
        'duplicate_first_names': set(),
        'bellen_last_names': set()
    }
    dataframe = read_datasheet(file_path)
    for index, row in dataframe.iterrows():
        name = row['first name'].strip()  # Use the 'first name' field as the key
        full_name = f'{name} {row["last name"].strip()}'

        # Keep track of duplicate first names. If a Google Calendar event's title is just the first name of a
        # client, and there are multiple clients with this first name, we need to inform the user that the script
        # cannot determine which client this event refers to.
        for c in client_data['clients'].values():
            if name.casefold() == c.first_name.casefold():
                client_data['duplicate_first_names'].add(c.full_name.lower())
                client_data['duplicate_first_names'].add(full_name.lower())

        # Also keep track of last names that are 'bellen'. A Google Calendar event title that ends with 'bellen' is
        # normally excluded from the invoice, because this indicates a free intro chat over the phone. If a client's
        # last name is bellen, however, it should be included, and the user should be notified.
        if row['last name'].strip().lower() == 'bellen':
            client_data['bellen_last_names'].add(full_name.lower())

        client = Client(
            first_name=name,
            last_name=row['last name'].strip(),
            address=row['address'].strip(),
            postal_code=row['postal code'].strip(),
            city=row['city'].strip(),
            invoice_addressee=row['to'].strip(),
            invoice_id=row['id'].strip(),
            rate=float(row['rate'].strip())
        )
        # Create a nested dictionary for each entry
        client_data['clients'][client.id] = client

    return client_data


def open_url(url):
    webbrowser.open(url)


def validate_date_string(date_string, date_format):
    try:
        datetime.strptime(date_string, date_format)
        return True
    except ValueError:
        return False


def transform_user_dates_to_google_calendar_api_dates(user_start_date, user_end_date):
    # Interpret user-selected calendar dates in the Netherlands, accounting for DST.
    # Google Calendar's timeMax is exclusive, so use midnight after the end date.
    local_tz = ZoneInfo("Europe/Amsterdam")
    start_local = datetime.strptime(user_start_date, "%d-%m-%Y").replace(tzinfo=local_tz)
    end_local = (datetime.strptime(user_end_date, "%d-%m-%Y") + timedelta(days=1)).replace(tzinfo=local_tz)
    return (start_local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            end_local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"))


@dataclass(slots=True)
class GoogleCalendarEvent:
    title: str
    id: str
    link: str
    start_date: datetime
    end_date: datetime
    duration_hours: float = field(init=False)
    sanitized_title: str = field(init=False)

    def __post_init__(self):
        self.duration_hours = (self.end_date - self.start_date).total_seconds() / 3600
        self.sanitized_title = self._sanitize_event_title(self.title)

    @staticmethod
    def _sanitize_event_title(event_title):
        """Remove duplicate whitespaces, strip surrounding whitespace, and make lowercase. This makes it easier to match
        the event title to the client names.
        """
        while '  ' in event_title:
            event_title = event_title.replace('  ', ' ')
        return event_title.strip().lower()


@dataclass(slots=True)
class Client:
    id: uuid.UUID = field(default_factory=uuid.uuid4, init=False)
    first_name: str
    last_name: str
    address: str
    postal_code: str
    city: str
    invoice_addressee: str
    invoice_id: str
    rate: float = 100
    full_name: str = field(init=False)
    matched_calendar_events: dict[str, dict[str, GoogleCalendarEvent | str]] = field(default_factory=dict)

    def __post_init__(self):
        self.full_name = f'{self.first_name} {self.last_name}'.strip()

    def __lt__(self, other):
        return self.full_name < other.full_name

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, Client):
            return self.id == other.id
        return False

    def calculate_price_for_event(self, event_id):
        if event_id not in self.matched_calendar_events:
            return None
        return float(self.rate * self.matched_calendar_events[event_id]['event'].duration_hours)
