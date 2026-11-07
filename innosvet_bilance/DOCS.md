# innosvět – finanční bilance (ALPHA 0.1.0-alpha8)

Testovací doplněk pro Home Assistant OS, **výhradně pro čtení** částky předpokládaného přeplatku nebo nedoplatku elektřiny a plynu z innosvěta. Zobrazené bilance pouze přenáší, nepočítá je.

**ZÁPIS PLYNOMĚRU JE NOVĚ POUZE EXPERIMENTÁLNÍ A VE VÝCHOZÍM STAVU VYPNUTÝ.** Ve čtecím režimu se blokují všechny nečtecí požadavky na `innosvet.innogy.cz`. Odeslání vyžaduje dva explicitní přepínače a zatím nebylo ověřeno v HAOS.

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

✅ Čtení obou finančních bilancí, přihlášení a MQTT discovery byly následně uživatelsky ověřeny také v HAOS. Kontrolní režim alpha4 i ostrý zápis alpha7 byly následně uživatelsky ověřeny v HAOS; tato část popisuje stav před těmito testy.


## Automatický zápis plynoměru – nové experimentální nastavení

- `gas_entity_id`: entita plynoměru v Home Assistantu, např. `sensor.plynomer_celkovy_stav`.
- `gas_write_enabled`: **výchozí `false`**. `true` aktivuje kontrolu senzoru a bezpečné otevření/vyplnění webového formuláře v plánovaných časech.
- `gas_write_confirmed`: **výchozí `false`**. Teprve při současném `true` obou přepínačů může dojít ke skutečnému odeslání. Neaktivujte bez následného řízeného testu.
- `schedule`: společné časy čtení finančních bilancí a případného zápisu odečtu, např. `05:55,11:55,17:55,23:55`.
- `read_on_start`: při startu provede pouze načtení finančních bilancí, **nikoliv** odeslání plynoměru.

Před odesláním aplikace kontroluje existenci senzoru, číselný stav, jednotku
`m³`, neklesající odečet vůči poslednímu úspěšnému zápisu v aplikaci, datum
v otevřeném formuláři a jednoznačně rozpoznanou plynovou smlouvu. Číslo
odesílá v celých m³ odříznutím desetinných míst. Formulář nejprve otevře
stránku „Zadat průběžný odečet“, zkontroluje datum a hodnotu na stránce
„Shrnutí před odesláním“ a teprve poté použije „Odeslat odečet“.

Po potvrzení „Odečet byl odeslán“ uloží výsledek. Před pokusem ukládá do
`/data/gas_write_journal.json` záznam termínu; pokud program skončí před
jednoznačným potvrzením, **tentýž termín znovu automaticky neodešle**.
Nepřepisujte ani nemažte tento deník, pokud potřebujete zachovat ochranu
před duplicitou. Denní stejné hodnoty jsou povolené.

Důležité: přijetí dvoustupňového zápisu bylo ověřeno ručně v prohlížeči,
**nebylo ověřeno automatické potvrzení obou kroků skriptem ani ostrý provoz
v HAOS**. V první fázi použijte `gas_write_enabled: true` a
`gas_write_confirmed: false` a prohlédněte si protokol. Vstup do ostrého
režimu vyžaduje vědomé zapnutí druhého přepínače. Chybný údaj může ovlivnit
zobrazenou historii a finanční bilanci v innosvětě.

## Jak zjistit ID smlouvy

V innosvětě otevřete požadovanou smlouvu → **Náklady a spotřeba** a v
adresním řádku najděte parametr `contractid`. Příklady s **fiktivními** ID:

- Plyn: `https://innosvet.innogy.cz/dashboard/detail-smlouvy-plyn/naklady-a-spotreba?contractid=1234567890`
- Elektřina: `https://innosvet.innogy.cz/dashboard/detail-smlouvy-elektrina/naklady-a-spotreba?contractid=9876543210`

Číslo za `contractid=` se vkládá do `gas_contract_id` či `electricity_contract_id`.
Nejde o EAN, EIC ani číslo měřidla.


### Oprava alpha3 – senzor HA a bezpečný test

