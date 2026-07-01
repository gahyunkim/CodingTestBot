CREATE TABLE IF NOT EXISTS cron_log (
    cron_type  TEXT NOT NULL,
    target_date DATE NOT NULL,
    sent_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (cron_type, target_date)
);
