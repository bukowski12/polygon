# Polygon 2.0

## Hlavní změny

- Více cvičenců současně v polygonu – zrušen limit 4 cvičenců, cvičení může mít i jediného účastníka.
- Nová karta **Provoz** – přehled, kdo je připravený, uvnitř a kdo už dokončil, s časy vstupu, výstupu a dobou průchodu.
- Evidence vstupu a výstupu cvičence jedním tlačítkem – uloží se aktuální čas.
- Možnost ručně opravit čas průchodu (vstup / výstup).
- Stav cvičence (PŘIPRAVEN / UVNITŘ / DOKONČENO) i na kartě Osoby.
- Historie cvičence – přehled všech jeho dřívějších cvičení.
- Zobrazení jednotky u osob a cvičenců.
- Smazané osoby – přehled a možnost smazanou osobu obnovit.
- Rychlé akce v tabulkách – dvojklik a nabídka pravého tlačítka.
- Spolehlivější vyhledávání osob (i se závorkami, tečkou a dalšími znaky) a české datum narození.
- Nové protokoly: souhrnná zpráva o cvičení a individuální potvrzení – náhled, tisk i uložení do PDF.
- Výpočet spotřeby vzduchu v protokolu.
- Kniha provozu – náhled, tisk a uložení do PDF: dnešní záznamy, předávka směny (dnešní + všechny otevřené), období, pouze otevřené nebo všechny záznamy.
- Automatický provozní report e-mailem při ukončení programu – jen když se od posledního odeslaného reportu v Knize provozu něco změnilo (nový, vyřešený nebo stornovaný záznam); v příloze PDF se změnami a všemi otevřenými záznamy. Ve výchozím stavu vypnuto.
- Vylepšený dialog Hodnoty – podle stavu cvičence nabídne správné pole, Enter uloží, ručně zadaný počáteční tlak se nepřepisuje.
- Bezpečnější práce s koncovým tlakem – nezadaný tlak se odlišuje od 0 bar a cvičení bez vyplněných hodnot nejde uložit.
- Kontrola zadaných hodnot ve formulářích osoby a člena.
- Modernizovaný vzhled aplikace.
- Nouzové tlačítko na kartě Polygon – jedním stiskem zastaví zvuk, vypne efekty, otevře žaluzie, rozsvítí světla a zapne ventilaci; opakovaný stisk nic nepřepíná, výrazné hlášení NOUZOVÝ REŽIM AKTIVNÍ a seznam výstupů, které se nepodařilo nastavit. Během nouze je běžné ovládání technologií a zvuku zamčené; tlačítko „Ukončit nouzový režim“ ho po potvrzení odemkne a stav výstupů nechá beze změny.
- Komunikace s QUIDO běží na pozadí – výpadek nebo pomalá odpověď QUIDO nezamrazí okno aplikace. Když stav výstupů QUIDO není známý, tlačítka technologií jsou šedá a nedají se stisknout (nouzové tlačítko funguje vždy).
- Stavový řádek ukazuje, zda běží lokální nebo ostrá databáze, a upozorní na DEV režim a simulaci QUIDO.
- Standardní spuštění přes systémový Python na Ubuntu (`bin/polygon`).
- Instalátor pro Ubuntu a spouštěč, který si při startu bezpečně stáhne schválenou novou verzi (jen fast-forward, s kontrolou nové verze a návratem při chybě); bez sítě se spustí nainstalovaná verze.
- Záznam nečekaných pádů aplikace pro snazší diagnostiku.

# Starší verze

- **1.0.2** (02/2025) – opravy kamer a nahrávání videa, ovládání výstupů QUIDO tlačítky.
- **1.0.1** (01/2025) – úpravy zabezpečení a stability, tisk protokolu cvičení, jméno přihlášeného uživatele ve stavovém řádku.
- **1.0.0** (08/2024) – přechod na Python 3, Qt 5 a nové AD.
