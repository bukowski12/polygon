-- ============================================================
-- Polygon Control System -- inicializace databaze
-- ============================================================
-- Pouziti:
--   mysql -u root -p < config/polygon.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS polygon
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_czech_ci;

USE polygon;

-- ------------------------------------------------------------
-- Tabulka osob (hasici)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS person (
    idPerson  INT          NOT NULL AUTO_INCREMENT,
    name      VARCHAR(64)  NOT NULL,
    surname   VARCHAR(64)  NOT NULL,
    birthday  DATE         DEFAULT NULL,
    oec       VARCHAR(32)  DEFAULT NULL COMMENT 'Osobni evidencni cislo',
    unit      VARCHAR(128) DEFAULT NULL COMMENT 'Nazev jednotky / organizace',
    valid     TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '1 = aktivni, 0 = smazan',
    PRIMARY KEY (idPerson)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- Tabulka cviceni (treningu)
-- ------------------------------------------------------------
-- status:
--   0  = priprava (mene nez 2 clenove)
--   1  = aktivni  (2+ clenove, pripraveno ke spusteni)
--   2  = dokonceno (po zastaveni stopek)
--   10 = ulozeno  (po potvrzeni a tisku protokolu)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS training (
    idTraining INT      NOT NULL AUTO_INCREMENT,
    time_start DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Cas zalozeni cviceni',
    time_cage  TIME     DEFAULT NULL                       COMMENT 'Cas vstupu do klece (MM:SS)',
    time_end   TIME     DEFAULT NULL                       COMMENT 'Cas ukonceni cviceni (MM:SS)',
    status     TINYINT  NOT NULL DEFAULT 0,
    PRIMARY KEY (idTraining)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- Tabulka clenu druzstva (prirazeni hasicu k cviceni)
-- ------------------------------------------------------------
-- volume    ... objem lahve v litrech (6.0 / 6.8 / 7.0)
-- press_start/press_end ... tlak v Bar
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS member (
    idMember    INT           NOT NULL AUTO_INCREMENT,
    training_id INT           NOT NULL,
    person_id   INT           NOT NULL,
    volume      DECIMAL(4,1)  DEFAULT NULL  COMMENT 'Objem lahve (l)',
    press_start SMALLINT      DEFAULT NULL  COMMENT 'Tlak pred cvicenim (Bar)',
    press_end   SMALLINT      DEFAULT NULL  COMMENT 'Tlak po cviceni (Bar)',
    PRIMARY KEY (idMember),
    CONSTRAINT fk_member_training FOREIGN KEY (training_id) REFERENCES training (idTraining),
    CONSTRAINT fk_member_person   FOREIGN KEY (person_id)   REFERENCES person   (idPerson)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------
-- Databazovy uzivatel aplikace
-- ------------------------------------------------------------
-- Upravte heslo pred spustenim!
-- ------------------------------------------------------------
CREATE USER IF NOT EXISTS 'polygon'@'%' IDENTIFIED BY 'HESLO';
GRANT SELECT, INSERT, UPDATE, DELETE ON polygon.* TO 'polygon'@'%';
FLUSH PRIVILEGES;

