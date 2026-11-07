-- NatAware PostgreSQL schema (production target).
-- The demo uses an equivalent JSON-backed store (nataware/data/store.py) instead.

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name    TEXT,
    city            TEXT,
    latitude        NUMERIC(8, 5),
    longitude       NUMERIC(8, 5),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Phase 1: 2D psych-profile matrix
CREATE TABLE IF NOT EXISTS profiles (
    user_id             UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    capacity            TEXT NOT NULL CHECK (capacity IN ('The Over-Leveraged','The Scrapper','The Stabilizer','The Accumulator')),
    tendency            TEXT NOT NULL CHECK (tendency IN ('The Comfort-Buyer','The Status-Seeker','The Experience-Junkie','The Panic-Hoarder')),
    baseline_needs      NUMERIC(5, 2) NOT NULL,
    baseline_wants      NUMERIC(5, 2) NOT NULL,
    baseline_savings    NUMERIC(5, 2) NOT NULL,
    rationale           TEXT,
    assessed_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS message_history (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content     JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Phase 2: normalised transactions + behavioural tags
CREATE TABLE IF NOT EXISTS transactions (
    id                  TEXT PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    txn_date            DATE NOT NULL,
    txn_time            TIME,
    merchant            TEXT NOT NULL,
    amount              NUMERIC(12, 2) NOT NULL CHECK (amount >= 0),
    currency            CHAR(3) NOT NULL DEFAULT 'GBP',
    direction           TEXT NOT NULL CHECK (direction IN ('debit','credit')),
    category            TEXT NOT NULL,
    tags                TEXT[] NOT NULL DEFAULT '{}',
    source              TEXT,
    tagged              BOOLEAN NOT NULL DEFAULT FALSE,
    is_flagged          BOOLEAN NOT NULL DEFAULT FALSE,
    highlight_reason    TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions (user_id, txn_date);
CREATE INDEX IF NOT EXISTS idx_transactions_untagged ON transactions (user_id) WHERE NOT tagged;

CREATE TABLE IF NOT EXISTS highlights (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label               TEXT NOT NULL,
    reason              TEXT,
    transaction_ids     TEXT[] NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Phase 3: threats
CREATE TABLE IF NOT EXISTS daily_macro_summaries (
    id          BIGSERIAL PRIMARY KEY,
    city        TEXT NOT NULL,
    summary_date DATE NOT NULL,
    payload     JSONB NOT NULL,
    UNIQUE (city, summary_date)
);

CREATE TABLE IF NOT EXISTS active_threats (
    id                          BIGSERIAL PRIMARY KEY,
    user_id                     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    threat_id                   TEXT NOT NULL,
    threat_name                 TEXT NOT NULL,
    estimated_dollar_burden     NUMERIC(12, 2) NOT NULL,
    currency                    CHAR(3) NOT NULL DEFAULT 'GBP',
    priority                    TEXT NOT NULL CHECK (priority IN ('low','medium','high')),
    recommended_budget_shift    TEXT NOT NULL,
    detail                      JSONB,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, threat_id)
);

-- Phase 4: coaching interventions
CREATE TABLE IF NOT EXISTS nudges (
    id          TEXT PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    trigger     TEXT NOT NULL CHECK (trigger IN ('transaction','macro','temporal')),
    title       TEXT NOT NULL,
    message     TEXT NOT NULL,
    channel     TEXT NOT NULL CHECK (channel IN ('push','email','audio')),
    stage       TEXT,
    delivered   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
