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


def _month_shift(year, month, offset):
    x = year * 12 + month - 1 + offset
    return f'{x // 12:04d}-{x % 12 + 1:02d}'


def read_cost_graph(page, contract_id, kind):
    """Capture the BillsGraph response for the right contract on navigation.

    The source is JSON despite content-type text/html. Only numeric series and
    safe year-month labels are retained, and values are not interpreted as bills.
    """
    captured = []
    def on_response(response):
        path = urlparse(response.url)
        if path.hostname != HOST or path.path != '/innogy24ajax/BillsGraph' or response.status != 200:
            return
        try:
            blob = json.loads(response.text())
            if isinstance(blob, list) and 10 <= len(blob) <= 18 and all(isinstance(x, dict) for x in blob):
                captured.append(blob)
        except (ValueError, TypeError):
            pass
    page.on('response', on_response)
    try:
        page.goto(BASE + f'/dashboard/detail-smlouvy-{kind}/naklady-a-spotreba?contractid=' + contract_id,
                  wait_until='domcontentloaded', timeout=60000)
        if urlparse(page.url).hostname != HOST or '/naklady-a-spotreba' not in urlparse(page.url).path:
            raise RuntimeError('cost page inaccessible')
        for _ in range(18):
            if captured:
                break
            page.wait_for_timeout(500)
        if not captured:
            raise RuntimeError('BillsGraph not captured')
        data = captured[-1]
        # Innosvět may use localized labels. Derive month labels from the visible
        # period heading, never assume an arbitrary list index is current month.
        visible = page.locator('body').inner_text(timeout=10000)
        start = _parse_month_start(visible)
        if start is None:
            raise RuntimeError('cost period start not found')
        points = []
        for i, src in enumerate(data):
            pts = {'mesic': _month_shift(start.year, start.month, i),
                   'naklady_kc': money(src['CurrentPeriodValue']),
                   'podle_zaloh_kc': money(src['PreviousPeriodValue'])}
            points.append(pts)
        current = datetime.now(ZoneInfo('Europe/Prague')).strftime('%Y-%m')
        measured = next((x for x in points if x['mesic'] == current), None)
        if measured is None:
            raise RuntimeError('current month absent from graph')
        # The point for the currently displayed month can reflect a supplier
        # estimate to month end; preserve this uncertainty in UI and attributes.
        return {'dosavadni_naklady_kc': measured['naklady_kc'],
                'predpoklad_podle_zaloh_kc': measured['podle_zaloh_kc'],
                'odhad_konec_obdobi_kc': points[-1]['naklady_kc'],
                'body_grafu': points, 'graf_zacatek': start.isoformat(),
                'mesic_zobrazenych_nakladu': current,
                'poznamka': 'Průběžná kalkulace innogy; bod aktuálního měsíce může obsahovat odhad.'}
    finally:
        page.remove_listener('response', on_response)
