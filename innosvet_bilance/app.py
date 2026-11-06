"""Experimental innosvět read-only HAOS app.

No gas meter submissions exist in this app. All non-read requests to the
innosvět host are blocked; authentication requests on the identity provider
may use POST. Never log credentials, URLs with query parameters or cookies.
"""
import json
import logging
import os
import re
import signal
import sys
import time
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
import paho.mqtt.client as mqtt

HOST = "innosvet.innogy.cz"
BASE = "https://" + HOST
DATA = Path("/data")
PROFILE = DATA / "browser_profile"
RESULT = DATA / "last_read.json"
OPTIONS = DATA / "options.json"
DISCOVERY_PREFIX = "homeassistant"
STATE_PREFIX = "innosvet_ha"
LOG = logging.getLogger("innosvet")
STOP = False

EXTRACT_JS = r'''() => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const rxHeader = /^Předpokládaný\s+(přeplatek|nedoplatek)$/i;
  const candidates = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,div,span,p,strong')]
    .filter(el => el.children.length === 0 && rxHeader.test(norm(el.textContent)));
  const numberRx = /(?:^|\s)(\d[\d\s\u00a0\u202f]*,\d{2})\s*Kč(?:\s|$)/i;
  for (const heading of candidates) {
    const typ = norm(heading.textContent).toLowerCase().includes('nedoplatek') ? 'nedoplatek' : 'přeplatek';
    let parent = heading.parentElement;
    for (let depth=0; parent && depth<6; depth++, parent=parent.parentElement) {
      const t = norm(parent.innerText);
      if (t.length > 650) break;
      const found = t.match(numberRx);
      if (found) {
        const ambiguous = /Předpokládaný\s+přeplatek/i.test(t) && /Předpokládaný\s+nedoplatek/i.test(t);
        if (!ambiguous) return {status:'ok', typ, amountText:found[1]};
      }
    }
  }
  return {status: candidates.length ? 'amount_not_found' : 'heading_not_found'};
}'''


def load_options():
    opts = json.loads(OPTIONS.read_text(encoding="utf-8"))
    if not str(opts.get("innogy_username", "")).strip() or not str(opts.get("innogy_password", "")):
        raise ValueError("V Konfiguraci doplňku vyplňte innogy_username a innogy_password")
    for k in ("gas_contract_id", "electricity_contract_id"):
        value = str(opts.get(k, "")).strip()
        if not re.fullmatch(r"\d{5,20}", value):
            raise ValueError("Nejprve nastavte platné číslo smlouvy: " + k)
        opts[k] = value
    opts["timezone"] = str(opts.get("timezone", "Europe/Prague"))
    ZoneInfo(opts["timezone"])
    times = [t.strip() for t in str(opts.get("schedule", "")).split(",") if t.strip()]
    if not times or len(set(times)) != len(times) or any(not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", t) for t in times):
        raise ValueError("schedule musí obsahovat unikátní časy HH:MM oddělené čárkami")
    opts["times"] = sorted(times)
    return opts


def mqtt_connection():
    token = os.getenv("SUPERVISOR_TOKEN", "")
    if not token:
        raise RuntimeError("Chybí SUPERVISOR_TOKEN pro MQTT service discovery")
    request = Request("http://supervisor/services/mqtt", headers={"Authorization": "Bearer " + token})
    with urlopen(request, timeout=15) as response:
        envelope = json.load(response)
    service = envelope.get("data", envelope)
    host = service.get("host")
    if not host:
        raise RuntimeError("MQTT broker není dostupný")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="innosvet_ha_bilance")
    if service.get("username"):
        client.username_pw_set(service["username"], service.get("password", ""))
    if service.get("ssl"):
        client.tls_set()
    client.will_set(STATE_PREFIX + "/availability", "offline", qos=1, retain=True)
    client.connect(host, int(service.get("port", 1883)), keepalive=45)
    client.loop_start()
    return client


def mqtt_publish(client, topic, payload, retain=True):
    info = client.publish(topic, payload, qos=1, retain=retain)
    info.wait_for_publish(timeout=12)
    if not info.is_published():
        raise RuntimeError("MQTT publish nebyl potvrzen")


