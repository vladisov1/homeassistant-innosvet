# Bezpečné vyřešení nepotvrzeného odečtu (alpha16)

Před jakýmkoli odblokováním ověřte na innosvětě historii odečtů pro správnou smlouvu a datum. Nepotvrzený zápis může ve skutečnosti uspět.

Pro událost **2026-11-11 18:00, 16 312 m³** uživatel potvrdil, že v historii innosvěta záznam není. Po **záloze** dat doplňku otevřete Konfiguraci a zadejte do nového pole `gas_review_failed_attempt` přesně:

`2026-11-11T18:00|16312|NOT_RECORDED`

Potom uložte konfiguraci a **restartujte doplněk**. Při startu se pouze upraví stav přesně odpovídajícího pokusu v `/data/gas_write_journal.json` na `verified_not_recorded` a zaznamená se původní stav. Žádný odečet se v okamžiku restartu neodešle. V logu ověřte `ručně uzavřen nezapsaný odečet`.

Po potvrzení **vymažte pole `gas_review_failed_attempt`**, uložte a restartujte doplněk, aby se tento jednorázový operátorský pokyn nadále nepoužíval. Opakované zadání stejného tokenu nic nemění.

Následující naplánovaný čas může odeslat aktuální hodnotu. Při výskytu bezpečnostní výzvy, chybné rekapitulace nebo nejednoznačného výsledku se automatické opakování neprovádí. Nesnižujte přitom bezpečnostní přepínače `gas_write_enabled` a `gas_write_confirmed` a nemažte deník.

**Upozornění:** jde o neotestovanou alfa aktualizaci. Před nasazením zálohujte konfiguraci a `/data`, zejména `gas_write_journal.json`; změnu proveďte nejprve pod dohledem. Zdrojový balíček nevytváří žádný automatický mechanismus instalace ani migrace historie.
