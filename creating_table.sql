CREATE TABLE IF NOT EXISTS plays (
    track_id TEXT,
    track_name TEXT,
    artist_name TEXT,
    played_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (trak_id, played_at)
)