"""Opt-in gas submission. No transmission unless enabled and all checks pass.

No secrets, request bodies, cookies or HTML are logged. Uncertain transmissions
are NOT retried automatically: see the persistent slot journal.
"""
import json
import logging
import os
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

LOG = logging.getLogger('innosvet.gas')
HOST = 'innosvet.innogy.cz'
BASE = 'https://' + HOST
FORM_PATH = '/chci-zaridit/zadat-prubezny-odecet'
SELECT_PATH = '/chci-zaridit/zadat-odecet'
JOURNAL = Path('/data/gas_write_journal.json')


class GasReadError(RuntimeError):
    """Safe, non-secret diagnostic for accessing the HA state API."""



def get_reading(entity_id):
    if not re.fullmatch(r'sensor\.[a-z0-9_]+', entity_id or ''):
        raise ValueError('Neplatná entita senzoru plynoměru')
    token = os.getenv('SUPERVISOR_TOKEN')
    if not token:
        raise RuntimeError('Chybí přístup k Home Assistant API')
    req = Request('http://supervisor/core/api/states/' + entity_id,
                  headers={'Authorization': 'Bearer ' + token})
    try:
        with urlopen(req, timeout=15) as response:
            data = json.load(response)
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise GasReadError(f'HTTP {exc.code}: Home Assistant odmítl přístup k entitě; ověřte homeassistant_api: true') from None
        if exc.code == 404:
            raise GasReadError('HTTP 404: zadaná entita plynoměru nebyla nalezena') from None
        raise GasReadError(f'HTTP {exc.code}: Home Assistant nevrátil stav plynoměru') from None
    except (URLError, TimeoutError):
        raise GasReadError('Nepodařilo se spojit s Home Assistant API') from None
    except (ValueError, TypeError):
        raise GasReadError('Home Assistant vrátil neplatnou odpověď senzoru') from None
    state = str(data.get('state', '')).strip().replace(',', '.')
    if state.lower() in ('unavailable', 'unknown', 'none', ''):
        raise ValueError('Senzor neposkytuje platný odečet')
    try:
        value = Decimal(state)
    except InvalidOperation:
        raise ValueError('Stav senzoru není číslo') from None
    if not value.is_finite() or value <= 0:
        raise ValueError('Neplatná nebo záporná hodnota plynoměru')
    unit = str((data.get('attributes') or {}).get('unit_of_measurement', '')).strip()
    if unit not in ('m³', 'm3'):
        raise ValueError('Senzor nemá očekávanou jednotku m³')
    return int(value.to_integral_value(rounding=ROUND_DOWN))