def publish_discovery(client):
    device = {"identifiers": ["innosvet_finance_readonly"], "name": "innogy innosvět", "manufacturer": "innogy (data)", "model": "Finanční bilance (pouze čtení)"}
    for kind, name in (("plyn", "Plyn"), ("elektrina", "Elektřina")):
        topic = f"{DISCOVERY_PREFIX}/sensor/innosvet_{kind}_bilance/config"
        cfg = {
            "name": f"innosvět {name} – bilance",
            "unique_id": f"innosvet_{kind}_bilance_readonly_v1",
            "state_topic": f"{STATE_PREFIX}/{kind}/state",
            "json_attributes_topic": f"{STATE_PREFIX}/{kind}/attributes",
            "availability_topic": STATE_PREFIX + "/availability",
            "unit_of_measurement": "Kč",
            "device": device,
            "icon": "mdi:cash-check",
        }
        mqtt_publish(client, topic, json.dumps(cfg, ensure_ascii=False))
    mqtt_publish(client, "homeassistant/sensor/innosvet_cteni_stav/config", json.dumps({
        "name": "innosvět – poslední čtení", "unique_id": "innosvet_last_read_status_v1",
        "state_topic": STATE_PREFIX + "/last_read_status",
        "availability_topic": STATE_PREFIX + "/availability",
        "device": device,
        "icon": "mdi:cloud-check",
    }, ensure_ascii=False))
    mqtt_publish(client, STATE_PREFIX + "/availability", "online")


def page_is_authed(page):
    try:
        return (not page.is_closed() and urlparse(page.url).hostname == HOST
                and page.get_by_text("Zprávy a oznámení", exact=False).count() > 0
                and page.get_by_text("Nastavení", exact=False).count() > 0)
    except Exception:
        return False


def find_authenticated(context, seconds):
    limit = time.monotonic() + seconds
    while time.monotonic() < limit:
        for page in reversed(context.pages):
            if page_is_authed(page):
                return page
        pages = [p for p in context.pages if not p.is_closed()]
        if not pages:
            break
        pages[0].wait_for_timeout(500)
    return None


def try_login(context, page, username, password):
    """Experimental: Cognito layout must be verified on HAOS.

    Never submit any form on innosvět's /chci-zaridit/ pages.
    """
    if not username or not password:
        return None
    LOG.info("Relace vypršela; pokus o automatické přihlášení")
    # Identity provider may open another tab, so search all live pages.
    for candidate in reversed(context.pages):
        if candidate.is_closed():
            continue
        # No automatic typing/submission on the energy portal itself.
        domain = urlparse(candidate.url).hostname or ""
        if domain == HOST or not domain.endswith(("amazoncognito.com", "innogy.cz", "innogy.com")):
            continue
        user_field = candidate.locator('input[type="email"],input[name="username"],input[autocomplete="username"]').first
        if user_field.count() == 0:
            continue
        try:
            user_field.fill(username, timeout=5000)
            pass_field = candidate.locator('input[type="password"]').first
            if pass_field.count() == 0:
                # Some login screens use a two-step username flow.
                next_btn = candidate.get_by_role("button", name=re.compile("pokračovat|continue|další|next", re.I)).first
                if next_btn.count() == 0:
                    continue
                next_btn.click(timeout=5000)
                pass_field.wait_for(timeout=12000)
            pass_field.fill(password, timeout=5000)
            submit = candidate.locator('button[type="submit"], input[type="submit"]').first
            if submit.count() == 0:
                continue
            submit.click(timeout=10000)
            return find_authenticated(context, 45)
        except (PWTimeout, Exception):
            # No screenshot, DOM dump, URL, username or password in logs.
            return None
    return None


