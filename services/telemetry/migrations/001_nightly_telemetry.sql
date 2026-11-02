CREATE TABLE IF NOT EXISTS job_runs (
    id BIGSERIAL PRIMARY KEY,
    job_name VARCHAR(64) NOT NULL,
    target_date DATE NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_job_runs_job_date UNIQUE (job_name, target_date)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_job_runs_one_processing
    ON job_runs (job_name)
    WHERE status = 'processing';

CREATE TABLE IF NOT EXISTS daily_kpi (
    id BIGSERIAL PRIMARY KEY,
    target_date VARCHAR(10) NOT NULL,
    metric_name VARCHAR(64) NOT NULL,
    metric_value JSON NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_daily_kpi_date_metric UNIQUE (target_date, metric_name)
);

CREATE INDEX IF NOT EXISTS ix_daily_kpi_target_date
    ON daily_kpi (target_date);