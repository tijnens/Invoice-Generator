import datetime
import os.path
import os
import sys

import google.auth.exceptions
from docx import Document
from docx.shared import Inches
from docx.text.paragraph import Paragraph
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from util import load_client_database, GoogleCalendarEvent, Client
from constants import (BTW, KVK_NR, BSN, NIP_REG_NUM, AGB_CODE, ADDRESS, POSTAL_CODE, INVOICE_HEADING,
                       INVOICE_SIGNATURE, INVOICE_METADATA_TEMPLATE, ADDRESSEE_DATA_TEMPLATE, THERAPIST_DATA_TEMPLATE, 
                       MONTH_NAMES_DUTCH, CONSULTATION_OVERVIEW_HEADER, CONSULTATION_OVERVIEW_TAB_STOPS, BANK_ACT_NO, 
                       MOCK_CALENDAR_LOC)

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


# Determine the base path where the script is running. This is needed to reference files in the packaged version
if getattr(sys, 'frozen', False):
    # The script is running in a bundled/executable form
    base_path = sys._MEIPASS
else:
    # The script is running in a normal Python environment
    base_path = os.path.dirname(os.path.abspath(__file__))


def format_invoice_number(client_id: str, invoice_date: datetime):
    return f'{client_id}{invoice_date.strftime("%d%m%Y")}'


def format_invoice_date(invoice_date: datetime):
    return f'{invoice_date.day} {MONTH_NAMES_DUTCH[invoice_date.month].lower()} {invoice_date.year}'


def create_docx(client: Client, invoice_date: datetime, consultations_overview_rows: list[tuple],
                total_price: str) -> Document:
    doc = Document()

    invoice_number = format_invoice_number(client.invoice_id, invoice_date)
    left_margin = doc.sections[0].left_margin.inches
    right_margin = doc.sections[0].right_margin.inches
    full_width = doc.sections[0].page_width.inches

    heading = doc.add_heading(INVOICE_HEADING + '\n', 1)

    therapist_data_paragraph = doc.add_paragraph()
    therapist_data = THERAPIST_DATA_TEMPLATE.format(
        address=ADDRESS,
        postal_code=POSTAL_CODE,
        btw=BTW,
        kvk=KVK_NR,
        bsn=BSN,
        nip=NIP_REG_NUM,
        agb=AGB_CODE
    )
    therapist_data_paragraph.add_run(therapist_data)

    invoice_metadata_paragraph = doc.add_paragraph()
    addressee = client.invoice_addressee if client.invoice_addressee else client.full_name
    invoice_metadata = INVOICE_METADATA_TEMPLATE.format(
        invoice_no=invoice_number,
        invoice_date=format_invoice_date(invoice_date)
    )
    invoice_metadata_paragraph.add_run(invoice_metadata)

    client_data_paragraph = doc.add_paragraph()
    client_data = ADDRESSEE_DATA_TEMPLATE.format(
        addressee=addressee,
        street=client.address,
        postal_code=client.postal_code,
        city=client.city
    )
    client_data_paragraph.add_run(client_data)

    consultations_overview_paragraph = doc.add_paragraph()
    create_consultations_overview(consultations_overview_rows, total_price, consultations_overview_paragraph)

    signature_paragraph = doc.add_paragraph()
    signature_paragraph.add_run(INVOICE_SIGNATURE.format(bank_act_no=BANK_ACT_NO, invoice_no=invoice_number))

    return doc


def create_consultations_overview(consultations_overview_rows: list[tuple], total_price: str, paragraph: Paragraph):
    """
    :param client_consultations_data: List of dicts with 'date', 'duration' and 'amount' keys for each consultation.
    :param paragraph: The docx Paragraph object pointing to the consultation overview paragraph.
    :return: None
    """

    tabs = paragraph.paragraph_format.tab_stops
    for tab_stop in CONSULTATION_OVERVIEW_TAB_STOPS:
        tabs.add_tab_stop(Inches(tab_stop))

    # Add the header
    add_row_to_consultations_overview(CONSULTATION_OVERVIEW_HEADER, paragraph)

    # Add the consultations
    for row in consultations_overview_rows:
        add_row_to_consultations_overview(row, paragraph)

    # Add
    add_row_to_consultations_overview(('', '', '______________+'), paragraph)
    add_row_to_consultations_overview(('', 'Totaal te betalen:', total_price), paragraph)


def add_row_to_consultations_overview(row_fields: tuple[str], paragraph: Paragraph):
    paragraph.add_run(row_fields[0])
    for field in row_fields[1:]:
        paragraph.add_run('\t' + field)
    paragraph.add_run('\n')