def read_balances(options):
    PROFILE.mkdir(parents=True, exist_ok=True)
    pages = {
        "plyn": BASE + "/dashboard/detail-smlouvy-plyn/naklady-a-spotreba?contractid=" + options["gas_contract_id"],
        "elektrina": BASE + "/dashboard/detail-smlouvy-elektrina/naklady-a-spotreba?contractid=" + options["electricity_contract_id"],
    }
    results = {}
    with sync_playwright() as playwright:
        context = playwright.firefox.launch_persistent_context(
            user_data_dir=str(PROFILE), headless=True, locale="cs-CZ", accept_downloads=False,
        )
        try:
            # This guard remains active through the whole run. Only the identity
            # provider may use POST for authentication. innosvět can never write.
            def guard(route):
                request = route.request
                if (urlparse(request.url).hostname == HOST
                        and request.method.upper() not in ("GET", "HEAD", "OPTIONS")):
                    route.abort()
                else:
                    route.continue_()
            context.route("**/*", guard)
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(BASE, wait_until="domcontentloaded", timeout=60000)
            active = find_authenticated(context, 35)
            if active is None:
                active = try_login(context, page, options.get("innogy_username", ""), options.get("innogy_password", ""))
            if active is None:
                raise RuntimeError("Přihlášení není dostupné; automatický login nebyl ověřen")
            for kind, link in pages.items():
                active.goto(link, wait_until="domcontentloaded", timeout=60000)
                if urlparse(active.url).hostname != HOST or "/naklady-a-spotreba" not in urlparse(active.url).path:
                    raise RuntimeError("Smlouva není dostupná: " + kind)
                active.get_by_text(re.compile(r"Předpokládaný\s+(přeplatek|nedoplatek)", re.I)).first.wait_for(timeout=20000)
                read = active.evaluate(EXTRACT_JS)
                if read.get("status") != "ok" or read.get("typ") not in ("přeplatek", "nedoplatek"):
                    raise RuntimeError("Bilanci nelze bezpečně rozpoznat: " + kind)
                amount = Decimal(re.sub(r"[\s\u00a0\u202f]", "", read["amountText"]).replace(",", "."))
                if not amount.is_finite() or amount < 0:
                    raise RuntimeError("Neplatná bilance: " + kind)
                signed = amount if read["typ"] == "přeplatek" else -amount
                results[kind] = {"typ": read["typ"], "castka_kc": float(amount), "bilance_kc": float(signed)}
        finally:
            context.close()
    if len(results) != 2:
        raise RuntimeError("Neúplné finanční údaje")
    return results


def save_result(data):
    blob = json.dumps(data, ensure_ascii=False, indent=2)
    temp = RESULT.with_suffix(".json.tmp")
    temp.write_text(blob + "\n", encoding="utf-8")
    temp.replace(RESULT)


def report_ok(client, results, now):
    for kind, obj in results.items():
        mqtt_publish(client, f"{STATE_PREFIX}/{kind}/state", f"{obj['bilance_kc']:.2f}")
        mqtt_publish(client, f"{STATE_PREFIX}/{kind}/attributes", json.dumps({
            "typ": obj["typ"], "castka_kc": obj["castka_kc"], "updated_at": now,
            "source": "innosvet", "read_only": True,
        }, ensure_ascii=False))
    mqtt_publish(client, STATE_PREFIX + "/last_read_status", "ok")


def handle_stop(_signum, _frame):
    global STOP
    STOP = True


def main():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)
    options = load_options()
    tz = ZoneInfo(options["timezone"])
    client = None
    try:
        client = mqtt_connection()
        publish_discovery(client)
        LOG.info("Spuštěno pouze ČTENÍ, časy: %s", ", ".join(options["times"]))
        last_day_slot = None
        first_run = True
        while not STOP:
            now = datetime.now(tz)
            slot = (now.date().isoformat(), now.strftime("%H:%M"))
            due = slot[1] in options["times"] and slot != last_day_slot
            if (first_run and options.get("read_on_start", True)) or due:
                if due:
                    last_day_slot = slot
                try:
                    result = read_balances(options)
                    stamped = datetime.now(tz).isoformat(timespec="seconds")
                    data = {"updated_at": stamped, "source": "innosvet", **result}
                    save_result(data)
                    report_ok(client, result, stamped)
                    LOG.info("Bilance plynu a elektřiny byly načteny a publikovány")
                except Exception as exc:
                    # Do not print URLs, cookies, exception details or credentials.
                    LOG.warning("Čtení selhalo: %s; starší hodnoty zůstávají zachované", type(exc).__name__)
                    mqtt_publish(client, STATE_PREFIX + "/last_read_status", "chyba")
            first_run = False
            for _ in range(20):
                if STOP:
                    break
                time.sleep(1)
    finally:
        if client:
            try:
                mqtt_publish(client, STATE_PREFIX + "/availability", "offline")
                client.loop_stop()
                client.disconnect()
            except Exception:
                pass


if __name__ == "__main__":
    main()
