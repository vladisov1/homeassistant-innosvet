# Changelog

## 0.1.0-alpha4 (2026-11-07) – bezpečný test formuláře plynu

- Kontrolní režim (`gas_write_enabled: true`, `gas_write_confirmed: false`) nyní kromě čtení senzoru skutečně otevře innosvět, vybere plynovou smlouvu, prověří pole data a stavu a vyplní odečet.
- V kontrolním režimu jsou všechny nečtecí HTTP požadavky na `innosvet.innogy.cz` blokované; nekliká se na „Pokračovat“ ani na „Odeslat odečet“.
- Stav `preview_form_ready` znamená vyplněný a zkontrolovaný formulář **před prvním odesílacím krokem**, nikoliv potvrzenou rekapitulaci.
- Bezpečný protokol uvádí fázi případného selhání bez přihlašovacích údajů či obsahu požadavků.
- Ostrý automatický zápis nadále nebyl ověřen v HAOS a má zůstat vypnutý.


## 0.1.0-alpha4 (2026-11-07) – oprava testu zápisu

- **Opraveno oprávnění k senzorům HA:** `homeassistant_api: true` v `config.yaml`. Předchozí varianta nedovolovala přístup přes `/core/api/states/` a mohla končit `HTTPError`.
- Při chybě načtení senzoru se nově zapisuje bezpečná diagnostika HTTP 401/403/404 bez tokenů či citlivých odpovědí.
- České názvy a stručné vysvětlivky všech konfiguračních položek přes `translations/cs.yaml`. Technické názvy zůstávají zachovány.
- **Kontrolní režim ověřuje dostupnost a hodnotu senzoru**, nikoli vyplnění formuláře innosvěta. Před skutečným odesláním je třeba samostatný test navigace a potvrzení.
- Skutečný automatický zápis plynu **není dosud ověřen v HAOS** a má zůstat zakázán (`gas_write_confirmed: false`).

# Changelog

## 0.1.0-alpha (2026-11-06)

- Zachována testovací větev 0.1.0-alpha (bez navyšování verze).
- Výslovně zdokumentováno jednorázové zadání loginu a hesla v konfiguraci doplňku (již podporovaná pole `innogy_username`, `innogy_password`).
- Přihlašovací údaje nejsou součástí zdrojového kódu ani distribučního ZIPu.
- GitHub repozitář se souborem `repository.yaml`; pouze čtení finančních bilancí elektřiny a plynu přes MQTT.
- Experimentální automatické obnovení přihlášení; v HAOS zatím neověřeno.
- **Zápis plynoměru není implementován.**

### Rozpracované rozšíření 0.1.0-alpha (neověřeno v ostrém provozu)
- Přidána opt-in funkce zápisu stavu plynoměru ze senzoru HA v časech `schedule`.
- Výchozí zápis vypnut, druhý potvrzovací přepínač a deník proti opakování.
- Přidán MQTT stav pokusu o odeslání plynu.
- Doplněn postup pro zjištění `contractid` a upozornění na neověřené automatické odeslání.
