"""Initial Canvex schema.

Revision ID: 202605240001
Revises:
Create Date: 2026-05-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "202605240001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')

    op.execute("CREATE TYPE member_role AS ENUM ('owner', 'admin', 'editor', 'viewer')")
    op.execute("CREATE TYPE element_type AS ENUM ('stroke', 'rect', 'ellipse', 'text', 'image', 'math', 'sticky', 'arrow', 'link')")
    op.execute("CREATE TYPE event_op AS ENUM ('create', 'update', 'delete', 'lock', 'unlock', 'restore')")
    op.execute("CREATE TYPE ai_trigger AS ENUM ('math', 'image', 'question', 'text_block', 'closed_shape', 'explicit')")

    op.execute(
        """
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            avatar_url TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_seen_at TIMESTAMPTZ
        )
        """
    )

    op.execute(
        """
        CREATE TABLE channels (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            description TEXT,
            owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            is_private BOOLEAN NOT NULL DEFAULT FALSE,
            invite_code TEXT UNIQUE DEFAULT encode(gen_random_bytes(6), 'hex'),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE channel_members (
            channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role member_role NOT NULL DEFAULT 'editor',
            joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (channel_id, user_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE channel_invites (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
            created_by UUID NOT NULL REFERENCES users(id),
            code TEXT NOT NULL UNIQUE DEFAULT encode(gen_random_bytes(8), 'hex'),
            role_on_join member_role NOT NULL DEFAULT 'editor',
            max_uses INTEGER,
            uses_count INTEGER NOT NULL DEFAULT 0,
            expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE refresh_tokens (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ NOT NULL,
            revoked BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE whiteboard_pages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
            branch_of UUID REFERENCES whiteboard_pages(id) ON DELETE SET NULL,
            title TEXT NOT NULL DEFAULT 'Untitled page',
            order_index INTEGER NOT NULL DEFAULT 0,
            is_branch BOOLEAN NOT NULL DEFAULT FALSE,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            created_by UUID REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE whiteboard_elements (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            page_id UUID NOT NULL REFERENCES whiteboard_pages(id) ON DELETE CASCADE,
            created_by UUID REFERENCES users(id),
            type element_type NOT NULL,
            transform JSONB NOT NULL DEFAULT jsonb_build_object('x', 0, 'y', 0, 'scaleX', 1, 'scaleY', 1, 'rotation', 0),
            style JSONB NOT NULL DEFAULT jsonb_build_object('stroke', '#000', 'fill', 'transparent', 'strokeWidth', 2),
            content JSONB NOT NULL DEFAULT '{}',
            locked_by UUID REFERENCES users(id),
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            embedding vector(1536),
            last_event UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE element_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            element_id UUID NOT NULL,
            page_id UUID NOT NULL REFERENCES whiteboard_pages(id),
            actor_id UUID REFERENCES users(id),
            operation event_op NOT NULL,
            before_state JSONB,
            after_state JSONB,
            vector_clock JSONB NOT NULL DEFAULT '{}',
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE element_permissions (
            element_id UUID NOT NULL,
            role member_role NOT NULL,
            can_read BOOLEAN NOT NULL DEFAULT TRUE,
            can_edit BOOLEAN NOT NULL DEFAULT TRUE,
            PRIMARY KEY (element_id, role)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            page_id UUID NOT NULL REFERENCES whiteboard_pages(id),
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            ended_at TIMESTAMPTZ
        )
        """
    )

    op.execute(
        """
        CREATE TABLE session_events (
            id BIGSERIAL PRIMARY KEY,
            session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            page_id UUID NOT NULL,
            event_type TEXT NOT NULL,
            payload JSONB NOT NULL,
            actor_id UUID REFERENCES users(id),
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE ai_interactions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            page_id UUID NOT NULL REFERENCES whiteboard_pages(id),
            trigger_element_id UUID,
            trigger_type ai_trigger NOT NULL,
            canvas_snapshot_url TEXT,
            prompt_sent TEXT NOT NULL,
            response_json JSONB,
            response_element_id UUID,
            input_tokens INTEGER,
            output_tokens INTEGER,
            latency_ms INTEGER,
            status TEXT NOT NULL DEFAULT 'pending',
            error_message TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE ai_feedback (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            interaction_id UUID NOT NULL REFERENCES ai_interactions(id),
            user_id UUID NOT NULL REFERENCES users(id),
            is_correct BOOLEAN NOT NULL,
            correction_text TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE review_comments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            element_id UUID NOT NULL,
            snapshot_event UUID REFERENCES element_events(id),
            author_id UUID NOT NULL REFERENCES users(id),
            body TEXT NOT NULL,
            resolved BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE webhooks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
            target_url TEXT NOT NULL,
            signing_secret TEXT NOT NULL DEFAULT encode(gen_random_bytes(32), 'hex'),
            event_types TEXT[] NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_delivery_at TIMESTAMPTZ
        )
        """
    )

    op.execute(
        """
        CREATE TABLE canvas_analytics (
            page_id UUID NOT NULL REFERENCES whiteboard_pages(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id),
            session_date DATE NOT NULL,
            region_x_bucket INTEGER NOT NULL DEFAULT 0,
            region_y_bucket INTEGER NOT NULL DEFAULT 0,
            edit_count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (page_id, user_id, session_date, region_x_bucket, region_y_bucket)
        )
        """
    )

    op.execute("CREATE INDEX idx_channel_members_user ON channel_members(user_id)")
    op.execute("CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id)")
    op.execute("CREATE INDEX idx_pages_channel ON whiteboard_pages(channel_id)")
    op.execute("CREATE INDEX idx_elements_content ON whiteboard_elements USING GIN (content)")
    op.execute("CREATE INDEX idx_elements_page ON whiteboard_elements(page_id)")
    op.execute("CREATE INDEX idx_events_element ON element_events(element_id, occurred_at)")
    op.execute("CREATE INDEX idx_events_page_time ON element_events(page_id, occurred_at)")
    op.execute("CREATE INDEX idx_events_actor ON element_events(actor_id, occurred_at)")
    op.execute("CREATE INDEX idx_session_events_session ON session_events(session_id, id)")
    op.execute("CREATE INDEX idx_ai_interactions_page ON ai_interactions(page_id, created_at)")
    op.execute("CREATE INDEX idx_review_comments_element ON review_comments(element_id)")
    op.execute("CREATE INDEX idx_canvas_analytics_page_date ON canvas_analytics(page_id, session_date)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS canvas_analytics")
    op.execute("DROP TABLE IF EXISTS webhooks")
    op.execute("DROP TABLE IF EXISTS review_comments")
    op.execute("DROP TABLE IF EXISTS ai_feedback")
    op.execute("DROP TABLE IF EXISTS ai_interactions")
    op.execute("DROP TABLE IF EXISTS session_events")
    op.execute("DROP TABLE IF EXISTS sessions")
    op.execute("DROP TABLE IF EXISTS element_permissions")
    op.execute("DROP TABLE IF EXISTS element_events")
    op.execute("DROP TABLE IF EXISTS whiteboard_elements")
    op.execute("DROP TABLE IF EXISTS whiteboard_pages")
    op.execute("DROP TABLE IF EXISTS refresh_tokens")
    op.execute("DROP TABLE IF EXISTS channel_invites")
    op.execute("DROP TABLE IF EXISTS channel_members")
    op.execute("DROP TABLE IF EXISTS channels")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TYPE IF EXISTS ai_trigger")
    op.execute("DROP TYPE IF EXISTS event_op")
    op.execute("DROP TYPE IF EXISTS element_type")
    op.execute("DROP TYPE IF EXISTS member_role")
