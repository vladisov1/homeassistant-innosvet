# Cenové senzory – alpha15

Při zapnutém `finance_extra_enabled` čte add-on během běžného finančního běhu dvě odpovědi innosvět: `BillsGraph` (13 měsíčních bodů) a `ConsumptionGraph` (365 denních bodů). Nové přihlášení ani druhý cyklus procházení portálu nejsou potřeba.

## MQTT Discovery

- `innosvet_plyn_prumerna_cena_v1`: **innosvět Plyn – předpokládaná průměrná cena**, jednotka `Kč/m³`, topic `innosvet_ha/plyn/finance/prumerna_cena`.
- `innosvet_elektrina_prumerna_cena_v1`: **innosvět Elektřina – předpokládaná průměrná cena**, jednotka `Kč/kWh`, topic `innosvet_ha/elektrina/finance/prumerna_cena`.

Výsledná entity_id Home Assistantu se může lišit podle již existujících entit; pro její dohledání použijte **Nastavení → Zařízení a služby → MQTT → innogy innosvět** nebo vyhledání podle názvu.

### Vzorec

`poslední BillsGraph.CurrentPeriodValue / poslední ConsumptionGraph.CurrentPeriodValue`

Čitatel = předpokládané náklady za celé období, nikoli předepsané zálohy (`PreviousPeriodValue`). Jmenovatel = předpokládaná kumulativní spotřeba za stejné období: kWh elektřiny, m³ plynu. Hodnota se publikuje se čtyřmi desetinnými místy. Nejde o variabilní tarifní sazbu, ale o roční průměr obsahující poměrnou část stálých nákladů, pokud je zahrnuje model dodavatele.

### Kontroly

Vyžaduje se 13 po sobě jdoucích měsíčních intervalů v `BillsGraph.Period`, 365 nepřerušených denních dat v `ConsumptionGraph.Date`, stejné počáteční a koncové datum a kladné konečné náklady i spotřeba. Neplatná, chybějící nebo neshodná data **nepřepíšou** poslední publikovanou cenu. Pokud není ještě žádná validní hodnota, senzor nemá stav. Datum poslední úspěšné aktualizace, období a vstupní čísla najdete v atributech MQTT senzoru.

### Nasazení

1. Rozbalte celý ZIP do zdrojového repozitáře Home Assistant add-onu, se zachováním struktury složek, a zveřejněte změny na GitHubu.
2. Aktualizujte doplněk v Home Assistant OS na verzi `0.1.0-alpha15`; zkontrolujte, že je zapnuté `finance_extra_enabled`.
3. Po úspěšném finančním běhu vyhledejte v MQTT zařízení `innogy innosvět` dvě nové cenové entity a zkontrolujte jejich atributy.
4. V energetickém panelu lze použít cenovou entitu při odpovídající jednotce spotřebního měřiče. Jde o orientační průběžné náklady, nikoli o reprodukci faktury.

**Poznámka ke grafové kartě:** Přiložený JS soubor zachovává poslední samostatně dodaný vizuální návrh alpha14. Aktualizace add-onu nepřepíše existující kopii v `/config/www/`; tu není nutné měnit kvůli novým cenovým senzorům.
