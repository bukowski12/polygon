# Polygon Control System

Řídicí aplikace výcvikového polygonu pro výcvik hasičů v dýchací technice (HZS).

## Popis

Aplikace umožňuje obsluze polygonu sledovat a řídit průběh výcviku. Pohyb hasičů v polygonu je snímán nášlapnými čidly zapojenými do modulů QUIDO — obsluha vidí v reálném čase, na které podlahy hasiči vstoupili. Zároveň může ovládat různé efekty pro ztížení podmínek výcviku.

**Funkce:**
- 🔥 **Sledování pohybu** — zobrazení aktivních nášlapných čidel v polygonu (až 59 podlah)
- 💡 **Světelné efekty** — ovládání osvětlení, strobosvětla, záření a horké zóny
- 💨 **Zadymení** — spouštění kouřového stroje
- 🔊 **Zvukové efekty** — přehrávání hlukového záznamu s regulací hlasitosti
- 📷 **Kamerový dohled** — živý obraz z IP kamer v grid zobrazení
- ⏱️ **Stopky** — měření času cvičení s automatickým záznamem do databáze
- 🎥 **Nahrávání** — automatické nahrávání videa z kamer po dobu cvičení
- 📋 **Tisk protokolu** — generování a tisk protokolu o absolvovaném cvičení
- 👥 **Evidence osob** — správa hasičů a jejich zařazení do cvičení

## Požadavky

- Python 3.8+
- PyQt5
- OpenCV (`cv2`) — pro kamery
- ldap3 — pro autentifikaci přes Active Directory
- requests
- MySQL server + ovladač

```bash
pip install PyQt5 opencv-python ldap3 requests
```

## Konfigurace

Zkopírujte vzorový konfigurační soubor a upravte podle prostředí:

```bash
cp config/polygon.conf.example config/polygon.conf
```

Konfigurační soubor obsahuje sekce:

| Sekce | Popis |
|---|---|
| `[LDAP]` | Přihlášení přes Active Directory |
| `[MYSQL]` | Připojení k databázi |
| `[QUIDO]` | IP adresy QUIDO modulů (vstupy / výstupy) |
| `[QUIDO_IN]` | Mapování nášlapných čidel na vstupy QUIDO |
| `[QUIDO_OUT]` | Mapování tlačítek efektů na výstupy QUIDO |
| `[CAMERA]` | RTSP URL kamer a rozlišení náhledu |
| `[AUDIO]` | Cesta ke zvukovému souboru |

## Spuštění

```bash
bin/polygon
# nebo přímo:
python app/main.py
```

## Struktura projektu

```
polygon/
├── app/                  # Zdrojový kód aplikace
│   ├── main.py           # Hlavní okno aplikace
│   ├── camera.py         # Kamerový modul (RTSP, nahrávání)
│   ├── quido.py          # Komunikace s QUIDO I/O moduly
│   ├── model.py          # Databázové modely
│   ├── protocol.py       # Generování HTML protokolu cvičení
│   ├── audio.py          # Přehrávání zvuku
│   ├── pyspinel.py       # Komunikace přes protokol Spinel 97
│   ├── config_manager.py # Načítání konfigurace
│   └── changelog.txt     # Historie verzí
├── config/
│   ├── polygon.conf          # Konfigurace (ignorována Gitem)
│   └── polygon.conf.example  # Vzorová konfigurace
├── files/                # Ikony a zvukové soubory
├── log/                  # Logy aplikace
├── video/                # Nahraná videa cvičení
└── bin/polygon           # Spouštěcí skript
```

## Hardware

- **QUIDO** — průmyslové I/O moduly (Papouch) připojené přes TCP/IP
  - Digitální vstupy: nášlapná čidla v podlahách polygonu
  - Digitální výstupy: relé pro ovládání efektů (ventilátory, světla, kouř, …)
- **IP kamery** — RTSP stream, protokol Hikvision nebo ONVIF
