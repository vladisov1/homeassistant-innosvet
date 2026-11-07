# Changelog

## 0.1.0-alpha (2026-11-06)

- Zachována testovací větev 0.1.0-alpha (bez navyšování verze).
- Výslovně zdokumentováno jednorázové zadání loginu a hesla v konfiguraci doplňku (již podporovaná pole `innogy_username`, `innogy_password`).
- Přihlašovací údaje nejsou součástí zdrojového kódu ani distribučního ZIPu.
- GitHub repozitář se souborem `repository.yaml`; pouze čtení finančních bilancí elektřiny a plynu přes MQTT.
- Experimentální automatické obnovení přihlášení; v HAOS zatím neověřeno.
- **Zápis plynoměru není implementován.**

### Rozpracované rozšíření 0.1.0-alpha (neověřeno v ostrém provozu)
- Přidána opt-in funkce zápisu stavu plynoměru ze senzoru HA v časech `schedule`.
- Výchozí zápis vypnut, druhý potvrzovací přepínač a deník proti opakování.
- Přidán MQTT stav pokusu o odeslání plynu.
- Doplněn postup pro zjištění `contractid` a upozornění na neověřené automatické odeslání.
