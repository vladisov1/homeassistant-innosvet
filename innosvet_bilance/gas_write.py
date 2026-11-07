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

from playwright.sync_api import sync_playwright

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


def validate_and_reserve(journal, slot, reading, now):
    attempts = journal.setdefault('attempts', {})
    if slot in attempts:
        raise ValueError('Tento plánovaný čas už byl zpracován; bez duplicitního zápisu')
    last = journal.get('last_success')
    if last is not None and reading < int(last['reading']):
        raise ValueError('Hodnota plynoměru klesla pod poslední úspěšný zápis')
    attempts[slot] = {'status': 'reserved', 'reading': reading, 'at': now.isoformat()}
    journal_save(journal)


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


def write_gas(opts, now, slot):
    """Returns status + value; only performs POST in explicit enabled mode.

    Each slot is reserved BEFORE interacting with the remote write form. On an
    uncertain result (timeout, crash, incomplete confirmation), the same slot
    will not be retried automatically. Manual inspection is required.
    """
    if not opts.get('gas_write_enabled', False):
        return 'disabled', None
    reading = get_reading(opts['gas_entity_id'])
    today = f'{now.day}.{now.month}.{now.year}'
    journal = journal_read()
    # Explicit opt-in: a second independent switch prevents accidental enabling.
    if not opts.get('gas_write_confirmed', False):
        # Na rozdíl od alpha3 skutečně ověříme webový formulář.
        # V kontrolním režimu nedochází k HTTP POST na innosvět.
        status = preview_gas_form(opts, today, reading)
        return status, reading
    validate_and_reserve(journal, slot, reading, now)
    attempts = journal['attempts']
    request_sent = False
    try:
        with sync_playwright() as p:
            from app import PROFILE, find_authenticated, try_login
            context = p.firefox.launch_persistent_context(
                user_data_dir=str(PROFILE), headless=True, locale='cs-CZ', accept_downloads=False)
            try:
                allow_post = {'value': False}
                def guard(route):
                    request = route.request
                    parsed = urlparse(request.url)
                    method = request.method.upper()
                    if parsed.hostname == HOST and method not in ('GET', 'HEAD', 'OPTIONS'):
                        if method == 'POST' and parsed.path == FORM_PATH and allow_post['value']:
                            route.continue_()
                        else:
                            route.abort()
                    else:
                        route.continue_()
                context.route('**/*', guard)
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(BASE, wait_until='domcontentloaded', timeout=60000)
                active = find_authenticated(context, 35)
                if active is None:
                    active = try_login(context, page, opts['innogy_username'], opts['innogy_password'])
                if active is None:
                    raise RuntimeError('Přihlášení se nezdařilo')
                target = BASE + SELECT_PATH + '?contractid=' + opts['gas_contract_id']
                active.goto(target, wait_until='domcontentloaded', timeout=60000)
                parsed_select = urlparse(active.url)
                if (parsed_select.path != SELECT_PATH or parsed_select.hostname != HOST
                    or parse_qs(parsed_select.query).get('contractid') != [opts['gas_contract_id']]):
                    raise RuntimeError('Nesprávná stránka plynové smlouvy')
                link = active.get_by_role('link', name=re.compile('Průběžný odečet', re.I))
                button = active.get_by_role('button', name=re.compile('Průběžný odečet', re.I))
                if link.count() == 1:
                    link.click(timeout=20000)
                elif button.count() == 1:
                    button.click(timeout=20000)
                else:
                    raise RuntimeError('Nejednoznačná volba průběžného odečtu')
                active.wait_for_url(lambda u: urlparse(str(u)).path == FORM_PATH, timeout=20000)
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
                if date.count() != 1 or count.count() != 1 or date.input_value().strip() != today:
                    raise RuntimeError('Datum formuláře nesouhlasí s dnešním dnem')
                count.fill(str(reading))
                if count.input_value() != str(reading):
                    raise RuntimeError('Stav nelze spolehlivě vyplnit')
                # No write allowed above this line.
                allow_post['value'] = True
                request_sent = True  # conservatively treat all subsequent failures as uncertain
                form.locator('button[name="command"][value="CountOffFormSendButton"]').click(timeout=20000)
                active.get_by_text('Shrnutí před odesláním', exact=False).wait_for(timeout=20000)
                summary = active.locator('body').inner_text(timeout=15000)
                # Confirm a distinct 'Nový stav' line, not merely previous reading.
                pattern = r'Nový\s+stav\s*:\s*' + re.escape(str(reading)) + r'\s*m[³3]'
                if not re.search(pattern, summary, re.I):
                    raise RuntimeError('Shrnutí neobsahuje očekávaný nový stav')
                if not re.search(r'Odečet\s+ke\s+dni\s*' + re.escape(today), summary, re.I):
                    raise RuntimeError('Shrnutí neobsahuje správné datum')
                send = active.get_by_role('button', name=re.compile(r'^Odeslat odečet$', re.I))
                if send.count() != 1:
                    raise RuntimeError('Nelze jednoznačně najít finální potvrzení')
                send.click(timeout=20000)
                active.get_by_text('Odečet byl odeslán', exact=False).wait_for(timeout=25000)
                attempts[slot]['status'] = 'success'
                journal['last_success'] = {'reading': reading, 'at': datetime.now(now.tzinfo).isoformat()}
                journal_save(journal)
                return 'success', reading
            finally:
                context.close()
    except Exception as exc:
        attempts[slot]['status'] = 'uncertain' if request_sent else 'not_sent'
        attempts[slot]['error_type'] = type(exc).__name__
        journal_save(journal)
        raise RuntimeError('Zápis nepotvrzen; bez automatického opakování') from None
