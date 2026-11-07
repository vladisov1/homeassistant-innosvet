## 0.1.0-alpha10 (2026-11-07) – rozpoznání období BillsGraph

- Po úspěšném zachycení JSON nákladů se období určuje přednostně z `Date`, `Year` a `Period` jednotlivých položek.
- Při různých formátech kalendářního data se používají přísná pravidla, nikoliv odhad podle aktuálního měsíce.
- Pokud datová pole nejsou použitelné, zkouší se datum z textu a HTML stránky.
- Pokud nelze období jednoznačně určit, nové náklady se nepublikují a existující hodnoty zůstávají zachované.
- V protokolu je bezpečný zdroj rozpoznaného období, bez čísla smlouvy, přihlašovacích údajů a raw JSON.
- Automatické odesílání plynoměru, načítání bilancí a rozpis záloh beze změn.
- Oprava otestována syntakticky a unit-testy; ověření na skutečném HAOS stále čeká.

## 0.1.0-alpha9 (2026-11-07) – oprava čtení BillsGraph

- Zachytávání `BillsGraph` začíná už před prvním otevřením detailu smlouvy, nikoliv až po načtení bilance.
- Síťový posluchač si pouze uloží odpověď; JSON zpracuje až následně mimo událost Playwrightu.
- Bezpečné diagnostické kódy odlišují chybějící AJAX, neplatnou odpověď, schéma a nepřiřaditelné období, bez logování URL, tokenů nebo HTML.
- Nezměněné načítání záloh, MQTT entity, harmonogram a odesílání plynoměru. Žádná deduplikace stejných odečtů.
- Dosud neověřeno v běžícím HAOS; nové finanční čtení zůstává volitelné.

## 0.1.0-alpha8 (2026-11-07) – rozšířené finance, testovací vydání

- Volitelné čtení `BillsGraph` pro plyn a elektřinu (13 bodů vývoje nákladů).
- Nová podrobná evidence předepsaných záloh z HTML včetně splatnosti, započtené platby a zůstatku, s rozdílnými budoucími částkami.
- Šest nových MQTT senzorů na energii: průběžné náklady dle innogy (hodnota bodu aktuálního měsíce), náklady podle záloh, odhad na konci období, předepsaná záloha, zbývající budoucí zálohy, nejbližší neuhrazená částka.
- Atributy s podkladovými měsíčními body a platebním kalendářem (bez hesel a identifikátorů smluv).
- Původní automatické odeslání plynu a čtení přeplatku/nedoplatku zachováno.
- Rozšířené finance **výchozí vypnuté**, protože ještě nejsou fyzicky otestované v HAOS.
- **Zatím neimplementováno:** grafová karta Lovelace a automatické doporučení změny záloh. Surové měsíční body pro budoucí graf se zveřejňují jako atributy.

## 0.1.0-alpha7 (2026-11-07) – diagnostika kliknutí a bezpečný klávesový fallback

- Po alpha6, kde tlačítko Pokračovat bylo viditelné/aktivní, ale Playwright kliknutí skončilo TimeoutError bez POST.
- Přidána kontrola zásahu středu tlačítka a přítomnosti překryvného prvku (bez citlivých dat v logu).
- Pokud kliknutí skončí TimeoutError a nebyl zachycen žádný POST, znovu se ověří nezměněný formulář a provede se **jedno** stisknutí Enter na témže tlačítku.
- Přísná síťová brána nadále povoluje nejvýše jeden POST v každém ze dvou kroků. Při nejistotě se zápis neobnovuje.
- Obě akce finálního potvrzení jsou v HAOS nadále experimentální; první ostrý běh vyžaduje sledování a kontrolu historie.

# Changelog

## 0.1.0-alpha6 (2026-11-07) – diagnostika prvního potvrzení

- Oprava a podrobnější bezpečná diagnostika prvního kroku „Pokračovat“ po TimeoutError v alpha5.
- Rozlišeno vyhledání a kliknutí na tlačítko, počet POST požadavků, HTTP odpověď a přítomnost rekapitulace.
- POST brána se zavírá ihned po prvním povoleném požadavku.
- Ponechán kontrolní režim bez odeslání i blokování automatického opakování. Ostrá větev nadále neověřená.

## 0.1.0-alpha5 (2026-11-07) – řízená dvoukroková větev zápisu

- Zachován ověřený kontrolní režim alpha4: otevření a vyplnění formuláře bez POST.
- V ostrém režimu po dvou výslovných souhlasech proběhne kontrola formuláře, „Pokračovat“, kontrola rekapitulace a „Odeslat odečet“.
- Každý potvrzovací krok smí povolit pouze jeden POST na ověřenou cestu formuláře; ostatní nečtecí požadavky na innosvět se blokují.
- Pro oba POST se vyžaduje úspěšná HTTP odpověď a po finálním kroku textové potvrzení portálu. Pokud se portál změnil, výsledek se označí za nejistý.
- Deník na disku brání automatickému opakování stejného plánovaného termínu po chybě nebo restartu.
- **Automatické odeslání nebylo ověřeno end-to-end v HAOS.** Odeslání zůstává výchozím nastavením vypnuté, první ostrý test musí být dozorovaný.

## 0.1.0-alpha4 (2026-11-07) – bezpečný test formuláře plynu

- Kontrolní režim (`gas_write_enabled: true`, `gas_write_confirmed: false`) nyní kromě čtení senzoru skutečně otevře innosvět, vybere plynovou smlouvu, prověří pole data a stavu a vyplní odečet.
- V kontrolním režimu jsou všechny nečtecí HTTP požadavky na `innosvet.innogy.cz` blokované; nekliká se na „Pokračovat“ ani na „Odeslat odečet“.
- Stav `preview_form_ready` znamená vyplněný a zkontrolovaný formulář **před prvním odesílacím krokem**, nikoliv potvrzenou rekapitulaci.
- Bezpečný protokol uvádí fázi případného selhání bez přihlašovacích údajů či obsahu požadavků.
- Ostrý automatický zápis nadále nebyl ověřen v HAOS a má zůstat vypnutý.


## 0.1.0-alpha3 (2026-11-07) – oprava testu zápisu

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
