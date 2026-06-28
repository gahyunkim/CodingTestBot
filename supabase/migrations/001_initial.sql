CREATE TABLE IF NOT EXISTS users (
    discord_id      TEXT PRIMARY KEY,
    github_username TEXT NOT NULL,
    discord_name    TEXT
);

CREATE TABLE IF NOT EXISTS user_repos (
    discord_id TEXT NOT NULL,
    repo       TEXT NOT NULL,
    PRIMARY KEY (discord_id, repo)
);

CREATE TABLE IF NOT EXISTS fines (
    id         SERIAL PRIMARY KEY,
    discord_id TEXT    NOT NULL,
    amount     INTEGER NOT NULL,
    reason     TEXT,
    date       TEXT    NOT NULL,
    paid       BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_fines_discord_id ON fines (discord_id);
CREATE INDEX IF NOT EXISTS idx_fines_paid       ON fines (discord_id, paid);
