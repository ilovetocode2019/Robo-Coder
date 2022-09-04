CREATE TABLE IF NOT EXISTS guild_config (
guild_id BIGINT PRIMARY KEY,
mute_role_id BIGINT,
muted BIGINT ARRAY,
spam_prevention BOOL,
ignore_spam_channels BIGINT ARRAY,
log_channel_id BIGINT
);

CREATE TABLE IF NOT EXISTS timers (
id SERIAL PRIMARY KEY,
event TEXT,
data jsonb DEFAULT ('{}'::jsonb),
expires_at TIMESTAMP,
created_at TIMESTAMP DEFAULT (now() at time zone 'utc')
);

CREATE TABLE IF NOT EXISTS reaction_roles (
guild_id BIGINT,
channel_id BIGINT,
message_id BIGINT,
title TEXT,
color INT,
roles jsonb DEFAULT ('{}'::jsonb)
);

CREATE TABLE IF NOT EXISTS autoroles (
guild_id BIGINT,
role_id BIGINT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS songs (
id SERIAL PRIMARY KEY,
song_id TEXT,
title TEXT,
filename TEXT,
extractor TEXT,
plays INT,
data jsonb DEFAULT ('{}'::jsonb),
created_at TIMESTAMP DEFAULT (now() at time zone 'utc'),
updated_at TIMESTAMP DEFAULT (now() at time zone 'utc')
);

CREATE TABLE IF NOT EXISTS song_searches (
search TEXT PRIMARY KEY,
song_id INT,
expires_at TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS unique_songs_index ON songs (song_id, extractor);
