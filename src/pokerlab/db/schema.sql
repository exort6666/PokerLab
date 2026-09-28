-- PokerLab database schema (SQLite)

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

-- ============================================================
-- Турниры
-- ============================================================

CREATE TABLE IF NOT EXISTS tournaments (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    buy_in_cents    INTEGER,
    is_bounty       INTEGER NOT NULL DEFAULT 0,
    start_date      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- Раздачи
-- ============================================================

CREATE TABLE IF NOT EXISTS hands (
    id              TEXT PRIMARY KEY,
    tournament_id   INTEGER NOT NULL REFERENCES tournaments(id) ON DELETE CASCADE,
    level           INTEGER NOT NULL,
    sb              INTEGER NOT NULL,
    bb              INTEGER NOT NULL,
    ante            INTEGER NOT NULL DEFAULT 0,
    table_name      TEXT,
    button_seat     INTEGER,
    max_seats       INTEGER NOT NULL DEFAULT 9,
    played_at       TEXT NOT NULL,
    board           TEXT,
    total_pot       INTEGER NOT NULL DEFAULT 0,
    hero_seat       INTEGER,
    hero_cards      TEXT,
    hero_position   TEXT,
    hero_net        INTEGER NOT NULL DEFAULT 0,
    raw_text        TEXT
);

CREATE INDEX IF NOT EXISTS idx_hands_tournament ON hands(tournament_id);
CREATE INDEX IF NOT EXISTS idx_hands_played_at  ON hands(played_at);
CREATE INDEX IF NOT EXISTS idx_hands_hero_pos   ON hands(hero_position);

-- ============================================================
-- Игроки в раздаче
-- ============================================================

CREATE TABLE IF NOT EXISTS hand_players (
    hand_id         TEXT NOT NULL REFERENCES hands(id) ON DELETE CASCADE,
    seat            INTEGER NOT NULL,
    name            TEXT NOT NULL,
    stack_start     INTEGER NOT NULL,
    cards           TEXT,
    position        TEXT,
    is_hero         INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (hand_id, seat)
);

CREATE INDEX IF NOT EXISTS idx_hand_players_name ON hand_players(name);

-- ============================================================
-- Действия
-- ============================================================

CREATE TABLE IF NOT EXISTS actions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    hand_id         TEXT NOT NULL REFERENCES hands(id) ON DELETE CASCADE,
    street          TEXT NOT NULL CHECK (street IN
        ('preflop','flop','turn','river','showdown')),
    action_order    INTEGER NOT NULL,
    seat            INTEGER NOT NULL,
    player_name     TEXT NOT NULL,
    action          TEXT NOT NULL CHECK (action IN
        ('post_ante','post_sb','post_bb','fold','check','call','bet','raise')),
    amount          INTEGER NOT NULL DEFAULT 0,
    amount_to       INTEGER NOT NULL DEFAULT 0,
    is_all_in       INTEGER NOT NULL DEFAULT 0,
    pot_after       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_actions_hand   ON actions(hand_id);
CREATE INDEX IF NOT EXISTS idx_actions_street ON actions(hand_id, street, action_order);

-- ============================================================
-- Заметки
-- ============================================================

CREATE TABLE IF NOT EXISTS hand_notes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    hand_id         TEXT NOT NULL REFERENCES hands(id) ON DELETE CASCADE,
    note            TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_hand_notes_hand ON hand_notes(hand_id);

-- ============================================================
-- Теги
-- ============================================================

CREATE TABLE IF NOT EXISTS hand_tags (
    hand_id         TEXT NOT NULL REFERENCES hands(id) ON DELETE CASCADE,
    tag             TEXT NOT NULL,
    PRIMARY KEY (hand_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_hand_tags_tag ON hand_tags(tag);
-- ============================================================
-- Результаты турниров (из Tournament Summary)
-- ============================================================

CREATE TABLE IF NOT EXISTS tournament_results (
    tournament_id   INTEGER PRIMARY KEY REFERENCES tournaments(id),
    buyin_cents     INTEGER,
    rake_cents      INTEGER,
    bounty_cents    INTEGER,
    field_size      INTEGER,
    prize_pool_cents INTEGER,
    hero_place      INTEGER,
    hero_payout_cents INTEGER,
    itm             INTEGER NOT NULL DEFAULT 0,
    started_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_tournament_results_itm ON tournament_results(itm);
CREATE INDEX IF NOT EXISTS idx_tournament_results_started ON tournament_results(started_at);
-- ============================================================
-- Анализ раздач (EV-расчёты)
-- ============================================================

CREATE TABLE IF NOT EXISTS hand_analysis (
    hand_id         TEXT PRIMARY KEY REFERENCES hands(id) ON DELETE CASCADE,
    spot_type       TEXT NOT NULL,           -- PREFLOP_VS_PUSH, POSTFLOP_SRP, ...
    street          TEXT NOT NULL,           -- preflop / flop / turn / river
    solver_name     TEXT NOT NULL,           -- 'cfr_hu_pushfold', 'cfr_multiway', ...
    solver_version  TEXT NOT NULL,           -- 'v1.0'

    hero_action     TEXT,                    -- что Hero фактически сделал
    optimal_action  TEXT,                    -- оптимальное действие
    ev_optimal      REAL,                    -- EV оптимального (в bb)
    ev_actual       REAL,                    -- EV фактического (в bb)
    ev_loss         REAL,                    -- ev_optimal - ev_actual

    is_correct      INTEGER NOT NULL DEFAULT 0,  -- 1 если hero_action == optimal_action
    is_critical     INTEGER NOT NULL DEFAULT 0,  -- 1 если ev_loss > threshold

    computed_at     TEXT NOT NULL DEFAULT (datetime('now')),
    details         TEXT                     -- JSON с доп. инфо (equity, range, ...)
);

CREATE INDEX IF NOT EXISTS idx_ha_spot      ON hand_analysis(spot_type);
CREATE INDEX IF NOT EXISTS idx_ha_correct   ON hand_analysis(is_correct);
CREATE INDEX IF NOT EXISTS idx_ha_loss      ON hand_analysis(ev_loss DESC);