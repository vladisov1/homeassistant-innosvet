"""Read-only additional financial data from innosvět.

Only the pre-existing authenticated Playwright page is used. No writes, no
payment-form interactions, and no raw portal responses stored or logged.
"""
import json
import math
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

HOST = 'innosvet.innogy.cz'
BASE = 'https://' + HOST
CURRENCY = re.compile(r'((?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?:[,\.]\d{1,2})?)\s*Kč', re.I)
DATES = re.compile(r'\b([0-3]?\d)\.([01]?\d)\.(20\d{2})\b')
PERIOD_HEADER = re.compile(r'\bOd\s+([0-3]?\d)\.\s*([01]?\d)\.\s*(20\d{2})', re.I)


def amount(text):
    raw = text.replace('\u00a0', '').replace('\u202f', '').replace(' ', '').replace(',', '.')
    try:
        out = float(raw)
        if not math.isfinite(out) or out < 0 or out > 1e9:
            raise ValueError('amount range')
        return round(out, 2)
    except (TypeError, ValueError):
        raise ValueError('bad amount')


def money(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('bad numeric value')
    if value < 0 or value > 1e9:
        raise ValueError('number outside safe range')
    return round(float(value), 2)


def parse_payments_row(text):
    """Parse only trusted numeric/date/status fragments; no names or addresses."""
    normalized = ' '.join(text.split())
    match = DATES.search(normalized)
    matches = CURRENCY.findall(normalized)
    if not match or not matches:
        return None
    try:
        due = date(int(match[3]), int(match[2]), int(match[1]))
        prescribed = amount(matches[0])
    except ValueError:
        return None
    low = normalized.casefold()
    if re.search(r'\buhrazena\b|\buhrazeno\b', low):
        status = 'uhrazena'
        outstanding = 0.0
    elif 'zbývá uhradit' in low:
        status = 'castecne_uhrazena'
        if len(matches) < 2:
            return None  # Do not infer partial payment without its amount
        try:
            outstanding = amount(matches[1])
        except ValueError:
            return None
    elif 'po splatnosti' in low:
        status = 'po_splatnosti'
        outstanding = prescribed
    elif 'čeká na platbu' in low:
        status = 'ceka_na_platbu'
        outstanding = prescribed
    elif 'předpis zálohy' in low:
        status = 'predpis'
        outstanding = prescribed
    else:
        return None
    if outstanding > prescribed:
        return None
    return {'datum_splatnosti': due.isoformat(), 'predpis_kc': prescribed,
            'uhrazeno_kc': round(prescribed - outstanding, 2),
            'zbyva_kc': outstanding, 'stav': status}


def read_payments(page, contract_id):
    page.goto(BASE + '/platby/zalohy?contractid=' + contract_id,
              wait_until='domcontentloaded', timeout=60000)
    if urlparse(page.url).hostname != HOST or urlparse(page.url).path != '/platby/zalohy':
        raise RuntimeError('payments page inaccessible')
    page.locator('table tr').first.wait_for(timeout=20000)
    texts = page.locator('table tr').all_text_contents()
    found = {}
    for text in texts:
        item = parse_payments_row(text)
        if item:
            found[item['datum_splatnosti']] = item
    if not found:
        raise RuntimeError('no validated payment rows')
    rows = sorted(found.values(), key=lambda x: x['datum_splatnosti'])
    today = datetime.now(ZoneInfo('Europe/Prague')).date().isoformat()
    future = [x for x in rows if x['datum_splatnosti'] >= today]
    if not future:
        raise RuntimeError('no future installment records')
    next_due = next((x for x in future if x['zbyva_kc'] > 0), None)
    # Use the first future scheduled amount (not an average, not an assumption).
    return {
        'mesicni_zaloha_kc': future[0]['predpis_kc'],
        'nejblizsi_neuhrazena_splatnost': next_due['datum_splatnosti'] if next_due else None,
        'nejblizsi_zbyva_kc': next_due['zbyva_kc'] if next_due else 0.0,
        'budouci_zbyva_kc': round(sum(x['zbyva_kc'] for x in future), 2),
        'platebni_kalendar': rows,
    }


def _parse_month_start(visible):
    m = PERIOD_HEADER.search(' '.join(visible.split()))
    if not m:
        return None
    try:
        return date(int(m[3]), int(m[2]), int(m[1]))
    except ValueError:
        return None



MONTH_NAMES = {
    'leden': 1, 'ledna': 1, 'unor': 2, 'unora': 2, 'brezen': 3, 'brezna': 3,
    'duben': 4, 'dubna': 4, 'kveten': 5, 'kvetna': 5, 'cerven': 6, 'cervna': 6,
    'cervenec': 7, 'cervence': 7, 'srpen': 8, 'srpna': 8, 'zari': 9, 'rijen': 10,
    'rijna': 10, 'listopad': 11, 'listopadu': 11, 'prosinec': 12, 'prosince': 12,
}


def _normalize_month_name(value):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFD', str(value).lower())
                   if unicodedata.category(c) != 'Mn')


