# innogy innosvět – doplněk pro Home Assistant OS

**Verze 0.1.0-alpha – testovací vydání, pouze čtení finančních bilancí.**

**Nově potvrzené nastavení:** přihlašovací jméno a heslo se zadávají jednou v **Konfiguraci** nainstalovaného doplňku (pole `innogy_username` / `innogy_password`); při aktualizaci se nepřepisují do Pythonu. Způsob přihlášení po vypršení relace je stále experimentální.

Tento repozitář lze přidat jako **vlastní repozitář aplikací/doplňků** v Home Assistant OS (Nastavení → Aplikace → Instalovat aplikaci → ⋮ → Repozitáře). Do pole se vkládá **URL vašeho nově vytvořeného GitHub repozitáře, nikoliv odkaz na ZIP soubor**. Tento ZIP je pouze pro první naplnění repozitáře GitHub.

## Obsah

- `repository.yaml` – identifikace repozitáře pro Supervisor.
- `innosvet_bilance/` – instalační složka doplňku.
- `innosvet_bilance/DOCS.md` – podrobný návod na konfiguraci a omezení.

## Co doplněk dělá

Čte **předpokládaný přeplatek / nedoplatek** plynu a elektřiny z innosvěta čtyřikrát denně (`05:55`, `11:55`, `17:55`, `23:55`) a publikuje dvě číselné entity pomocí MQTT discovery. **Nečte stav elektroměru z VisionQ, nepočítá náklady a nijak neodesílá odečty.**

**Zápis plynoměru v této verzi není implementován.** Načítání finančních údajů bylo ověřeno na Windows s uloženou relací Playwright; **instalace v HAOS, nové automatické přihlášení heslem a MQTT zatím nejsou ověřené**.

## Instalace z GitHubu

1. Na svém GitHub účtu založte prázdný repozitář, např. `homeassistant-innosvet`.
2. Rozbalte tento archiv a nahrajte **jeho obsah** do kořene repozitáře, tak aby `repository.yaml` byl přímo na nejvyšší úrovni. Nenahrávejte samotný ZIP místo souborů.
3. Otevřete Home Assistant OS → Nastavení → Aplikace → Instalovat aplikaci → ⋮ → Repozitáře.
4. Přidejte URL repozitáře `https://github.com/VAŠE_JMÉNO/homeassistant-innosvet` (jde jen o příklad; skutečnou adresu získáte po založení).
5. Najděte doplněk `innosvět – plyn a bilance (ALPHA)`, nainstalujte a vyplňte nastavení.
6. Před spuštěním ověřte přítomnost MQTT brokeru a integrace MQTT. Pokyny a upozornění v `innosvet_bilance/DOCS.md`.

**Kompatibilita:** pouze `amd64`; první sestavení může být pomalé a nemusí projít na každé instalaci. Pokud se doplněk nenabídne, ověřte, že je `repository.yaml` v kořeni a že architektura HAOS odpovídá.

**Bezpečnost:** GitHub repozitář nesmí obsahovat přihlašovací údaje, cookies, `options.json`, soubory profilu prohlížeče ani jiné tokeny. Heslo se zadává až v konfiguraci nainstalovaného doplňku. Hesla ani tokeny neposílejte do chatu.


## Připravovaný automatický zápis plynoměru (0.1.0-alpha – experimentální)

V této aktualizaci je nově přidána **volitelná funkce odeslání** z entity
`sensor.plynomer_celkovy_stav`. Výchozí konfigurace `gas_write_enabled: false`
znamená, že **se nic neodesílá**. Po zapnutí prvního přepínače lze pouze ověřovat
hodnotu senzoru; odeslání vyžaduje ještě nezávislé výslovné zapnutí
`gas_write_confirmed: true`.

Časy se zadávají společným polem `schedule`, například
`05:55,11:55,17:55,23:55`. Při každém termínu se nejprve načtou finanční
bilance a pak se samostatně vyhodnotí zápis plynu. Zápis se při spuštění
aplikace **mimo plánovaný čas neprovádí**.

**Zatím nebylo ověřeno automatické kliknutí na „Pokračovat“ a „Odeslat odečet“ v HAOS**.
Proto neaktivujte `gas_write_confirmed` před řízeným testováním. Aplikace
ukládá trvalý deník pokusů a po nejasném výsledku zápis automaticky
neopakuje. Odesílá se celé m³ (desetinná část se odřízne); stejnou hodnotu lze
odeslat v různých plánovaných časech.

Podrobnosti jsou v `innosvet_bilance/DOCS.md`.
