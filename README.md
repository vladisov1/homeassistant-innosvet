# innogy innosvět – Home Assistant OS (0.1.0-alpha10)

Aktuální alfa doplněk rozšiřuje funkční bilanci obou smluv a dříve otestovaný automatický zápis plynoměru o **volitelné čtení nákladů a záloh**. Podrobnosti v [DOCS](innosvet_bilance/DOCS.md) a [CHANGELOG](innosvet_bilance/CHANGELOG.md).

- Dříve uložené přihlašovací údaje, smlouvy, entity a časy se nepřejmenovávají.
- `finance_extra_enabled` je nová volitelná volba, standardně `false`.
- `gas_write_enabled` a `gas_write_confirmed` zůstávají nezávislé.

**Neinstalujte bez zálohy. Rozšířené finance nejsou zatím ověřené v HAOS; pokud selže jejich rozpoznání, dosavadní finanční bilance mají zůstat funkční.**
