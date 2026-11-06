# innosvět – finanční bilance (ALPHA 0.1.0-alpha)

Testovací doplněk pro Home Assistant OS, **výhradně pro čtení** částky předpokládaného přeplatku nebo nedoplatku elektřiny a plynu z innosvěta. Zobrazené bilance pouze přenáší, nepočítá je.

**ZÁPIS PLYNOMĚRU NENÍ V TÉTO VERZI IMPLEMENTOVÁN.** Není zde tlačítko, příkaz ani plánovač pro odeslání odečtu. Všechny nečtecí požadavky na `innosvet.innogy.cz` se blokují.

## Požadavky

- HAOS na **amd64/x86-64** (jiné architektury zatím nemají ověřený obraz Playwright/Firefox).
- Nainstalovaný a funkční Mosquitto broker + integrace MQTT v Home Assistantu.
- Připojení k internetu.
- Čísla smluv pro elektřinu a plyn, která zadáte v nastavení doplňku.

## Instalace z GitHub repozitáře

1. Nahrajte obsah distribučního ZIPu do vlastního GitHub repozitáře (v kořeni musí být `repository.yaml`).
2. V Home Assistantu otevřete **Nastavení → Aplikace → Instalovat aplikaci → ⋮ → Repozitáře** a vložte URL GitHub repozitáře.
3. Vyberte doplněk **innosvět – finanční bilance (ALPHA)** a nainstalujte jej.
4. V nastavení zadejte `gas_contract_id` a `electricity_contract_id`, přihlašovací jméno a heslo do innosvěta. Jméno/heslo nemusíte při běžném restartu doplňovat.
5. Spusťte doplněk a zkontrolujte **Protokol**.
6. Po úspěšném čtení se přes MQTT discovery objeví entity s názvy **innosvět Plyn – bilance** a **innosvět Elektřina – bilance**. Ve vlastnostech senzorů je typ (`přeplatek`/`nedoplatek`) a čas posledního úspěšného načtení.

## Důležité omezení prvního vydání

**První automatické přihlášení do innosvěta z prostředí HAOS ještě nebylo ověřeno.** Na Windows byl ověřen pouze přenos přihlašovací relace v rámci stejného profilu Playwright Firefoxu. Profil Firefoxu z Windows **nelze považovat za přenositelný** do HAOS. Doplněk umí experimentálně vyplnit uložené jméno a heslo na podporovaných obrazovkách přihlášení poskytovatele identity; pokud innogy používá jinou strukturu přihlášení, MFA nebo CAPTCHA, přihlášení selže a uživatelský zásah či úprava doplňku bude nutná.

Nepředávejte autorovi/ChatGPT žádné heslo, cookies ani soubory prohlížečového profilu. Heslo v nastavení HAOS není hardwarově šifrovaný trezor; konfiguraci, zálohy a `/data/browser_profile` je třeba chránit jako přihlašovací údaje.


## Jednorázové zadání přihlašovacích údajů

V kartě doplňku otevřete záložku **Konfigurace** a vyplňte:

- **`innogy_username`** – přihlašovací jméno/e-mail do innosvěta.
- **`innogy_password`** – heslo do innosvěta (v konfiguraci typu `password`, tedy maskované při zadávání).
- **`gas_contract_id`** a **`electricity_contract_id`** – čísla obou smluv.

Konfiguraci uložte. Při běžném restartu nebo aktualizaci doplňku tyto údaje zůstávají v jeho nastavení; nevyplňují se znovu, dokud je sami nezměníte. Při přihlášení skript nejprve použije uloženou relaci a po jejím vypršení se pokusí o nové přihlášení z uložených údajů. **Nové automatické přihlášení v HAOS zatím není ověřeno** a může selhat na MFA/CAPTCHA.

Heslo se neukládá do `app.py`, do repozitáře GitHub ani se nevypisuje do protokolu. Maskování pole není šifrování – chraňte přístup do HAOS i jeho zálohy.

## Harmonogram

Výchozí časy: `05:55,11:55,17:55,23:55` v `Europe/Prague`. Čtení proběhne navíc při spuštění, pokud je `read_on_start: true`. Obě bilance se aktualizují nezávisle na stavu plynoměru. Při neúspěchu poslední naměřené hodnoty zůstávají, pouze stavový senzor hlásí `chyba`.

## Výstup a bezpečnost

- MQTT discovery: dva číselné senzory se znaménkem (přeplatek +, nedoplatek −); absolutní částka a textový typ jsou v atributech.
- Trvalý JSON: `/data/last_read.json`.
- Trvalý prohlížečový profil: `/data/browser_profile/`.
- Při odstranění doplňku/smazání dat profilu bude pravděpodobně nutné přihlásit se znovu.
- Žádná měřená elektřina se do HA nepřenáší, žádné finance se lokálně nepřepočítávají.

## Stav ověření

✅ Čtení obou hodnot, obnova relace a headless běh ověřeny na Windows (test v10c).

⚠️ **Sestavení Docker image, automatické přihlášení na HAOS a doručení MQTT discovery zatím nebyly ověřeny na skutečné instalaci HAOS.** Jde o testovací vydání. Nepovažujte jej za produkční integraci.
