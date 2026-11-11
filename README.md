# innogy innosvět – Home Assistant OS (0.1.0-alpha17)

Aktuální alfa doplněk rozšiřuje funkční bilanci obou smluv a dříve otestovaný automatický zápis plynoměru o **volitelné čtení nákladů a záloh**. Podrobnosti v [DOCS](innosvet_bilance/DOCS.md) a [CHANGELOG](innosvet_bilance/CHANGELOG.md).

- Dříve uložené přihlašovací údaje, smlouvy, entity a časy se nepřejmenovávají.
- `finance_extra_enabled` je nová volitelná volba, standardně `false`.
- `gas_write_enabled` a `gas_write_confirmed` zůstávají nezávislé.

**Neinstalujte bez zálohy. Finanční čtení alpha10 bylo ověřeno v HAOS. Nová aktivace finálního tlačítka alpha12 vyžaduje samostatný dozorovaný test; při nejistém výsledku kontrolujte historii v innosvětě.**

### Novinky alpha13

- Volitelná optimalizace odesílání plynoměru (`gas_write_optimized`, **výchozí vypnuto**).
- Přiložená grafová karta bez závislostí: [návod k instalaci](innosvet_bilance/dashboard/DASHBOARD-GRAF.md). Vyžaduje samostatné ruční přidání do Home Assistant dashboardu.
- Ostrý test alpha13 na skutečném innosvětě dosud neproběhl; zachován ověřený postup finálního potvrzení alpha12.

Nové cenové senzory alpha15: [CENOVE-SENZORY.md](innosvet_bilance/CENOVE-SENZORY.md).

### Alpha17 – kontrola nepotvrzených odečtů

Doplněk publikuje přes MQTT nový senzor **innosvět – kontrola odečtu** a dvě tlačítka potvrzení historie. Tlačítka se používají jen po ruční kontrole historie na portálu; nikdy sama neodesílají odečet. Při více nevyřešených pokusech se řeší nejstarší. Testujte nejprve s vypnutým skutečným odesíláním.
