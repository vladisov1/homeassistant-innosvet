# Kontrola nepotvrzeného odečtu – alpha17

Při nejistém výsledku finálního zápisu otevřete v Home Assistantu zařízení **innogy innosvět** (integrace MQTT). Senzor „innosvět – kontrola odečtu“ zobrazí datum, čas a hodnotu nejstaršího nevyřešeného pokusu.

1. Otevřete historii odečtů přímo v innosvětě a ověřte konkrétní čas a hodnotu.
2. Pokud odečet v historii je, použijte tlačítko **Odečet JE v innosvětě – potvrdit**.
3. Pokud v historii není, použijte tlačítko **Odečet NENÍ v innosvětě – potvrdit**.
4. Aplikace zapíše výsledek do `/data/gas_write_journal.json` a neprovede žádné okamžité odeslání. Nový zápis se může uskutečnit až v dalším naplánovaném termínu, pokud je povolen.

Při několika nevyřešených pokusech potvrzujte postupně nejstarší; po každém potvrzení se tlačítka aktualizují. Pokud nebyla historie ověřena, žádné tlačítko nepoužívejte.

**Důležité:** Tato verze je testovací. MQTT tlačítka jsou dostupná uživatelům s příslušnými oprávněními v Home Assistantu. Zápis v portálu innosvět není automaticky kontrolován. Funkci nejprve testujte se skutečným odesíláním vypnutým.
