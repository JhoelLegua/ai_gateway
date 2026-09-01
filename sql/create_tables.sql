-- ==============================================================================
-- AI Gateway Perimetral - PostgreSQL DDL
-- Database: ai_gateway
--
-- Run this script against your PostgreSQL instance to initialize the schema.
-- Usage: psql -U <user> -d ai_gateway -f sql/create_tables.sql
-- ==============================================================================


-- ------------------------------------------------------------------------------
-- Table 1: users_notification
-- Security team members who receive Brevo SMTP alert emails.
-- Managed via /v1/notifications/recipients endpoints (Admin Token required).
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users_notification (
    id          SERIAL PRIMARY KEY,

    -- Identity
    first_name  VARCHAR(100)    NOT NULL,
    last_name   VARCHAR(100)    NOT NULL,
    ci          VARCHAR(30)     NOT NULL UNIQUE,     -- National ID / Cédula de Identidad
    email       VARCHAR(255)    NOT NULL UNIQUE,

    -- Role within the security team
    role        VARCHAR(50)     NOT NULL DEFAULT 'SOC_ANALYST',
                                -- SOC_ANALYST | ADMIN | AUDITOR

    -- Alert subscription toggle
    is_active   BOOLEAN         NOT NULL DEFAULT TRUE,
                                -- TRUE = receives alerts; FALSE = silenced

    -- Audit timestamps
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Index for fast lookup of active recipients (used by email notifier)
CREATE INDEX IF NOT EXISTS idx_users_notification_active
    ON users_notification (is_active);

-- Trigger to auto-update updated_at on row modification
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_notification_updated_at ON users_notification;
CREATE TRIGGER trg_users_notification_updated_at
    BEFORE UPDATE ON users_notification
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ------------------------------------------------------------------------------
-- Table 2: prompt_audit_dataset
-- Full audit log of every prompt processed by the Gateway.
-- Captures automatic Gateway telemetry + optional Human-in-the-Loop (HITL) labels.
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prompt_audit_dataset (
    id                  SERIAL PRIMARY KEY,

    -- Request context
    user_id             VARCHAR(64)     NOT NULL,
    session_id          VARCHAR(64)     NOT NULL,
    prompt_text         TEXT            NOT NULL,

    -- Gateway automatic telemetry
    predicted_threat    BOOLEAN         NOT NULL,
                                        -- TRUE if the Gateway blocked or flagged the prompt
    confidence_score    FLOAT,          -- AI classifier confidence (Layer 3), NULL if not invoked
    blocked_by_layer    VARCHAR(50),    -- layer_1_heuristics | layer_2_vectorial |
                                        -- layer_3_intelligence | layer_5_egress | NULL (passed)
    block_reason        TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    -- Human-in-the-Loop (HITL) review fields
    reviewed            BOOLEAN         NOT NULL DEFAULT FALSE,
                                        -- TRUE once a human analyst has reviewed this entry
    is_threat           BOOLEAN,        -- Human verdict: TRUE=confirmed attack, FALSE=false positive
    threat_category     VARCHAR(50),    -- prompt_leakage | jailbreak | direct_injection |
                                        -- social_engineering | legitimate | other
    reviewed_by_ci      VARCHAR(30),    -- References users_notification.ci (soft FK)
    reviewed_at         TIMESTAMPTZ
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_audit_predicted_threat
    ON prompt_audit_dataset (predicted_threat);

CREATE INDEX IF NOT EXISTS idx_audit_reviewed
    ON prompt_audit_dataset (reviewed);

CREATE INDEX IF NOT EXISTS idx_audit_is_threat
    ON prompt_audit_dataset (is_threat);

CREATE INDEX IF NOT EXISTS idx_audit_created_at
    ON prompt_audit_dataset (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_user_session
    ON prompt_audit_dataset (user_id, session_id);


-- ==============================================================================
-- Verification: list created tables
-- ==============================================================================
SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns c
     WHERE c.table_name = t.table_name
       AND c.table_schema = 'public') AS column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name IN ('users_notification', 'prompt_audit_dataset')
ORDER BY table_name;
