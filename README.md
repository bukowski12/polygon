# Polygon

Polygon je řídicí software pro výcvikové polygonové pracoviště pro výcvik v dýchací technice – evidence
cvičenců a průchodů polygonem, ovládání technologií polygonu, kamerový dohled a provozní dokumentace.

Každé pracoviště si nastavuje databázi, LDAP, moduly QUIDO, kamery, mapování vstupů a výstupů a svou
identitu (název, organizace, adresa, místo, logo) v lokální konfiguraci (viz *Lokální konfigurace*).

Tento repozitář obsahuje **produkční sestavení** aplikace. Verze a zdrojový build jsou uvedené
v souboru `PRODUCTION-BUILD.txt`.

## Co Polygon umí

- evidence osob a cvičenců, vstup a výstup z polygonu jedním tlačítkem, doba průchodu, spotřeba vzduchu;
- mapa polygonu se stavem nášlapných čidel;
- ovládání technologií (ventilace, kouř, světla, žaluzie, efekty) a nouzové tlačítko;
- náhled a záznam IP kamer;
- protokoly o cvičení a Kniha provozu – náhled, tisk a PDF;
- volitelný provozní report e-mailem.

## Podporovaná platforma

- **Ubuntu** (ověřeno na Ubuntu 26.04), systémový Python 3 a balíčky z APT – bez virtuálního prostředí.
- Aplikace se spouští pod běžným uživatelem s grafickým prostředím.

## Potřebné vybavení a služby

| Část | Použití |
|---|---|
| Moduly **Papouch QUIDO** (Ethernet, protokol Spinel 97) | jeden modul pro vstupy (čidla), jeden pro reléové výstupy (technologie) |
| **IP kamery** s RTSP streamem | náhled a záznam (volitelné) |
| Databázový server **MariaDB / MySQL** | data aplikace |
| **LDAP / Active Directory** | přihlášení obsluhy |
| SMTP server | provozní report e-mailem (volitelné) |
| Zvuk přes PipeWire / PulseAudio / ALSA | zvukové efekty (volitelné, vlastní WAV soubor provozovatele) |

## Databáze

Pro novou instalaci je připravené schéma [`database/schema.sql`](database/schema.sql) (MariaDB) – vytvoří
databázi a prázdné tabulky aplikace. Postup, potřebná oprávnění uživatele aplikace a odpovědnosti
správce popisuje [`database/README.md`](database/README.md). Databázového uživatele a jeho heslo zakládá
lokální správce; schéma žádné přístupové údaje neobsahuje.

## Instalace

Instalátor se spouští jako uživatel, pod kterým bude Polygon běžet (ne root); `sudo` použije jen pro
instalaci balíčků z APT.

```bash
git clone --single-branch --no-tags --branch production https://github.com/bukowski12/polygon.git ~/polygon
~/polygon/deploy/install_polygon.sh
```

Instalátor:

1. nainstaluje potřebné balíčky z APT;
2. vytvoří adresáře `log/` a `video/`;
3. pokud neexistuje `config/polygon.conf`, vytvoří ho z `config/polygon.conf.example` (práva 600) –
   existující konfiguraci nikdy nepřepíše;
4. přidá spouštěč do menu (volitelně `--desktop-icon`, `--autostart`);
5. spustí kontrolu prostředí (preflight).

Nápověda: `deploy/install_polygon.sh --help`.

## Spuštění a aktualizace

| Příkaz | Co dělá |
|---|---|
| `bin/polygon-start` | bezpečná aktualizace a spuštění aplikace (spouštěč v menu) |
| `bin/polygon-start --no-update` | spuštění bez aktualizace |
| `bin/polygon-preflight` | kontrola prostředí (Python moduly, ovladač databáze, konfigurace) – nic nemění |

Aktualizace stahuje jen schválené verze větve `production` (pouze fast-forward). Nová verze se nejdřív
zkontroluje preflightem; pokud neprojde, vrátí se předchozí verze. Bez sítě se spustí nainstalovaná verze.
Konfigurace, logy a záznamy kamer se aktualizací nemění.

## Lokální konfigurace

Veškerá nastavení konkrétního polygonu jsou jen v souboru `config/polygon.conf` na cílovém PC
a do repozitáře nepatří: identita pracoviště, adresy a přístupy k databázi a LDAP, IP adresy modulů QUIDO,
mapování čidel a výstupů, kamery a e-mail. Vzor se všemi sekcemi a komentáři je v `config/polygon.conf.example`
(obsahuje jen ukázkové hodnoty).

Povinná sekce `[SITE]` určuje identitu pracoviště – název pracoviště (titulek okna, provozní report),
organizaci, adresu a místo (hlavička a patička protokolů, hlavička Knihy provozu) a volitelně vlastní logo
protokolů jako lokální soubor mimo repozitář. Distribuce obsahuje jen neutrální logo Polygon.

Zvukový efekt je ve výchozí konfiguraci vypnutý (`[AUDIO] disable = true`) – distribuce žádný zvukový
soubor neobsahuje. Provozovatel může dodat vlastní lokální WAV soubor, nastavit jeho cestu v `[AUDIO] file`
a zvuk zapnout.

Sekce `[DEV]` slouží jen pro vývoj a v produkčním provozu musí zůstat vypnutá.

## Licence

Polygon is free software licensed under the
GNU General Public License version 3 or later (GPL-3.0-or-later).

Úplný text licence je v souboru [`LICENSE`](LICENSE). Převzaté komponenty a jejich původní licence (GPL)
uvádí [`THIRD_PARTY_LICENSES.md`](THIRD_PARTY_LICENSES.md), úplné texty licencí jsou v adresáři `licenses/`.

## Autor

Viz `CREDITS.md` (v aplikaci *O aplikaci → Autoři*). Přehled změn je v `CHANGELOG.md`.
