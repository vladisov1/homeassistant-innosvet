# innosvět – finanční údaje a zápis plynu (ALPHA 0.1.0-alpha18)

Home Assistant OS doplněk pro **čtení finančních údajů innogy** a volitelný automatický zápis stavů plynoměru. Stavy plynu se získávají přímo ze senzoru Home Assistantu; elektřina se **nikdy nezapisuje**.

- Funkční původní čtení přeplatků a nedoplatků pro obě energie.
- Nové volitelné čtení grafu nákladů (`BillsGraph`) a skutečného platebního kalendáře záloh, včetně částečných úhrad a rozdílných částek v jednotlivých měsících.
- MQTT senzory pro částky a atributy s třinácti body grafu i celým rozpisem záloh.
- Zachován ověřený zápis plynoměru z alpha7; výchozí nastavení zápisu je vypnuté.

**Rozšířené finance jsou zatím testovací:** přepínač „Načítat rozšířené finanční údaje“ je zpočátku vypnutý. Po aktualizaci se nezapne zápis plynu ani nové finanční čtení samo.

Podrobnosti a přesný rozsah: [DOCS.md](DOCS.md). Změny: [CHANGELOG.md](CHANGELOG.md).

Cenové senzory přidané v alpha15: [CENOVE-SENZORY.md](CENOVE-SENZORY.md).

Historické denní odečty alpha18: [DOPLNENI-DENNIHO-ODECTU.md](DOPLNENI-DENNIHO-ODECTU.md).
