# Graf nákladů innosvět v Home Assistantu

Karta se dodává jako samostatný soubor JavaScript, aby nebylo nutné instalovat HACS nebo další knihovnu. Samotná instalace doplňku **automaticky nevkládá kartu do dashboardu**; toto je záměrné. Při aktualizaci doplňku zůstanou všechny dosavadní karty nedotčené.

1. Ověřte, že je v nastavení doplňku `finance_extra_enabled: true` a že oběma finančním senzorům přibyl atribut `body_grafu` s 13 body. V **Nástroje pro vývojáře → Stavy** si poznamenejte přesné `entity_id` senzorů „innosvět Plyn – dosavadní náklady innogy“ a „innosvět Elektřina – dosavadní náklady innogy“.
2. Zkopírujte `innosvet-cost-chart.js` do složky `/config/www/innosvet-cost-chart.js` ve své instalaci Home Assistantu (například přes File editor nebo Samba).
3. V **Nastavení → Dashboardy → Zdroje** přidejte `/local/innosvet-cost-chart.js` jako **JavaScript modul**. U některých verzí Home Assistantu je nabídka Zdroje vidět až po zapnutí pokročilého režimu uživatele.
4. V úpravě dashboardu zvolte **Ruční kartu** a vložte YAML, v němž nahradíte `gas_entity` a `electricity_entity` skutečnými identifikátory z kroku 1:

```yaml
type: custom:innosvet-cost-chart
title: Vývoj nákladů innosvět
gas_entity: sensor.VAS_SKUTECNY_SENZOR_PLYNU
electricity_entity: sensor.VAS_SKUTECNY_SENZOR_ELEKTRINY
```

Po přidání zdroje případně obnovte stránku prohlížeče s vymazáním cache.

## Význam grafu

- Modrá křivka: `naklady_kc` (průběžný výpočet a odhad dodavatele).
- Oranžová přerušovaná křivka: `podle_zaloh_kc` (srovnávací hodnoty dle dat innogy; **nejde o potvrzení připsání jednotlivých plateb**).
- Šedé pozadí označuje měsíce **po aktuálním měsíci**, pokud jej lze nalézt v atributech. Současný měsíc může zahrnovat odhad.
- Data se obnovují automaticky ze stavů entit Home Assistantu. Karta neposílá žádné požadavky do innosvěta.
- Graf není senzor `total_increasing` pro Energy Dashboard, protože výpočty dodavatele se mohou zpětně měnit.