def journal_read():
    try:
        value = json.loads(JOURNAL.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except FileNotFoundError:
        return {}
    except (ValueError, OSError):
        raise RuntimeError('Deník zápisů je poškozen; zápis z bezpečnostních důvodů zakázán')


def journal_save(journal):
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    temp = JOURNAL.with_suffix('.tmp')
    temp.write_text(json.dumps(journal, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.chmod(temp, 0o600)
    temp.replace(JOURNAL)


UNRESOLVED_STATUSES = ('reserved', 'uncertain', 'final_step_uncertain', 'first_step_uncertain')


def pending_review():
    """Oldest unresolved attempt. No credentials or portal data are exposed."""
    attempts = journal_read().get('attempts', {})
    candidates = [
        {'slot': slot, 'reading': int(attempt['reading'])}
        for slot, attempt in attempts.items()
        if isinstance(attempt, dict) and attempt.get('status') in UNRESOLVED_STATUSES
        and isinstance(attempt.get('reading'), int)
    ]
    return min(candidates, key=lambda v: v['slot']) if candidates else None


def resolve_reviewed_attempt(review_token):
    """Review EXACT pending slot+reading after checking the external portal.

    No portal write is ever performed. Stale commands are rejected.
    """
    token = str(review_token or '').strip()
    match = re.fullmatch(r'(\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d)\|([1-9]\d*)\|(RECORDED|NOT_RECORDED)', token)
    if not match:
        raise ValueError('Neplatný příkaz kontroly odečtu')
    slot, reading, outcome = match.group(1), int(match.group(2)), match.group(3)
    datetime.strptime(slot, '%Y-%m-%dT%H:%M')
    journal = journal_read()
    attempt = journal.get('attempts', {}).get(slot)
    pending = pending_review()
    if pending != {'slot': slot, 'reading': reading}:
        raise ValueError('Zastaralé potvrzení nebo jiný dosud nevyřešený pokus')
    if not isinstance(attempt, dict) or attempt.get('status') not in UNRESOLVED_STATUSES or attempt.get('reading') != reading:
        raise ValueError('Odečet není ve stavu vyžadujícím potvrzení')
    attempt['previous_status'] = attempt['status']
    attempt['status'] = 'verified_recorded' if outcome == 'RECORDED' else 'verified_not_recorded'
    attempt['reviewed_at'] = datetime.now().astimezone().isoformat()
    attempt['review_note'] = ('Uživatel ověřil v innosvětě: zaznamenáno' if outcome == 'RECORDED'
                              else 'Uživatel ověřil v innosvětě: nezaznamenáno')
    closing = journal.get('daily_closings', {}).get(slot[:10])
    if closing and closing.get('slot') == slot and closing.get('reading') == reading:
        closing['status'] = 'confirmed' if outcome == 'RECORDED' else 'verified_not_recorded'
    if outcome == 'RECORDED':
        last = journal.get('last_success')
        if last is None or reading >= int(last['reading']):
            journal['last_success'] = {'reading': reading, 'at': attempt['reviewed_at'],
                                       'source': 'user_verified_portal_history'}
    journal_save(journal)
    LOG.warning('Plyn: odečet %s m³ (%s) uzavřen jako %s; bez nového odeslání', reading, slot, attempt['status'])
    return True


def validate_and_reserve(journal, slot, reading, now):
    attempts = journal.setdefault('attempts', {})
    if slot in attempts:
        raise ValueError('Tento plánovaný čas už byl zpracován; bez duplicitního zápisu')
    last = journal.get('last_success')
    if last is not None and reading < int(last['reading']):
        raise ValueError('Hodnota plynoměru klesla pod poslední úspěšný zápis')
    attempts[slot] = {'status': 'reserved', 'reading': reading, 'at': now.isoformat()}
    journal_save(journal)



# Persistent, date-bound snapshots. Never reconstruct past readings from a
# current sensor value. Stored in the same atomically replaced audit journal.
def capture_daily_closing(local_date, slot, reading, observed_at):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', local_date):
        raise ValueError('Neplatné datum závěrečného odečtu')
    datetime.strptime(local_date, '%Y-%m-%d')
    if not isinstance(reading, int) or reading <= 0:
        raise ValueError('Neplatný stav denního odečtu')
    journal = journal_read()
    records = journal.setdefault('daily_closings', {})
    existing = records.get(local_date)
    if existing:
        if existing.get('slot') != slot or existing.get('reading') != reading:
            raise RuntimeError('Denní odečet je již uložen s jinou identitou; kontrola nutná')
        return existing
    record = {'slot': slot, 'reading': reading, 'observed_at': observed_at,
              'status': 'captured', 'source': 'home_assistant_sensor'}
    records[local_date] = record
    journal_save(journal)
    LOG.info('Plyn: závěrečný stav dne %s místně uložen: %s m³', local_date, reading)
    return record


def set_daily_closing_status(local_date, status, slot=None):
    journal = journal_read()
    record = journal.get('daily_closings', {}).get(local_date)
    if not record:
        return False
    if slot and record.get('slot') != slot:
        return False
    if record.get('status') == 'confirmed' and status != 'confirmed':
        return False
    record['status'] = status
    journal_save(journal)
    return True


def oldest_closing_for_review():
    records = journal_read().get('daily_closings', {})
    items = [(day, r) for day, r in records.items()
             if isinstance(r, dict) and r.get('status') not in ('confirmed', 'skipped')]
    if not items:
        return None
    day, rec = min(items, key=lambda x: x[0])
    return {'date': day, 'slot': rec['slot'], 'reading': rec['reading'],
            'status': rec['status'], 'observed_at': rec['observed_at']}


def validate_historical_closing(local_date, reading):
    """Conservative boundaries from locally CONFIRMED successes only.

    These are necessary, not sufficient: the portal may hold other readings.
    No automatic submission is authorised by this check.
    """
    datetime.strptime(local_date, '%Y-%m-%d')
    journal = journal_read()
    record = journal.get('daily_closings', {}).get(local_date)
    if not record or record.get('reading') != reading:
        raise ValueError('Neexistuje odpovídající uložený denní stav')
    if record['status'] == 'confirmed':
        raise ValueError('Denní stav již byl potvrzen')
    if record['status'] in ('uncertain', 'awaiting_review'):
        raise ValueError('Výsledek původního zápisu je nejistý; nejprve vyřešte kontrolu')
    lower = upper = None
    for at, attempt in journal.get('attempts', {}).items():
        if not isinstance(attempt, dict) or attempt.get('status') not in ('success', 'verified_recorded'):
            continue
        if not isinstance(attempt.get('reading'), int):
            continue
        day = at[:10]
        if day < local_date:
            lower = attempt['reading'] if lower is None else max(lower, attempt['reading'])
        elif day > local_date:
            upper = attempt['reading'] if upper is None else min(upper, attempt['reading'])
    if lower is not None and reading < lower:
        raise ValueError('Historický odečet je nižší než předchozí potvrzená hodnota')
    if upper is not None and reading > upper:
        raise ValueError('Historický odečet je vyšší než následující potvrzená hodnota')
    return True

def preview_gas_form(opts, today, reading):
    """Test navigace a vyplnění. Veškeré POST/PUT/PATCH/DELETE na portál blokuje.

    Záměrně NEKLIKÁ na Pokračovat: jde o POST, který může být vedlejší účinek.
    Nikdy neprovádí žádný zápis ani rezervaci slotu v deníku zápisů.
    """
    from app import PROFILE, find_authenticated, try_login
    PROFILE.mkdir(parents=True, exist_ok=True)
    LOG.info('Plyn: kontrola formuláře zahájena (bez odesílání)')
    phase = 'otevření portálu'
    try:
        with sync_playwright() as p:
            context = p.firefox.launch_persistent_context(
                user_data_dir=str(PROFILE), headless=True,
                locale='cs-CZ', accept_downloads=False)
            try:
                def guard(route):
                    request = route.request
                    parsed = urlparse(request.url)
                    # Autentizační server je jiná doména. Na innosvět
                    # v tomto režimu nepovolujeme žádný měnící požadavek.
                    if parsed.hostname == HOST and request.method.upper() not in ('GET', 'HEAD', 'OPTIONS'):
                        route.abort()
                    else:
                        route.continue_()
                context.route('**/*', guard)
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(BASE, wait_until='domcontentloaded', timeout=60000)
                phase = 'přihlášení'
                active = find_authenticated(context, 35)
                if active is None:
                    active = try_login(context, page, opts['innogy_username'], opts['innogy_password'])
                if active is None:
                    raise RuntimeError('Přihlášení do innosvěta není dostupné')
                phase = 'výběr plynové smlouvy'
                url = BASE + SELECT_PATH + '?contractid=' + opts['gas_contract_id']
                active.goto(url, wait_until='domcontentloaded', timeout=60000)
                parsed = urlparse(active.url)
                if (parsed.hostname != HOST or parsed.path != SELECT_PATH
                    or parse_qs(parsed.query).get('contractid') != [opts['gas_contract_id']]):
                    raise RuntimeError('Nesprávná stránka plynové smlouvy')
                LOG.info('Plyn: stránka plynové smlouvy ověřena')
                phase = 'otevření formuláře'
                link = active.get_by_role('link', name=re.compile('Průběžný odečet', re.I))
                button = active.get_by_role('button', name=re.compile('Průběžný odečet', re.I))
                if link.count() == 1:
                    link.click(timeout=20000)
                elif button.count() == 1:
                    button.click(timeout=20000)
                else:
                    raise RuntimeError('Nelze jednoznačně nalézt volbu průběžného odečtu')
                active.wait_for_url(lambda u: urlparse(str(u)).path == FORM_PATH, timeout=20000)
                phase = 'ověření formuláře'
                form = active.locator('#meterReadingForm')
                form.wait_for(state='visible', timeout=20000)
                method_ok = (form.get_attribute('method') or '').lower() == 'post'
                action_ok = (form.get_attribute('action') or '').split('?')[0] == FORM_PATH
                gas_ok = (active.get_by_text('Zadejte stav plynoměru', exact=False).count() > 0
                          and active.get_by_text('Vysoký tarif', exact=False).count() == 0)
                token_ok = form.locator('input[name="__RequestVerificationToken"]').count() == 1
                count = form.locator('input[name="CountOff"]')
                date = form.locator('input[name="Date"]:visible')
                if not all((method_ok, action_ok, gas_ok, token_ok,
                            count.count() == 1, date.count() == 1)):
                    raise RuntimeError('Kontrola plynového formuláře neprošla')
                if date.input_value().strip() != today:
                    raise RuntimeError('Datum na formuláři nesouhlasí s dnešním dnem')
                phase = 'vyplnění formuláře'
                count.fill(str(reading))
                if count.input_value() != str(reading):
                    raise RuntimeError('Formulář nepřijal stav plynoměru')
                LOG.info('Plyn: formulář otevřen, smlouva a datum ověřeny, stav %s m³ vyplněn; BEZ POST a BEZ odeslání', reading)
                return 'preview_form_ready'
            finally:
                context.close()
    except Exception as exc:
        # Nikdy nevypisovat URL, HTML, token, cookies ani text výjimky.
        LOG.warning('Plyn: kontrolní formulář selhal ve fázi %s (%s); nic neodesláno', phase, type(exc).__name__)
        raise GasReadError('Příprava formuláře innosvěta selhala ve fázi: ' + phase) from None


def write_gas(opts, now, slot, historical=None, reading_override=None):
    """Returns status + value; only performs POST in explicit enabled mode.

    Each slot is reserved BEFORE interacting with the remote write form. On an
    uncertain result (timeout, crash, incomplete confirmation), the same slot
    will not be retried automatically. Manual inspection is required.
    """
    if not opts.get('gas_write_enabled', False):
        return 'disabled', None
    reading = (reading_override if reading_override is not None else get_reading(opts['gas_entity_id']))
    if historical is not None:
        local_date, saved_reading = historical
        if saved_reading != reading:
            raise ValueError('Historická hodnota neodpovídá uloženému stavu')
        validate_historical_closing(local_date, reading)
        target_day = datetime.strptime(local_date, '%Y-%m-%d')
        if target_day.date() >= now.date():
            raise ValueError('Zpětný zápis musí být za minulý den')
        today = f'{target_day.day}.{target_day.month}.{target_day.year}'
    else:
        today = f'{now.day}.{now.month}.{now.year}'
    journal = journal_read()
    # Explicit opt-in: a second independent switch prevents accidental enabling.
    if not opts.get('gas_write_confirmed', False):
        # Na rozdíl od alpha3 skutečně ověříme webový formulář.
        # V kontrolním režimu nedochází k HTTP POST na innosvět.
        status = preview_gas_form(opts, today, reading)
        return status, reading
    # Block an unresolved attempt for the SAME reading even when optimization
    # is disabled. Do not silently bypass the safety journal.
    if slot in journal.get('attempts', {}):
        raise ValueError('Tento plánovaný čas už byl zpracován; bez duplicitního zápisu')
    unresolved_same_value = any(
        isinstance(a, dict) and a.get('status') in (
            'reserved', 'uncertain', 'final_step_uncertain', 'first_step_uncertain'
        ) and a.get('reading') == reading
        for a in journal.get('attempts', {}).values()
    )
    if unresolved_same_value and historical is None:
        LOG.warning('Plyn: stav %s m³ má předchozí nepotvrzený pokus; automatický zápis pozastaven', reading)
        return 'vyzaduje_kontrolu_historie', reading
    # Optional optimized schedule: retain alpha12 behavior unless explicitly enabled.
    # Always send the first and last slot of the configured local day. Middle slots
    # only send if the integer meter value changed since the last CONFIRMED write.
    # An unknown/uncertain outcome is never silently treated as a success.
    if opts.get('gas_write_optimized', False) and historical is None:
        times = opts['times']
        local_slot = now.strftime('%H:%M')
        first_or_last = local_slot in (times[0], times[-1])
        existing = journal.get('attempts', {}).get(slot)
        if existing is not None:
            raise ValueError('Tento plánovaný čas už byl zpracován; bez duplicitního zápisu')
        previous = journal.get('last_success')
        if previous is not None and reading < int(previous['reading']):
            raise ValueError('Hodnota plynoměru klesla pod poslední úspěšný zápis')
        if not first_or_last and previous is not None and reading == int(previous['reading']):
            journal.setdefault('attempts', {})[slot] = {
                'status': 'skipped_unchanged', 'reading': reading,
                'at': now.isoformat(), 'reason': 'same_as_last_confirmed'
            }
            journal_save(journal)
            LOG.info('Plyn: mezilehlý čas %s, stav %s m³ beze změny od potvrzeného zápisu; odeslání vynecháno', local_slot, reading)
            return 'beze_zmeny', reading
        LOG.info('Plyn: optimalizace – %s, stav %s m³',
                 'první/poslední čas dne' if first_or_last else 'změna celých m³', reading)
    if historical is None:
        validate_and_reserve(journal, slot, reading, now)
    else:
        # Separate, uniquely identified attempt: original attempt is never edited.
        attempts = journal.setdefault('attempts', {})
        if slot in attempts:
            raise ValueError('Tento opravný pokus již existuje')
        attempts[slot] = {'status': 'reserved', 'reading': reading,
                          'at': now.isoformat(), 'historical_date': historical[0]}
        journal_save(journal)
    attempts = journal['attempts']
    request_sent = False
    phase = 'zahájení zápisu'
    diagnostic = {'first_button_count': -1, 'first_button_visible': False,
                  'first_button_enabled': False, 'first_post_count': 0,
                  'final_post_count': 0, 'response_statuses': [],
                  'summary_heading': False, 'summary_button': False,
                  'final_hit': None, 'final_activated_by': 'none',
                  'portal_block_statuses': [], 'js_error_count': 0}
    try:
        with sync_playwright() as p:
            from app import PROFILE, find_authenticated, try_login
            context = p.firefox.launch_persistent_context(
                user_data_dir=str(PROFILE), headless=True, locale='cs-CZ', accept_downloads=False)
            try:
                # We only authorize the specific form POST, one request per stage.
                # Everything else that could change portal state is blocked.
                post_gate = {'phase': 'blocked', 'counts': {'continue': 0, 'final': 0},
                             'http_statuses': []}
                def observe_response(response):
                    req = response.request
                    parsed = urlparse(req.url)
                    # Only HTTP status codes; never store URLs, headers, bodies or cookies.
                    if parsed.hostname == HOST and response.status in (401, 403, 429):
                        diagnostic['portal_block_statuses'].append(response.status)
                    if parsed.hostname == HOST and parsed.path == FORM_PATH and req.method.upper() == 'POST':
                        post_gate['http_statuses'].append(response.status)
                        diagnostic['response_statuses'] = list(post_gate['http_statuses'])
                context.on('response', observe_response)
                def guard(route):
                    request = route.request
                    parsed = urlparse(request.url)
                    method = request.method.upper()
                    if parsed.hostname == HOST and method not in ('GET', 'HEAD', 'OPTIONS'):
                        stage = post_gate['phase']
                        if (method == 'POST' and parsed.path == FORM_PATH
                            and stage in ('continue', 'final') and post_gate['counts'][stage] == 0):
                            post_gate['counts'][stage] += 1
                            diagnostic['first_post_count'] = post_gate['counts']['continue']
                            diagnostic['final_post_count'] = post_gate['counts']['final']
                            # Close gate at the FIRST permitted request, not after a page transition.
                            post_gate['phase'] = 'blocked'
                            route.continue_()
                        else:
                            route.abort()
                    else:
                        route.continue_()
                context.route('**/*', guard)
                def note_page_error(_error):
                    # Error strings may contain private URLs and tokens: count only.
                    diagnostic['js_error_count'] += 1
                context.on('page', lambda new_page: new_page.on('pageerror', note_page_error))
                page = context.pages[0] if context.pages else context.new_page()
                for existing_page in context.pages:
                    existing_page.on('pageerror', note_page_error)
                phase = 'přihlášení do portálu'
                page.goto(BASE, wait_until='domcontentloaded', timeout=60000)
                active = find_authenticated(context, 35)
                if active is None:
                    active = try_login(context, page, opts['innogy_username'], opts['innogy_password'])
                if active is None:
                    raise RuntimeError('Přihlášení se nezdařilo')
                phase = 'výběr plynové smlouvy'
                target = BASE + SELECT_PATH + '?contractid=' + opts['gas_contract_id']
                active.goto(target, wait_until='domcontentloaded', timeout=60000)
                parsed_select = urlparse(active.url)
                if (parsed_select.path != SELECT_PATH or parsed_select.hostname != HOST
                    or parse_qs(parsed_select.query).get('contractid') != [opts['gas_contract_id']]):
                    raise RuntimeError('Nesprávná stránka plynové smlouvy')
                phase = 'otevření formuláře'
                link = active.get_by_role('link', name=re.compile('Průběžný odečet', re.I))
                button = active.get_by_role('button', name=re.compile('Průběžný odečet', re.I))
                if link.count() == 1:
                    link.click(timeout=20000)
                elif button.count() == 1:
                    button.click(timeout=20000)
                else:
                    raise RuntimeError('Nejednoznačná volba průběžného odečtu')
                active.wait_for_url(lambda u: urlparse(str(u)).path == FORM_PATH, timeout=20000)
                phase = 'ověření formuláře a hodnoty'
                form = active.locator('#meterReadingForm')
                form.wait_for(state='visible', timeout=20000)
                if ((form.get_attribute('method') or '').lower() != 'post'
                    or (form.get_attribute('action') or '').split('?')[0] != FORM_PATH
                    or active.get_by_text('Zadejte stav plynoměru', exact=False).count() == 0
                    or active.get_by_text('Vysoký tarif', exact=False).count() > 0
                    or form.locator('input[name="__RequestVerificationToken"]').count() != 1):
                    raise RuntimeError('Formulář plynu neprošel kontrolou')
                date = form.locator('input[name="Date"]:visible')
                count = form.locator('input[name="CountOff"]')
                if date.count() != 1 or count.count() != 1:
                    raise RuntimeError('Nejednoznačné datum nebo stav formuláře')
                if historical is None:
                    if date.input_value().strip() != today:
                        raise RuntimeError('Datum formuláře nesouhlasí s dnešním dnem')
                else:
                    # The portal's visible Date input must accept the requested
                    # historical date by normal interaction. Never bypass readonly
                    # fields or inject JavaScript state.
                    if date.input_value().strip() != today:
                        date.fill(today, timeout=8000)
                        date.press('Tab')
                    if date.input_value().strip() != today:
                        raise RuntimeError('Portál nepřijal historické datum')
                count.fill(str(reading))
                if count.input_value() != str(reading):
                    raise RuntimeError('Stav nelze spolehlivě vyplnit')
                # Before this point: NO POST. From here every permitted POST is
                # treated as a potentially irreversible remote action.
                LOG.info('Plyn: ověřena smlouva, datum a hodnota %s m³; zahajuji dvoukrokové potvrzení', reading)
                phase = 'první krok Pokračovat'
                post_gate['phase'] = 'continue'
                request_sent = True
                attempts[slot]['status'] = 'first_step_uncertain'
                journal_save(journal)
                # The portal may render an <input type=submit> rather than <button>.
                # Count and check the precise command field BEFORE interacting.
                command = form.locator('[name="command"][value="CountOffFormSendButton"]')
                diagnostic['first_button_count'] = command.count()
                if command.count() == 1:
                    diagnostic['first_button_visible'] = command.is_visible()
                    diagnostic['first_button_enabled'] = command.is_enabled()
                LOG.info('Plyn: Pokračovat – počet prvků %s, viditelné: %s, aktivní: %s',
                         diagnostic['first_button_count'], diagnostic['first_button_visible'],
                         diagnostic['first_button_enabled'])
                if command.count() != 1 or not diagnostic['first_button_visible'] or not diagnostic['first_button_enabled']:
                    raise RuntimeError('První potvrzovací tlačítko není jednoznačné nebo aktivní')
                # Kontrola překryvu / cíle kliknutí. Zaznamenáváme pouze názvy
                # značek a třídy prvků, nikdy text formuláře ani citlivá data.
                hit = command.evaluate("""el => {
                  const b = el.getBoundingClientRect();
                  const n = document.elementFromPoint(b.left+b.width/2, b.top+b.height/2);
                  return {hit: !!n && (n === el || el.contains(n)),
                          tag: n ? n.tagName.toLowerCase() : 'none',
                          overlay: !!document.querySelector('.js-overlay--body:not([hidden])') &&
                            getComputedStyle(document.querySelector('.js-overlay--body:not([hidden])')).display !== 'none'};
                }""")
                LOG.info('Plyn: Pokračovat – cíl kliknutí: %s, překryv na stránce: %s',
                         hit['hit'], hit['overlay'])
                # Playwright čeká na kliknutelnost. Pokud kliknutí skončí
                # timeoutem dřív, než byl zachycen POST, lze jako jednu
                # alternativní aktivaci použít Enter na stejném tlačítku.
                LOG.info('Plyn: Pokračovat – pokus o kliknutí')
                try:
                    command.click(timeout=8000, no_wait_after=True)
                except PlaywrightTimeout:
                    if post_gate['counts']['continue'] != 0:
                        raise RuntimeError('Kliknutí je nejisté a POST již začal') from None
                    # Při ztrátě formuláře či jeho změně nezkoušíme nic znovu.
                    if (form.count() != 1 or command.count() != 1
                        or not command.is_visible() or not command.is_enabled()
                        or count.input_value() != str(reading)
                        or date.input_value().strip() != today):
                        raise RuntimeError('Formulář se po timeoutu změnil') from None
                    LOG.warning('Plyn: běžné kliknutí se neprovedlo; bez POST, zkouším Enter na stejném tlačítku')
                    command.focus(timeout=5000)
                    # Alternativní JEDNORÁZOVÉ odeslání formuláře stiskem Enter.
                    command.press('Enter', timeout=8000, no_wait_after=True)
                LOG.info('Plyn: Pokračovat – aktivace dokončena, zaznamenaný POST: %s', post_gate['counts']['continue'])
                phase = 'odpověď prvního kroku'
                # Both network response and new confirmation page may arrive later.
                for _ in range(40):
                    if post_gate['http_statuses'] or post_gate['counts']['continue'] == 0:
                        # Wait longer for a possible POST (async validation) without resending.
                        if post_gate['http_statuses']:
                            break
                    active.wait_for_timeout(500)
                LOG.info('Plyn: Pokračovat – POST počet %s, HTTP stavy %s',
                         post_gate['counts']['continue'], post_gate['http_statuses'])
                if post_gate['counts']['continue'] != 1:
                    raise RuntimeError('Po kliknutí nebyl zachycen právě jeden POST')
                if len(post_gate['http_statuses']) != 1 or not (200 <= post_gate['http_statuses'][0] < 400):
                    raise RuntimeError('První POST nemá potvrzenou úspěšnou HTTP odpověď')
                phase = 'ověření rekapitulace'
                # Wait for the summary, but do not depend on one hard-coded title.
                send = active.get_by_role('button', name=re.compile(r'^Odeslat odečet$', re.I))
                for _ in range(30):
                    if send.count() == 1:
                        break
                    active.wait_for_timeout(500)
                diagnostic['summary_heading'] = active.get_by_text('Shrnutí před odesláním', exact=False).count() > 0
                diagnostic['summary_button'] = send.count() == 1
                LOG.info('Plyn: rekapitulace – očekávaný nadpis: %s, finální tlačítko: %s',
                         diagnostic['summary_heading'], diagnostic['summary_button'])
                if send.count() != 1 or not send.is_visible() or not send.is_enabled():
                    raise RuntimeError('Není jednoznačně dostupná rekapitulace s finálním potvrzením')
                summary = active.locator('body').inner_text(timeout=15000)
                # The presentation may use spaces as thousands separators.
                condensed = re.sub(r'[\s\u00a0\u202f]', '', summary)
                reading_ok = str(reading) in condensed
                date_ok = today in summary or today in condensed
                # Require BOTH data points and the final confirmation button.
                LOG.info('Plyn: rekapitulace – stav souhlasí: %s, datum souhlasí: %s', reading_ok, date_ok)
                if not (reading_ok and date_ok):
                    raise RuntimeError('Rekapitulace neobsahuje jednoznačný stav a datum')
                LOG.info('Plyn: rekapitulace ověřena; povoleno finální potvrzení')
                phase = 'finální odeslání'
                attempts[slot]['status'] = 'final_step_uncertain'
                journal_save(journal)
                post_gate['phase'] = 'final'
                # The mouse hit-test is performed BEFORE any irreversible attempt.
                # If another element occupies the button centre, keyboard activation
                # is chosen as the FIRST AND ONLY activation. No click is attempted.
                # This is not an anti-bot bypass; if a security challenge or HTTP
                # block is present, fail closed and require manual inspection.
                final_hit = send.evaluate("""el => {
                    const b = el.getBoundingClientRect();
                    const at = document.elementFromPoint(b.left+b.width/2, b.top+b.height/2);
                    const blocker = document.querySelector('iframe[src*="captcha"], iframe[src*="challenge"], .g-recaptcha, .h-captcha, [data-sitekey]');
                    return {hit: !!at && (at === el || el.contains(at)),
                            challenge: !!blocker, width: b.width, height: b.height};
                }""")
                diagnostic['final_hit'] = bool(final_hit['hit'])
                LOG.info('Plyn: finální tlačítko – cíl kliknutí: %s, bezpečnostní výzva: %s',
                         diagnostic['final_hit'], bool(final_hit['challenge']))
                if final_hit['challenge'] or diagnostic['portal_block_statuses']:
                    raise RuntimeError('Potenciální bezpečnostní kontrola portálu; bez odeslání')
                if final_hit['width'] <= 0 or final_hit['height'] <= 0:
                    raise RuntimeError('Finální tlačítko nemá platné rozměry')
                LOG.info('Plyn: finální odeslání – zahajuji jedinou aktivaci')
                # A single keyboard activation avoids the Playwright pointer
                # actionability race seen on 2026-11-11. No pointer fallback and
                # no second activation are permitted on an ambiguous outcome.
                diagnostic['final_activated_by'] = 'keyboard_primary'
                send.focus(timeout=5000)
                send.press('Enter', timeout=8000, no_wait_after=True)
                LOG.info('Plyn: finální aktivace=%s; počet zachycených POST=%s',
                         diagnostic['final_activated_by'], post_gate['counts']['final'])
                # Guard blocks any additional POST; accept only a portal confirmation.
                active.get_by_text('Odečet byl odeslán', exact=False).wait_for(timeout=25000)
                if post_gate['counts']['final'] != 1:
                    raise RuntimeError('Finální POST nebyl jednoznačný')
                if len(post_gate['http_statuses']) != 2 or not (200 <= post_gate['http_statuses'][1] < 400):
                    raise RuntimeError('Finální POST nemá úspěšnou HTTP odpověď')
                post_gate['phase'] = 'blocked'
                attempts[slot]['status'] = 'success'
                if historical is None:
                    journal['last_success'] = {'reading': reading, 'at': datetime.now(now.tzinfo).isoformat()}
                else:
                    # Do not regress last_success to an earlier historical reading.
                    last = journal.get('last_success')
                    if last is None or reading >= int(last['reading']):
                        journal['last_success'] = {'reading': reading, 'at': datetime.now(now.tzinfo).isoformat()}
                if historical is not None:
                    record = journal.get('daily_closings', {}).get(historical[0])
                    if record:
                        record['status'] = 'confirmed'
                        record['recovered_at'] = datetime.now(now.tzinfo).isoformat()
                journal_save(journal)
                LOG.info('Plyn: odečet %s m³ potvrzen stránkou innosvěta', reading)
                return 'success', reading
            finally:
                context.close()
    except Exception as exc:
        attempts[slot]['status'] = 'uncertain' if request_sent else 'not_sent'
        attempts[slot]['error_type'] = type(exc).__name__
        attempts[slot]['phase'] = phase
        if historical is not None:
            record = journal.get('daily_closings', {}).get(historical[0])
            if record:
                record['status'] = 'uncertain' if request_sent else 'not_sent'
        journal_save(journal)
        LOG.warning('Plyn: diagnostika: tlačítko počet=%s, viditelné=%s, aktivní=%s; první POST=%s, finální POST=%s, HTTP=%s; nadpis rekapitulace=%s, finální tlačítko=%s',
                    diagnostic['first_button_count'], diagnostic['first_button_visible'],
                    diagnostic['first_button_enabled'], diagnostic['first_post_count'],
                    diagnostic['final_post_count'], diagnostic['response_statuses'],
                    diagnostic['summary_heading'], diagnostic['summary_button'])
        LOG.warning('Plyn: diagnostika finále: hit=%s, aktivace=%s, blokovací HTTP=%s, JS chyby=%s',
                    diagnostic['final_hit'], diagnostic['final_activated_by'],
                    diagnostic['portal_block_statuses'][:8], diagnostic['js_error_count'])
        LOG.warning('Plyn: odeslání nepotvrzeno ve fázi %s (%s), bez opakování; zkontrolujte historii innosvěta', phase, type(exc).__name__)
        raise RuntimeError('Zápis nepotvrzen; bez automatického opakování') from None
