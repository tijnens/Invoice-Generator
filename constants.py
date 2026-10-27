BTW = '123456789A01'
KVK_NR = '12345678'
BSN = '123456789'
NIP_REG_NUM = '123456'
AGB_CODE = '12345678'
ADDRESS = 'Straatnaam 1'
POSTAL_CODE = '1234AA Stad'
BANK_ACT_NO = 'NL01INGB1234567'
HOURLY_RATE_EUR = 100

INVOICE_HEADING = "PSYCHOLOGISCHE PRAKTIJK"
THERAPIST_DATA_TEMPLATE = """{address}
{postal_code}
BTW: {btw}
KvK: {kvk}
BSN: {bsn}
Nip registratienummer: {nip}
AGB code: {agb}"""

INVOICE_METADATA_TEMPLATE = "Factuurkenmerk: {invoice_no}\nFactuurdatum: {invoice_date}"

ADDRESSEE_DATA_TEMPLATE = "{addressee}\n{street}\n{postal_code}\n{city}"

INVOICE_SIGNATURE = """Graag binnen 14 dagen overmaken naar:
{bank_act_no} t.n.v. T Rapeut
Betalingskenmerk: {invoice_no}
Als het betalingskenmerk niet geaccepteerd wordt kunt u het in de omschrijving zetten."""

CONSULTATION_OVERVIEW_HEADER = ('Datum consult', 'Aantal uur', 'Prijs')
CONSULTATION_OVERVIEW_TAB_STOPS = (3.5, 5)

MONTH_NAMES_DUTCH = {
    1: 'Januari',
    2: 'Februari',
    3: 'Maart',
    4: 'April',
    5: 'Mei',
    6: 'Juni',
    7: 'Juli',
    8: 'Augustus',
    9: 'September',
    10: 'Oktober',
    11: 'November',
    12: 'December'
}

DEMO_CLIENTS_DATA_LOC = './demo/clientsdata_demo.csv'

MOCK_CALENDAR_LOC = './demo/mock_calendar.json'