Doplněk potřebuje v manifestu `homeassistant_api: true`, protože čte `sensor.plynomer_celkovy_stav` prostřednictvím `/core/api/states/...`. `gas_write_enabled: true` a `gas_write_confirmed: false` v alpha3 jen ověřily senzor. **V alpha4 navíc otevřou a vyplní formulář plynu bez jediného POST na innosvět**. Později bylo skutečné odeslání v alpha7 uživatelsky ověřeno. Před každým dalším zapnutím zvažte provozní riziko plánovaných zápisů. Názvy a popisy nastavení jsou přeloženy v `translations/cs.yaml`.

### Alpha4 – co ověří kontrolní režim

Při naplánovaném čase se otevře správná smlouva, stránka „Průběžný odečet“, zkontroluje se datum a jednotka, vyplní se celá hodnota m³. Úspěšný protokol hlásí `preview_form_ready`. **Na „Pokračovat“ se nekliká**, protože formulář používá POST a není nezávisle ověřeno, že už tento krok nemůže změnit data. Nezobrazí se tedy skutečná rekapitulace. Veškeré měnící HTTP požadavky přímo na innosvět jsou v kontrolním režimu blokované. Pro produkční odesílání ponechte `gas_write_confirmed: false` do samostatného ověření.

## Poznámka k alpha5 (experimentální ostrý zápis)

Ověřeno uživatelem: kontrolní režim alpha4 prošel až k vyplnění formuláře (bez POST). V alpha5 přibyla tehdy **dosud nevyzkoušená** dvoukroková ostrá větev; v alpha7 byl tento postup později úspěšně otestován. Je vypnutá, dokud nejsou zapnuté oba přepínače `gas_write_enabled` a `gas_write_confirmed`. Ostrý režim je určen jen pro vědomý, sledovaný test; poté ověřte zapsanou hodnotu v historii innosvěta. Při neočekávané změně formuláře nebo nepotvrzené odpovědi doplněk zápis neopakuje a v deníku `/data/gas_write_journal.json` zachová stav pokusu. Doba plánování se řídí společným polem `schedule`.


## Rozšířené finance (alpha8 – testovací)

V nastavení zapněte **Načítat rozšířené finanční údaje** (`finance_extra_enabled`). Při příštím plánovaném čtení nebo startu s `read_on_start=true` se doplněk pokusí získat:

- `BillsGraph` pro obě smlouvy, z něhož počítá bod aktuálního měsíce (tzv. průběžné náklady, které mohou zahrnovat odhad do konce měsíce), referenční náklady podle záloh a odhad ke konci období.
- `/platby/zalohy` pro každou smlouvu. Každá záloha je samostatný záznam s částkou předpisu, započtenou úhradou, zbývající částkou, splatností a stavem. Příští měsíc nemusí mít stejnou částku.

V Home Assistantu mají vzniknout pro každou energii entity: `dosavadni_naklady_kc`, `predpoklad_podle_zaloh_kc`, `odhad_konec_obdobi_kc`, `mesicni_zaloha_kc`, `budouci_zbyva_kc`, `nejblizsi_zbyva_kc` s prefixem zařízení „innosvět“. Jejich atributy obsahují `body_grafu` a `platebni_kalendar`. Nejde o 365 denních měření, ta nadále zůstávají v Home Assistantu.

**Význam:** částky z grafu jsou odhady/výpočty dodavatele, nikoli konečné faktury. Bod současného měsíce může obsahovat odhad do konce měsíce. Z dat nezjišťujeme spolehlivě jednotkovou cenu 1 m³. Zálohy nijak neměníme ani neplatíme. Historie plateb není samostatně vyúčtováním.

**Pro první test** ponechte skutečný zápis plynu vypnutý, zapněte rozšířené finance a restartujte. Protokol by měl obsahovat „graf nákladů načten“ a „rozpis záloh načten“ u obou energií. Pokud část neprojde, původní bilance zůstane použitelná a starší rozšířené hodnoty se nemají přepisovat. V tomto vydání se doporučená výše zálohy automaticky nevypočítává a není součástí UI; bude navržena až po ověření zaúčtování částečných úhrad a správného vyúčtovacího období.
