CREATE TABLE IF NOT EXISTS plays (
    track_id TEXT,
    track_name TEXT,
    artist_name TEXT,
    played_at TIMESTAMPTZ,
    artist_id TEXT,
    album_id TEXT,
    album_name TEXT,
    duration_ms INTEGER,
    ingested_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (track_id, played_at)
);


CREATE TABLE IF NOT EXISTS streaming_history (
    ts TIMESTAMPTZ NOT NULL,
    platform TEXT,
    ms_played INTEGER,
    track_id TEXT,
    track_name TEXT,
    artist_name TEXT,
    album_name TEXT,
    episode_name TEXT,
    episode_show_name TEXT,
    reason_start TEXT,
    reason_end TEXT,
    shuffle BOOLEAN,
    skipped BOOLEAN,
    offline BOOLEAN,
    UNIQUE NULLS NOT DISTINCT (ts, platform, track_id, episode_name, ms_played)
);