def _parse_month_field(value, year_hint=None):
    """Parse month/year labels only, never guess from numeric amounts."""
    if value is None or isinstance(value, bool):
        return None
    raw = str(value).strip()
    if not raw or len(raw) > 100:
        return None
    # Exact year-month, YYYY-MM-DD, DD.MM.YYYY, MM/YYYY, and JS/ISO stamps.
    m = re.search(r'(?<!\d)(20\d{2})[-/.]([01]?\d)(?:[-/.]([0-3]?\d))?(?!\d)', raw)
    if m:
        y, mo = int(m[1]), int(m[2])
        if 1 <= mo <= 12:
            return date(y, mo, 1)
    m = re.search(r'(?<!\d)([0-3]?\d)\.\s*([01]?\d)\.\s*(20\d{2})(?!\d)', raw)
    if m and 1 <= int(m[2]) <= 12:
        return date(int(m[3]), int(m[2]), 1)
    m = re.search(r'(?<!\d)([01]?\d)[/. -](20\d{2})(?!\d)', raw)
    if m and 1 <= int(m[1]) <= 12:
        return date(int(m[2]), int(m[1]), 1)
    y = None
    try:
        if year_hint is not None and re.fullmatch(r'20\d{2}', str(year_hint).strip()):
            y = int(str(year_hint).strip())
    except (TypeError, ValueError):
        pass
    if y is not None:
        if re.fullmatch(r'0?[1-9]|1[0-2]', raw):
            return date(y, int(raw), 1)
        for month_name, month in MONTH_NAMES.items():
            if month_name in _normalize_month_name(raw):
                return date(y, month, 1)
    return None


def _resolve_cost_graph_start(payload, page):
    """Prefer AJAX record dates over visible body text; require 13 consecutive months."""
    # Try each record's own month. One well-formed dated record is enough
    # only if every other parseable dated record agrees with the sequence.
    candidates = []
    for i, record in enumerate(payload):
        hint = record.get('Year')
        parsed = None
        for field in ('Date', 'Period'):
            parsed = _parse_month_field(record.get(field), hint)
            if parsed is not None:
                break
        if parsed is not None:
            start_month_index = parsed.year * 12 + parsed.month - 1 - i
            candidates.append(start_month_index)
    if candidates and len(set(candidates)) == 1:
        idx = candidates[0]
        return date(idx // 12, idx % 12 + 1, 1), 'json'
    if candidates and len(set(candidates)) > 1:
        raise RuntimeError('graf_obdobi_nejednoznacne')

    # Visual period labels might be in SVG / embedded HTML, not body.innerText.
    for extractor in (
        lambda: page.locator('body').inner_text(timeout=10000),
        lambda: page.content(),
    ):
        try:
            result = _parse_month_start(extractor())
            if result is not None:
                return result, 'page'
        except Exception:
            pass
    raise RuntimeError('graf_obdobi_nezjisteno')

def _month_shift(year, month, offset):
    x = year * 12 + month - 1 + offset
    return f'{x // 12:04d}-{x % 12 + 1:02d}'


def read_cost_graph(page, contract_id, kind):
    """Listen before the FIRST navigation to the contract details page.

    Store response handles inside the event handler and parse only after the
    handler has returned. Playwright response handlers must not themselves
    synchronously read the body while the navigation is ongoing.
    """
    responses = []

    def on_response(response):
        url = urlparse(response.url)
        if url.hostname == HOST and url.path == '/innogy24ajax/BillsGraph':
            responses.append(response)

    page.on('response', on_response)
    try:
        page.goto(BASE + f'/dashboard/detail-smlouvy-{kind}/naklady-a-spotreba?contractid=' + contract_id,
                  wait_until='domcontentloaded', timeout=60000)
        if (urlparse(page.url).hostname != HOST or
                '/naklady-a-spotreba' not in urlparse(page.url).path):
            raise RuntimeError('stranka_nedostupna')

        # AJAX may finish after domcontentloaded. The callback stores only
        # Response references so reading the body cannot stall callbacks.
        for _ in range(40):
            if responses:
                break
            page.wait_for_timeout(500)
        if not responses:
            raise RuntimeError('ajax_neprislo')

        data = None
        malformed = False
        wrong_shape = False
        for response in responses:
            if response.status != 200:
                continue
            try:
                payload = response.json()  # JSON can carry text/html header
            except Exception:
                malformed = True
                continue
            if (isinstance(payload, list) and len(payload) == 13 and
                    all(isinstance(x, dict) and
                        'CurrentPeriodValue' in x and
                        'PreviousPeriodValue' in x for x in payload)):
                data = payload
                break
            wrong_shape = True
        if data is None:
            raise RuntimeError('ajax_spatny_json' if malformed else 'ajax_spatne_schema' if wrong_shape else 'ajax_neprislo')

        start, period_source = _resolve_cost_graph_start(data, page)
        try:
            points = [
                {'mesic': _month_shift(start.year, start.month, i),
                 'naklady_kc': money(src['CurrentPeriodValue']),
                 'podle_zaloh_kc': money(src['PreviousPeriodValue'])}
                for i, src in enumerate(data)
            ]
        except (KeyError, TypeError, ValueError):
            raise RuntimeError('ajax_neplatna_data') from None
        current = datetime.now(ZoneInfo('Europe/Prague')).strftime('%Y-%m')
        measured = next((x for x in points if x['mesic'] == current), None)
        if measured is None:
            raise RuntimeError('graf_aktualni_mesic_nenalezen')
        return {'dosavadni_naklady_kc': measured['naklady_kc'],
                'predpoklad_podle_zaloh_kc': measured['podle_zaloh_kc'],
                'odhad_konec_obdobi_kc': points[-1]['naklady_kc'],
                'body_grafu': points, 'graf_zacatek': start.isoformat(),
                'graf_obdobi_zdroj': period_source,
                'mesic_zobrazenych_nakladu': current,
                'poznamka': 'Průběžná kalkulace innogy; bod aktuálního měsíce může obsahovat odhad.'}
    finally:
        page.remove_listener('response', on_response)
