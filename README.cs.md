# Suptronics UPS X120x pro Home Assistant

Integrace pro UPS desky Suptronics / Geekworm **X120x** (X1200, X1201,
X1202) na Raspberry Pi 5 s Home Assistantem.

Verze 3.0 je kompletní přepracování: integrace sama hlídá limity nabíjení,
sama vypne Pi při výpadku, odhaduje zbývající výdrž, na výpadek reaguje
okamžitě a přináší animovanou kartu do dashboardu. Všechny entity z verze 2
si zachovaly svá ID, takže stávající automatizace a historie fungují dál.

## Co integrace vytvoří

Jedno **zařízení** *Suptronics X120x* s těmito entitami:

| Entita | Typ | Poznámka |
|---|---|---|
| Baterie (`sensor.ups_battery_level`) | senzor | procenta z měřiče baterie |
| Napětí baterie (`sensor.ups_battery_voltage`) | senzor | volty |
| Výpadek napájení (`binary_sensor.ups_power`) | binární senzor | senzor z verze 2: zapnutý při výpadku sítě (lze změnit) |
| Nabíjení baterie (`switch.ups_charging_on_off`) | přepínač | hlavní vypínač nabíjení |
| Stav | senzor (výčet) | Na síti, Nabíjí se, Na baterii, Slabá baterie, Vypíná se |
| Úroveň baterie | senzor (výčet) | Plná / Vysoká / Střední / Nízká / Kritická |
| Síťové napájení | binární senzor | síť je připojená |
| Nabíjení | binární senzor | baterie se právě nabíjí |
| Slabá baterie | binární senzor | pod nastaveným prahem |
| Odhadovaná výdrž | senzor | minuty na baterii, naučené ze skutečných výpadků |
| Doba na baterii | senzor | minuty od výpadku sítě |
| Poslední výpadek / Poslední obnovení napájení | senzor | časové značky |
| Počet výpadků | senzor | počítadlo |
| Nabíjet pod / Nabíjet do | číslo | okno nabíjení |
| Vypnout při slabé baterii | přepínač | automatické čisté vypnutí, výchozí vypnuto |
| Vypnout pod | číslo | úroveň baterie pro vypnutí |
| Vypnout po minutách na baterii | číslo | časové pravidlo pro vypnutí, 0 = vypnuto |
| Odpočet do vypnutí | senzor | sekundy do vypnutí, když se blíží |

### Okno nabíjení

*Nabíjet do* a *Nabíjet pod* tvoří rozsah s hysterezí, který hlídá sama
integrace: nabíjení se zastaví na horním limitu a znovu začne, až úroveň
klesne na dolní. Nastavte 60 a 80 a baterie zůstane v pásmu, které
zpomaluje její stárnutí, bez jakékoli automatizace. Výchozí hodnoty (95 až
100) odpovídají chování samotné desky.

*Nabíjení baterie* je hlavní vypínač: když je vypnutý, baterie se nikdy
nenabíjí. Nastavení se znovu zapisuje při každém čtení, takže se deska
nemůže sama vrátit k nabíjení, a přežije restart.

### Automatické vypnutí

Zapněte *Vypnout při slabé baterii* a Raspberry Pi se čistě vypne, když UPS
běží na baterii a splní se jedno z pravidel:

- baterie je na úrovni *Vypnout pod* nebo níž, nebo
- UPS běží na baterii déle než *Vypnout po minutách na baterii*.

Pojistky: síť má vždy přednost a zruší čekající vypnutí; podmínka musí
platit celou minutu; první tři minuty po startu Home Assistanta se nic
nevypíná; oznámení vám řekne, jak vypnutí zastavit. Na Home Assistant OS a
Supervised se používá `hassio.host_shutdown`. Na jiných typech instalace
integrace místo toho vyvolá událost `suptronics_ups_x120x_shutdown` s poli
`reason`, `capacity`, `voltage` a `time_on_battery`, na kterou může reagovat
automatizace.

Aby se Pi po obnovení sítě samo **znovu zapnulo**, musí se Pi 5 při vypnutí
opravdu odpojit od napájení. Nastavuje se jednou v EEPROM z Raspberry Pi OS:

```
sudo rpi-eeprom-config -e
POWER_OFF_ON_HALT=1
PSU_MAX_CURRENT=5000
```

### Odhad výdrže

Během výpadku integrace měří, jak rychle baterie klesá, a ukazuje zbývající
minuty. Rychlost si pamatuje, takže po prvním skutečném výpadku se odhad
zobrazuje i na síti, jako „kolik byste měli, kdyby teď vypadl proud“. Do té
doby je *neznámý*; potřebuje výpadek dlouhý aspoň dvě minuty.

## Karta do dashboardu

Integrace má vlastní kartu a sama ji zaregistruje jako zdroj dashboardu.
Přidejte ji z nabídky karet jako *Suptronics UPS*, nebo v YAML:

