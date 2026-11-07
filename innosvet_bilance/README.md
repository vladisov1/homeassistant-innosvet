# innosvět – finanční bilance (ALPHA 0.1.0-alpha5)

Testovací doplněk Home Assistant OS pro čtení předpokládané bilance plynu a elektřiny z portálu innosvět. Publikuje údaje přes MQTT discovery.

**Pouze čtení. Zápis plynoměru není implementován.**

Podrobnosti, konfigurace, omezení a bezpečnostní upozornění: [DOCS.md](DOCS.md).


### Oprava alpha3 – senzor HA a bezpečný test

Doplněk potřebuje v manifestu `homeassistant_api: true`, protože čte `sensor.plynomer_celkovy_stav` prostřednictvím `/core/api/states/...`. `gas_write_enabled: true` a `gas_write_confirmed: false` **jen ověří hodnotu senzoru; formulář innosvěta v tomto režimu neotevírá**. Skutečné automatické odesílání do innosvěta zatím není testováno v HAOS, proto druhý přepínač ponechte vypnutý. Názvy a popisy nastavení jsou přeloženy v `translations/cs.yaml`.
