# Databáze Polygonu

Polygon ukládá data do databáze **MariaDB** (ověřeno s MariaDB 11; MySQL kompatibilní se syntaxí MariaDB
není ověřen – schéma používá generovaný sloupec `PERSISTENT` a `CHECK`).

## Nová instalace

`schema.sql` vytvoří databázi `polygon` (znaková sada `utf8mb3`, řazení `utf8mb3_czech_ci`) a prázdné tabulky
aplikace: `person`, `training`, `member`, `exercise_session`, `operation_log` – včetně cizích klíčů, indexů,
kontrolních omezení a generovaného sloupce. Neobsahuje žádná data.

Spouští ho administrátor databáze na databázovém serveru:

```bash
mariadb -u <administrátor> -p < database/schema.sql
```

Skript je určený jen pro **novou** instalaci. Na existující databázi ho nespouštějte – existující tabulky nezmění
a změny schématu mezi verzemi aplikace řeší správce samostatně.

## Uživatel aplikace

Vytvoření databázového uživatele pro Polygon, volba jeho hesla a omezení, odkud se smí připojit, je
odpovědností **lokálního správce databáze**. Schéma žádného uživatele ani heslo nevytváří.

Polygon potřebuje na databázi `polygon` jen tato oprávnění:

| Oprávnění | Proč |
|---|---|
| `SELECT` | čtení osob, cvičení, průchodů a Knihy provozu |
| `INSERT` | nové osoby, cvičení, cvičenci, průchody a záznamy Knihy provozu |
| `UPDATE` | úpravy záznamů, stavy cvičení a průchodů |
| `DELETE` | odebrání cvičence (a jeho průchodu) z rozpracovaného cvičení, zrušení nového cvičení |

Žádná administrátorská oprávnění (vytváření nebo mazání tabulek, správa uživatelů) aplikace nepotřebuje.

Přihlašovací údaje (server, databáze, uživatel, heslo) se zadávají jen do lokálního `config/polygon.conf`,
sekce `[MYSQL]` – viz `config/polygon.conf.example`.