```yaml
type: custom:suptronics-ups-card
variant: full        # full | compact | gauge
hours: 24            # rozsah historie
name: UPS v racku    # volitelný název
language: cs         # volitelné, jinak podle jazyka Home Assistanta
```

Entity si najde sama. Horní lišta ukazuje stav (a odpočet, když se blíží
vypnutí), budík ukazuje nabití obarvené podle pásma a okno nabíjení jako
vnější oblouk, dlaždice ukazují odhadovanou výdrž, dobu na baterii nebo
poslední výpadek, napětí a počet výpadků. Pod tím je historie baterie s
proužkem sítě (zelená na síti, červená během výpadku) a tlačítka pro
nabíjení a automatické vypnutí. Každý prvek otevře dialog své entity.

### Doplňkové budíky

Do stejné karty jde přidat libovolnou další entitu jako malý budík, třeba
hodnoty ze System Monitoru, se stejnými prahy `severity` jako u vestavěné
karty gauge (vzestupně pro teplotu, sestupně pro napětí):

```yaml
type: custom:suptronics-ups-card
extras:
  - entity: sensor.processor_temperature
    name: CPU °C
    min: 0
    max: 100
    severity: { green: 0, yellow: 65, red: 80 }
  - entity: sensor.memory_use_percent
    name: RAM
    severity: { green: 0, yellow: 75, red: 90 }
```

`unit` a `decimals` jsou volitelné. Bloky lze vynutit nebo skrýt volbami
`show_stats`, `show_history`, `show_extras` a `show_actions`.

Kompletní ukázkový pohled s odznaky, kartou, klasickými budíky a entitami
System Monitoru je v [docs/dashboard-example.yaml](docs/dashboard-example.yaml).

Pokud se karta po aktualizaci neobjeví, obnovte stránku prohlížeče pomocí
Ctrl+F5.

## Instalace

### HACS

Přidejte `https://github.com/soukal24/ha_suptronics_ups_x120x` jako vlastní
repozitář (kategorie *Integration*), nainstalujte *Suptronics X120x UPS* a
restartujte Home Assistant.

### Ručně

Zkopírujte složku `custom_components/suptronics_ups_x120x/` do adresáře
`config/` a restartujte.

### I2C

Musí existovat `/dev/i2c-1`. Na Home Assistant OS přidejte
`dtparam=i2c_arm=on` do `config.txt` na spouštěcím oddílu (nebo použijte
doplněk HassOS I2C Configurator) a restartujte.

### Nastavení

*Nastavení → Zařízení a služby → Přidat integraci → Suptronics X120x*.
Integrace před vytvořením ověří, že měřič baterie odpovídá.

**Možnosti** (tlačítko Konfigurovat u integrace): interval čtení, práh slabé
baterie a třída a polarita staršího senzoru *Výpadek napájení*.

## Přechod z verze 2.x

Stačí aktualizovat. Zařízení a čtyři původní entity si zachovají ID i
historii, dialog nastavení si zachová své dvě volby. Nové entity se objeví
vedle nich. Automatizaci, která přepínala nabíjení podle úrovně baterie,
můžete smazat a použít okno nabíjení.

## Řešení potíží

- **„UPS nebyla nalezena“ při nastavení**: není povolené I2C, nebo deska
  nesedí na konektoru. `i2cdetect -y 1` má ukázat `36`.
- **500 Internal Server Error při přidávání integrace** s hláškou
  `TypeError: 'NoneType' object is not subscriptable` v logu: poškozená
  složka `/config/deps`. V doplňku Terminal spusťte `rm -rf /config/deps`
  a restartujte Home Assistant.
- **Diagnostika**: stránka zařízení nabízí stažení diagnostiky s aktuálními
  hodnotami, všemi nastaveními a nalezenými GPIO čipy.
- **Ladicí log**:

```yaml
logger:
  logs:
    custom_components.suptronics_ups_x120x: debug
```

## Jak to funguje

| Co | Kde | Detail |
|---|---|---|
| Napětí článku | I2C `0x36`, registr `0x02` | 78,125 µV na LSB |
| Stav nabití | I2C `0x36`, registr `0x04` | 1/256 % na LSB |
| Síť přítomna | GPIO 6 | vysoká úroveň, když adaptér napájí; hrany dávají okamžitou detekci |
| Řízení nabíjení | GPIO 16 | vysoká úroveň nabíjení zastaví, nízká nabíjí (příkaz výrobce `pinctrl set 16 op dh/dl`) |

Obě GPIO linky integrace drží po celou dobu běhu. Uvolnění linky nabíjení
vrátí desku do výchozího stavu, tedy nabíjení.

## Poděkování a licence

MIT, viz [LICENSE](LICENSE). Verze 3.0 vznikla s využitím
[integrace X120X od mesgas](https://github.com/mesgas/Suptronics-X120x-homeassistant)
jako předlohy; viz [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
Bez vazby na Suptronics nebo Geekworm.