def match_event_title_to_client_names(event: GoogleCalendarEvent, client_data: dict):
    """Iterate over all clients in the client database, and if one of their names matches the event title, add the event
    to the client's matched_calendar_events, and return the client.
    Matching is done on the following criteria

    Checks if the event title matches a client name, meaning it should appear on the invoice. This is decided based
    on these criteria:
        - The appointment title does not end with 'bellen' (these are free intro chats), unless the client's last name
          is 'Bellen' (bellen_match)
        - It starts with the full name of a client (= exact match)
        - It starts with only the first name of a client, and no other client has this first name (= exact match)
        - It starts with only the first name of a client, and one or more other clients have this name (= fuzzy match)
    When a match is found a client, the GoogleCalendarEvent object is added to the Client object's
    matched_calendar_events list. A list of Client objects that match the event is returned. Usually this will be a list
    of only one Client, but if there are multiple fuzzy matches, multiple Clients are returned.
    """
    event_title = event.sanitized_title
    matched_clients = []
    # If this is a 'bellen' appointment, and there's no client with 'Bellen' as last name, it is not a billable session
    if (event_title.split()[-1] == 'bellen'
            and not any(n in event_title for n in client_data['bellen_last_names'])):
        return matched_clients  # Return early

    # Check if any of the clients' names match the appointment title.
    client: Client
    for client in client_data['clients'].values():
        match_type = None
        full_name = client.full_name
        full_name_match = event_title.startswith(full_name.lower())
        # If client's full name matches, it's an exact match: we're sure the appointment title refers to this client
        if full_name_match:
            match_type = 'exact_match'
            # If the client's last name is 'bellen', we set match type to 'bellen_match' so we can inform the user that
            # this consultation was included based on that.
            if full_name.lower() in client_data['bellen_last_names'] and event_title == full_name.lower():
                match_type = 'bellen_match'
        # Else if only client's first name matches:
        elif event_title.startswith(client.first_name.lower()):
            # If this client is the only one with this name, it's also an exact match
            if client.full_name.lower() not in client_data['duplicate_first_names']:
                match_type = 'exact_match'
            # If only first name matches, and this client is not the only one with this first name, and no other
            # client's full name matches, we have a fuzzy match. This event could point to multiple clients, we
            # can't know for sure which one. E.g. if the event is titled 'Mark' and we have 'Mark A' and 'Mark B' in
            # our client database, we can't know which Mark this event points to, so we fuzzy match it to both.
            elif not any(event_title.startswith(full_name) for full_name in client_data['duplicate_first_names']):
                match_type = 'fuzzy_match'
                matched_clients.append(client)
        else:  # If there's no match even for the first name, continue to next client.
            continue
        # If we've found a match between the event title and the client, add the event to the client's matched events
        if match_type is not None:
            client.matched_calendar_events[event.id] = {'event': event, 'match_type': match_type}
            if match_type in ('exact_match', 'bellen_match'):
                matched_clients.append(client)
                return matched_clients  # Return immediately if we have an exact match.
    return matched_clients


def get_credentials_from_oauth_flow():
    flow = InstalledAppFlow.from_client_secrets_file(os.path.join(base_path, "credentials.json"), SCOPES)
    creds = flow.run_local_server(port=0)
    return creds


def check_credentials(app_data_loc):
    creds = None
    token_loc = os.path.join(app_data_loc, 'token.json')
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(token_loc):
        creds = Credentials.from_authorized_user_file(token_loc, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except google.auth.exceptions.RefreshError:
                creds = get_credentials_from_oauth_flow()
        else:
            creds = get_credentials_from_oauth_flow()
        # Save the credentials for the next run
        with open(token_loc, "w") as token:
            token.write(creds.to_json())
    return creds


def sanitize_event_title(event_title):
    """Remove duplicate whitespaces, strip surrounding whitespace, and make lowercase."""
    while '  ' in event_title:
        event_title = event_title.replace('  ', ' ')
    return event_title.strip().lower()


def get_start_and_end_datetime_from_calendar_event(event):
    start = create_datetime_from_calendar_event_date(event['start'])
    end = create_datetime_from_calendar_event_date(event['end'])
    return start, end


def create_datetime_from_calendar_event_date(date_dict: dict) -> datetime:
    """Creates a datetime object from a Google Calendar event 'start' or 'end' entry."""
    # If there's a 'dateTime' entry, this means a specific time was set for the event. This will be in %Y-%m-%dT%H:%M:%S
    # format
    if 'dateTime' in date_dict:
        datetime_obj = datetime.datetime.strptime(
            date_dict['dateTime'].replace('Z', '+00:00'), '%Y-%m-%dT%H:%M:%S%z'
        )
    # If no specific time was set for the event, it will be in %Y-%m-%d format
    else:
        datetime_obj = datetime.datetime.strptime(date_dict['date'], '%Y-%m-%d')
    return datetime_obj


def pull_calendar_data(start_date, end_date, client_data, creds, demo=False):
    try:
        if not demo:
            service = build("calendar", "v3", credentials=creds)

            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=start_date,
                    timeMax=end_date,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        else:
            import json

            with open(MOCK_CALENDAR_LOC, "r") as f:
                events_result = json.load(f)

        events = events_result.get("items", [])

        if not events:
            print("No upcoming events found.")
            return

        billable_clients = []

        for event in events:
            event_start, event_end = get_start_and_end_datetime_from_calendar_event(event)
            event_object = GoogleCalendarEvent(title=event['summary'], id=event['id'], link=event['htmlLink'],
                                               start_date=event_start, end_date=event_end)
            matched_clients = match_event_title_to_client_names(event_object, client_data)
            billable_clients.extend([client for client in matched_clients if client not in billable_clients])

        return billable_clients

    except HttpError as error:
        print(f"An error occurred: {error}")


def generate_invoice(client: Client, invoice_date: datetime, consultations_overview_rows: list[tuple], total_price: str,
                     file_path: str) -> None:
    invoice_doc = create_docx(client, invoice_date, consultations_overview_rows, total_price)
    invoice_doc.save(file_path)
