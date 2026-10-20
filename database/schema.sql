-- ============================================================
-- Polygon Control System - databazove schema pro NOVOU instalaci
-- ============================================================
-- Pouziti (MariaDB, administrator databaze):
--   mariadb -u <administrator> -p < database/schema.sql
--
-- Vytvori databazi polygon a prazdne tabulky aplikace. Neobsahuje
-- zadna data, databazove uzivatele ani hesla - uzivatele aplikace
-- a jeho opravneni zaklada lokalni spravce (viz database/README.md).
-- Na existujici databazi se nespousti (CREATE ... IF NOT EXISTS
-- existujici tabulky nezmeni).
-- ============================================================

CREATE DATABASE IF NOT EXISTS polygon
    CHARACTER SET utf8mb3
    COLLATE utf8mb3_czech_ci;

USE polygon;

-- ------------------------------------------------------------
-- Tabulka osob (hasici)
-- ------------------------------------------------------------
-- valid ... 1 = aktivni, 0 = smazana (soft delete, aplikace filtruje valid=1)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS person (
    idPerson  INT(11)     NOT NULL AUTO_INCREMENT,
    name      VARCHAR(30) NOT NULL,
    surname   VARCHAR(30) NOT NULL,
    birthday  DATE        NOT NULL,
    oec       VARCHAR(6)  DEFAULT NULL COMMENT 'Osobni evidencni cislo',
    unit      VARCHAR(30) NOT NULL     COMMENT 'Nazev jednotky / organizace',
    valid     BIT(1)      NOT NULL DEFAULT b'1' COMMENT '1 = aktivni, 0 = smazana',
    PRIMARY KEY (idPerson)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_czech_ci;

-- ------------------------------------------------------------
-- Tabulka cviceni (treningu)
-- ------------------------------------------------------------
-- status:
--   0  = nove     (prave zalozene, zatim bez clenu)
--   1  = aktivni  (1+ clenove, provozne pouzitelne)
--   2  = dokonceno (ceka na kontrolu hodnot a ulozeni)
--   10 = ulozeno  (po potvrzeni a tisku protokolu)
--
-- time_start ... jen DATUM zalozeni (bez casu); casy vstupu/vystupu
--                jsou v exercise_session
-- time_cage / time_end ... historicke spolecne casy stareho modelu
--                druzstva; nova cviceni je nechavaji '00:00:00'
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS training (
    idTraining INT(11)    NOT NULL AUTO_INCREMENT,
    time_start DATE       NOT NULL,
    time_cage  TIME       NOT NULL DEFAULT '00:00:00',
    time_end   TIME       NOT NULL DEFAULT '00:00:00',
    status     TINYINT(4) NOT NULL DEFAULT 0,
    PRIMARY KEY (idTraining)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_czech_ci;

-- ------------------------------------------------------------
-- Tabulka clenu cviceni (prirazeni hasicu k cviceni)
-- ------------------------------------------------------------
-- volume    ... objem lahve v litrech (6.0 / 6.8 / 7.0)
-- press_start/press_end ... tlak v Bar
-- press_start 0 = nevyplneno (Ulozit cviceni takovou hodnotu odmitne)
-- press_end NULL = nezadano (Ulozit cviceni odmitne), 0 = skutecne 0 bar
--   (Ulozit cviceni vyzaduje potvrzeni)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS member (
    idMember    INT(11)      NOT NULL AUTO_INCREMENT,
    training_id INT(11)      NOT NULL,
    person_id   INT(11)      NOT NULL,
    volume      DECIMAL(3,1) NOT NULL DEFAULT 0.0 COMMENT 'Objem lahve (l)',
    press_start SMALLINT(6)  NOT NULL DEFAULT 0   COMMENT 'Tlak pred cvicenim (Bar)',
    press_end   SMALLINT(6)  NULL DEFAULT NULL    COMMENT 'Tlak po cviceni (Bar), NULL = nezadano',
    PRIMARY KEY (idMember),
    KEY training_id (training_id),
    KEY person_id (person_id),
    CONSTRAINT fk_member_person   FOREIGN KEY (person_id)   REFERENCES person (idPerson),
    CONSTRAINT fk_member_training FOREIGN KEY (training_id) REFERENCES training (idTraining)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_czech_ci;

-- ------------------------------------------------------------
-- Individualni pruchod cvicence polygonem (vstup/vystup)
-- ------------------------------------------------------------
-- status:
--   0 = pripraven (session zalozena, vstup jeste nezapsan)
--   1 = uvnitr polygonu (entry_at zapsan, exit_at zatim NULL)
--   2 = dokonceno (entry_at i exit_at zapsany)
--
-- source:
--   'MANUAL' = obsluha rucne zapsala cas
--   'DALLAS' = budouci automaticka evidence pres Dallas cip
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exercise_session (
    idSession   INT      NOT NULL AUTO_INCREMENT,
    member_id   INT      NOT NULL,
    entry_at    DATETIME DEFAULT NULL COMMENT 'Skutecny cas vstupu do polygonu',
    exit_at     DATETIME DEFAULT NULL COMMENT 'Skutecny cas vystupu z polygonu',
    status      TINYINT  NOT NULL DEFAULT 0,
    source      VARCHAR(16) NOT NULL DEFAULT 'MANUAL',
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (idSession),
    INDEX idx_session_member (member_id),
    INDEX idx_session_status (status),
    INDEX idx_session_entry_at (entry_at),
    CONSTRAINT fk_session_member
        FOREIGN KEY (member_id)
        REFERENCES member (idMember)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- Kniha provozu. Zaznamy se nemazou, chybny zaznam = status
-- CANCELLED. Nefunkcni cidlo = otevreny zaznam SENSOR_FAULT /
-- FLOOR_SENSOR / floor_XX.
-- ------------------------------------------------------------
-- status:
--   'OPEN'      = otevreno
--   'RESOLVED'  = vyreseno (resolved_at/by, resolution_note)
--   'CANCELLED' = stornovano - chybny zaznam (cancelled_at/by, cancel_reason)
--
-- category: 'TECH_FAULT', 'SENSOR_FAULT', 'DAMAGE', 'MAINTENANCE',
--           'INJURY' (jen provozni zaznam, zadne diagnozy), 'NOTE'
--
-- event_at   = skutecny cas udalosti (zada obsluha)
-- created_at = cas zapisu do aplikace
-- *_by       = textove LDAP jmeno obsluhy (aplikace nema tabulku uzivatelu)
--
-- open_sensor_fault: generovany sloupec, = component_id jen u OTEVRENE
-- zavady cidla, jinak NULL -> UNIQUE zarucuje max. jednu otevrenou
-- zavadu na jedno cidlo (NULL se v UNIQUE neporovnava).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS operation_log (
    idLog             INT          NOT NULL AUTO_INCREMENT,
    event_at          DATETIME     NOT NULL COMMENT 'Skutecny cas udalosti',
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Cas zapisu do aplikace',
    created_by        VARCHAR(100) NOT NULL COMMENT 'LDAP jmeno obsluhy',
    category          VARCHAR(32)  NOT NULL,
    description       TEXT         NOT NULL,
    status            VARCHAR(16)  NOT NULL DEFAULT 'OPEN',
    component_type    VARCHAR(32)  DEFAULT NULL COMMENT 'Napr. FLOOR_SENSOR',
    component_id      VARCHAR(64)  DEFAULT NULL COMMENT 'Napr. floor_17',
    location_text     VARCHAR(255) DEFAULT NULL COMMENT 'Misto / zarizeni volnym textem',
    resolved_at       DATETIME     DEFAULT NULL,
    resolved_by       VARCHAR(100) DEFAULT NULL,
    resolution_note   TEXT         DEFAULT NULL,
    cancelled_at      DATETIME     DEFAULT NULL,
    cancelled_by      VARCHAR(100) DEFAULT NULL,
    cancel_reason     TEXT         DEFAULT NULL,
    training_id       INT(11)      DEFAULT NULL COMMENT 'Volitelna vazba na vycvik',
    open_sensor_fault VARCHAR(64)  AS (IF(status = 'OPEN' AND category = 'SENSOR_FAULT', component_id, NULL)) PERSISTENT,
    PRIMARY KEY (idLog),
    UNIQUE KEY uq_log_open_sensor_fault (open_sensor_fault),
    INDEX idx_log_status (status),
    INDEX idx_log_category (category),
    INDEX idx_log_component (component_type, component_id),
    INDEX idx_log_event_at (event_at),
    INDEX idx_log_training (training_id),
    CONSTRAINT chk_log_status CHECK (status IN ('OPEN', 'RESOLVED', 'CANCELLED')),
    CONSTRAINT fk_log_training
        FOREIGN KEY (training_id)
        REFERENCES training (idTraining)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_czech_ci;
