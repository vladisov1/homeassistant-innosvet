# Závěrečný denní odečet – alpha18

Při posledním plánovaném termínu, např. 23:55, doplněk uloží stav senzoru do `/data/gas_write_journal.json` ještě před komunikací s portálem. Uložení probíhá i při kontrolním režimu. Ve vypnutém zápisu se zachová jako `not_sent`.

MQTT senzor `innosvět – denní závěrečný odečet` ukazuje nejstarší nevyřízený místně uložený denní stav, datum, hodnotu a status.

Tlačítko `innosvět – odeslat uložený denní odečet` funguje pouze při zapnutých **obou** povoleních odeslání, pro minulý den a pro jednoznačně neodeslaný (`not_sent`) či uživatelem ověřený nezapsaný (`verified_not_recorded`) stav. Stisk znamená **skutečný pokus o odeslání**. Před stiskem porovnejte datum a stav se záznamy innosvěta. MQTT tlačítko s payloadem NONE nic nedělá.

Pokud má původní pokus nejednoznačný výsledek, nelze jej automaticky opakovat. Ověření přes dvě stávající tlačítka kontroly odečtů z alpha17 je dostupné, avšak portál neuvádí čas všech dílčích zápisů; jednotlivý pokus proto nemusí být možné zpětně jednoznačně ověřit. Nepotvrzujte údaje, které nelze doložit.

Historický opravný zápis používá původní uloženou hodnotu a vyplňuje původní datum. Pokud pole Date nejde bezpečně vyplnit obvyklým způsobem, zápis se ukončí bez POST. Oprava zachová nový samostatný auditní pokus; původní pokus se nemění. Výpadky samotného HA v čase 23:55 nedokážeme bez historického zdroje doplnit zpětně.

**Stav:** Provedeny pouze lokální testy; neověřeno proti živému portálu ani proti skutečnému nastavení HAOS.
