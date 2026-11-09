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

- Fialová plná část: `naklady_kc` (dosavadní výpočet innogy, včetně průběžného aktuálního měsíce).
- Fialová přerušovaná část: budoucí prognóza `naklady_kc`.
- Oranžová plná křivka: `podle_zaloh_kc` (srovnávací hodnoty dle dat innogy; **nejde o potvrzení připsání jednotlivých plateb**).
- Šedé pozadí označuje měsíce **po aktuálním měsíci**, pokud jej lze nalézt v atributech. Současný měsíc může zahrnovat odhad.
- Data se obnovují automaticky ze stavů entit Home Assistantu. Karta neposílá žádné požadavky do innosvěta.
- Graf není senzor `total_increasing` pro Energy Dashboard, protože výpočty dodavatele se mohou zpětně měnit.

## Změna pro alpha14

Po aktualizaci doplňku na alpha14 **ručně nahraďte** `/config/www/innosvet-cost-chart.js` novou verzí ze složky `dashboard` a obnovte stránku prohlížeče (Ctrl+F5). Aktualizace doplňku soubor v `/config/www` sama nemění. YAML karty a entity mohou zůstat stejné.

Fialová plná část zobrazuje výpočet innogy do aktuálního měsíce (který může obsahovat odhad), fialová přerušovaná budoucí měsíce, oranžová referenci podle záloh. Kliknutím na bod lze zobrazit Kč a jejich rozdíl.

### Oprava ovládání hodnot grafu (alpha14)

Podrobnosti měsíce se při pohybu kurzoru průběžně zobrazují **trvale v textovém řádku pod grafem**. Kliknutím kamkoli do vykreslovací plochy grafu lze měsíc připnout; šipky vlevo/vpravo při zaměření grafu měsíce přepínají. Karta při běžných aktualizacích HA nepřekresluje SVG, pokud se finanční data nezměnila, a proto hodnoty neblikají. Po přepnutí plynu/elektřiny se výběr měsíce vynuluje. Tato oprava nemění kód doplňku, jen `innosvet-cost-chart.js`.
