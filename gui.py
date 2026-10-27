import os
import yaml
import tkinter as tk
from docxtopdf import convert
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timedelta

from constants import MONTH_NAMES_DUTCH, DEMO_CLIENTS_DATA_LOC
from calendar_processor import pull_calendar_data, generate_invoice, check_credentials
from util import (load_client_database, open_url, validate_date_string, GoogleCalendarEvent,
                  transform_user_dates_to_google_calendar_api_dates, Client)


class InvoiceGenerator(tk.Tk):
    CACHE_VARS = ('client_data_csv_filepath',)
    CACHE_FILE = 'cache.yaml'
    app_data_loc = os.path.join(os.getenv('APPDATA'), 'UurtjeFactuurtje')

    def __init__(self, demo=False):
        super().__init__()
        self.demo = demo
        self.title(
            "Invoice Generator [DEMO MODE]" if self.demo else "Invoice Generator"
        )
        self._cache_file_loc = os.path.join(self.app_data_loc, self.CACHE_FILE)
        self.invoice_date = datetime.now()
        self.default_dates = self._get_default_start_and_end_dates()
        if self.demo:
            self.default_dates = (
                datetime(2026, 10, 1),
                datetime(2026, 10, 31)
            )
        self.billed_month = None
        self.date_format = "%d-%m-%Y"
        self.client_data_csv_filepath = None if not self.demo else DEMO_CLIENTS_DATA_LOC
        self.client_data = None
        self.tabs = None
        self.start_date_entry = None
        self.end_date_entry = None
        self.start_date_error = None
        self.end_date_error = None
        self.select_csv_file_button = None
        self.selected_csv_file_path_label = None
        self.process_button = None
        self._setup_app_data_dir()
        self._read_from_cache()
        self._create_homescreen_widgets()

    @property
    def cache_file_loc(self):
        return os.path.join(self.app_data_loc, self.CACHE_FILE)

    def _get_default_start_and_end_dates(self):
        """Set default datetimes for the start and end date of the invoice period. It defaults to the start and
        end days of the previous month. If we are currently on the last day of the month, it defaults to the start and
        end days of the current month.
        """
        # If we're not on the last day of the current month, the default dates should be the start and end of the
        # previous month
        if self.invoice_date.month == (self.invoice_date + timedelta(days=1)).month:
            year = self.invoice_date.year
            month = self.invoice_date.month - 1 if self.invoice_date.month != 1 else 12
            start_day = 1
            # Subtract one day from the first day of the current month to get the last day of the previous month
            end_day = (datetime(year=year, month=self.invoice_date.month, day=1) - timedelta(days=1)).day
            default_start_date = datetime(year=year, month=month, day=start_day)
            default_end_date = datetime(year=year, month=month, day=end_day)
        # If we are on the last day of the month, the default dates are the start and end of this month
        else:
            default_start_date = datetime(year=self.invoice_date.year, month=self.invoice_date.month, day=1)
            default_end_date = self.invoice_date
        return default_start_date, default_end_date

    def _setup_app_data_dir(self, app_data_loc=None):
        """Create a directory for app data if it doesn't exist yet. Also create an empty cache.yaml if it doesn't exist
        yet.
        """
        if app_data_loc is not None:
            self.app_data_loc = app_data_loc
        if not os.path.exists(self.app_data_loc):
            os.mkdir(self.app_data_loc)
            if not os.path.exists(self.cache_file_loc):
                with open(self.cache_file_loc, 'w') as f:
                    yaml.dump({}, f)

    def _load_cache(self):
        if os.path.exists(self.cache_file_loc):
            with open(self.cache_file_loc, 'r') as f:
                loaded = yaml.safe_load(f)
            return loaded
        return {}

    def _save_cache(self, cache_dict):
        with open(self.cache_file_loc, 'w') as f:
            yaml.dump(cache_dict, f)

    def _read_from_cache(self):
        loaded_cache = self._load_cache()
        for variable in self.CACHE_VARS:
            if variable in loaded_cache:
                setattr(self, variable, loaded_cache[variable])

    def _write_var_to_cache(self, variable, value):
        loaded_cache = self._load_cache()
        loaded_cache[variable] = value
        self._save_cache(loaded_cache)

    def _create_homescreen_widgets(self):
        # Create a Notebook widget to be able to display an interface with tabs
        self.tabs = ttk.Notebook(self)
        self.tabs.grid(row=0, column=0, sticky="nsew")

        # Add 'Home' tab
        home_tab = ttk.Frame(self.tabs)
        self.tabs.add(home_tab, text='Home')

        # Add instructions text
        self._create_home_tab_instructions(home_tab)

        # Create entry fields for the start and end date of the invoice period
        self._create_date_entry_fields(home_tab)

        # Create a button to select a CSV file with client data
        self._create_csv_file_selection_button(home_tab)

        # Create a button for pulling Google Calendar data
        self._create_pull_google_calendar_data_button(home_tab)

    @staticmethod
    def _create_home_tab_instructions(home_tab):
        tk.Label(
            home_tab,
            text='Vul de begin- en einddatum van de factuurperiode in, selecteer een CSV bestand met cliëntgegevens, en'
                 ' klik op \'Google Calendar afspraken verwerken\'.'
        ).grid(row=0, column=0, padx=10, pady=10, sticky='w')

    def _create_date_entry_fields(self, tab):
        # Add date entry fields to the tab
        tk.Label(tab, text="Begindatum (DD-MM-YYYY):").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.start_date_entry = tk.Entry(tab)
        self.start_date_entry.grid(row=1, column=0, padx=200, pady=10, sticky='w')
        self.start_date_entry.insert(0, self.default_dates[0].strftime('%d-%m-%Y'))
        # Error label for start date
        self.start_date_error = tk.Label(tab, text="", fg="red")
        self.start_date_error.grid(row=1, column=0, padx=325, pady=10, sticky="w")

        tk.Label(tab, text="Einddatum (DD-MM-YYYY):").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.end_date_entry = tk.Entry(tab)
        self.end_date_entry.grid(row=2, column=0, padx=200, pady=10, sticky='w')
        self.end_date_entry.insert(0, self.default_dates[1].strftime('%d-%m-%Y'))
        # Error label for end date
        self.end_date_error = tk.Label(tab, text="", fg="red")
        self.end_date_error.grid(row=2, column=0, padx=325, pady=10, sticky="w")

    def _create_csv_file_selection_button(self, tab):
        self.select_csv_file_button = tk.Button(tab, text="Selecteer cliëntgegevens",
                                                command=self.on_select_csv_file_click)
        self.select_csv_file_button.grid(row=3, column=0, padx=10, pady=10, sticky='w')

        # Label to display the selected file path
        if self.client_data_csv_filepath is not None and os.path.exists(self.client_data_csv_filepath):
            csv_path_label_text = self.client_data_csv_filepath
        else:
            csv_path_label_text = "Geen bestand geselecteerd"
        self.selected_csv_file_path_label = tk.Label(tab, text=csv_path_label_text)
        self.selected_csv_file_path_label.grid(row=3, column=0, padx=200, pady=10, sticky="w")

    def _create_pull_google_calendar_data_button(self, tab):
        tk.Button(
            tab, text="Google Calendar afspraken verwerken",
            command=self._on_pull_data_button_click
        ).grid(row=4, column=0, padx=10, pady=10, sticky='w')

    def _on_pull_data_button_click(self):
        # Get start and end date given by user (or defaults if not given)
        start_date = self.start_date_entry.get()
        end_date = self.end_date_entry.get()

        # Validate date input and selected CSV file
        valid_dates = True
        valid_csv_selected = True
        if not validate_date_string(start_date, self.date_format):
            self.start_date_error.config(text="Onjuiste datum")
            valid_dates = False
        if not validate_date_string(end_date, self.date_format):
            self.end_date_error.config(text="Onjuiste datum")
            valid_dates = False
        if self.client_data_csv_filepath is None:
            messagebox.showwarning("Geen CSV geselecteerd", "Selecteer een CSV bestand met cliëntendata.")
            valid_csv_selected = False

        # If valid:
        if valid_dates and valid_csv_selected:
            self.start_date_error.config(text="")
            self.end_date_error.config(text="")
            self._pull_calendar_data(start_date, end_date)

    def _pull_calendar_data(self, start_date, end_date):
        creds = None if self.demo else check_credentials(self.app_data_loc)
        self.billed_month = MONTH_NAMES_DUTCH[datetime.strptime(start_date, self.date_format).month]
        self._load_selected_csv_file()
        if self.client_data is not None:
            # Transform start and end date to the format expected by Google Calendar API
            start_date, end_date = transform_user_dates_to_google_calendar_api_dates(start_date, end_date)
            billable_clients = pull_calendar_data(start_date, end_date, self.client_data, creds, demo=self.demo)
            self._create_tabbed_interface_for_consultations_per_client(billable_clients)

    @staticmethod
    def create_single_consultation_string_for_checkbox(event: GoogleCalendarEvent, client: Client, match_type: str):
        date = event.start_date.strftime('%Y-%m-%d')
        price = client.calculate_price_for_event(event.id)
        return f'Datum: {date}, Duur: {event.duration_hours} uur, Prijs: € {price:.2f}'

    def _create_tabbed_interface_for_consultations_per_client(self, billable_clients: set[Client]):
        # Clear any existing tabs except 'home_tab'
        for tab in self.tabs.tabs():
            if self.tabs.tab(tab, "text") == 'Home':
                continue
            self.tabs.forget(tab)
        for client in sorted(billable_clients):
            tab = ttk.Frame(self.tabs)
            self.tabs.add(tab, text=client.full_name)
            instructions_label = tk.Label(
                tab, text=f'Overzicht van de gevonden Calendar afspraken voor {client.full_name}.\nVink afspraken aan '
                          f'of uit om ze wel of niet in de factuur op te nemen.',
                anchor='w', justify='left'
            )
            instructions_label.pack(side='top', anchor='w', pady=10, padx=10)

            # Frame for checkboxes and labels
            checkbox_frame = ttk.Frame(tab)
            checkbox_frame.pack(fill='x', padx=10, pady=5)
            checkbox_states = []  # Store (IntVar, GoogleCalendarEvent pairs) to track checkbox states
            for matched_event_dict in client.matched_calendar_events.values():
                event = matched_event_dict['event']
                match_type = matched_event_dict['match_type']
                frame = ttk.Frame(checkbox_frame)
                frame.pack(anchor="w", pady=2, fill='x')

                display_text = self.create_single_consultation_string_for_checkbox(event, client, match_type)
                var = tk.IntVar(value=1)  # Default to checked
                chk = tk.Checkbutton(frame, text=display_text, variable=var)
                chk.pack(side="left")

                # Create a button to open the event in Google Calendar
                link_button = ttk.Button(frame, text='Open in Calendar', command=lambda u=event.link: open_url(u))
                link_button.pack(side='left', padx=(5, 0))

                checkbox_states.append((var, event))

                warning_label = tk.Label(frame, fg='red')
                warning_label.pack(side='left', padx=(5, 0))

                if match_type == 'fuzzy_match':
                    var.set(0)
                    warning_label.config(text=f'!! Calendar afspraak heet \'{event.title}\'. Hoort deze afspraak bij '
                                              f'{client.full_name}?')
                elif match_type == 'bellen_match':
                    warning_label.config(text=f'!! Calendar afspraak heet \'{event.title}\', en wordt gefactureerd '
                                              f'omdat de achternaam van de cliënt \'Bellen\' is. Klopt dit?')

            # Frame for the generate button
            button_frame = ttk.Frame(tab)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))  # Adjusted padding

            # Button to process checked data
            generate_docx_button = tk.Button(
                button_frame, text="Maak factuur (docx)",
                command=lambda c=client, v=checkbox_states: self.on_generate_docx_button_click(c, v)
            )
            generate_docx_button.pack(padx=10, side='left')

            # Button to process checked data
            generate_pdf_button = tk.Button(
                button_frame, text="Maak factuur (pdf)",
                command=lambda c=client, v=checkbox_states: self.on_generate_pdf_button_click(c, v)
            )
            generate_pdf_button.pack(padx=10, side='left')

    def on_generate_docx_button_click(self, client: Client, checkbox_states: list[tuple[tk.IntVar | GoogleCalendarEvent]]) -> None:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word Documents", "*.docx"), ("All Files", "*.*")],
            initialfile=f"{client.full_name.replace(' ', '-')}_"
                        f"Factuur_{self.billed_month}_{self.invoice_date.year}.docx"
        )
        self.generate_docx(client, checkbox_states, file_path)
        tk.messagebox.showinfo("", f"Bestand opgeslagen als {file_path}")

    def on_generate_pdf_button_click(self, client: Client, checkbox_states: list[tuple[tk.IntVar | GoogleCalendarEvent]]) -> None:
        file_name = f"{client.full_name.replace(' ', '-')}_Factuur_{self.billed_month}_{self.invoice_date.year}.pdf"
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Documents", "*.pdf"), ("All Files", "*.*")],
            initialfile=file_name
        )
        temp_docx_file_path = os.path.join(self.app_data_loc, file_name.replace('.pdf', '.docx'))
        self.generate_docx(client, checkbox_states, temp_docx_file_path)
        convert(temp_docx_file_path, file_path)

        os.remove(temp_docx_file_path)

        tk.messagebox.showinfo("", f"Bestand opgeslagen als {file_path}")

    def generate_docx(self, client: Client, checkbox_states: list[tuple[tk.IntVar | GoogleCalendarEvent]], file_path):
        # Use only the consultations that have their checkbox checked
        filtered_events_list = [event for checkbox, event in checkbox_states if bool(checkbox.get())]
        total_price = 0
        consultations_overview_rows = []
        # Create list of (date, duration, price) rows per event that will be displayed on the invoice.
        for event in filtered_events_list:
            price = client.calculate_price_for_event(event.id)
            consultations_overview_rows.append(
                (event.start_date.strftime('%d-%m-%Y'), str(event.duration_hours), f'€ {price:.2f}')
            )
            total_price += price  # also calculate total price while we're at it
        total_price = f'€ {total_price:.2f}'

        generate_invoice(client, self.invoice_date, consultations_overview_rows, total_price,
                         file_path)

    def on_select_csv_file_click(self):
        # Open a file dialog to select a CSV file
        file_path = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("snarfs", ".txt"), ("XSLX files", ".xlsx")],
            title="Select a CSV file"
        )

        if file_path:  # Check if a file was selected
            self.client_data_csv_filepath = file_path
            self.selected_csv_file_path_label.config(text=file_path)  # Update label with file path
            self._write_var_to_cache('client_data_csv_filepath', file_path)

    def _load_selected_csv_file(self):
        # Read and process the CSV file
        try:
            self.client_data = load_client_database(self.client_data_csv_filepath)
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while reading the CSV file: {e}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate invoices from Google Calendar appointments."
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run with fictional calendar data without Google authentication."
    )
    args = parser.parse_args()

    app = InvoiceGenerator(demo=args.demo)
    app.mainloop()
