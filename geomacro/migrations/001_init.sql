-- Generated from the SQLAlchemy models (PostgreSQL). The app also creates these tables itself on start.
-- Optional: on TimescaleDB run SELECT create_hypertable('raw_events','timestamp', migrate_data=>true); (not required).

CREATE TABLE alerts (
	id VARCHAR(36) NOT NULL, 
	region VARCHAR(16) NOT NULL, 
	score INTEGER NOT NULL, 
	label VARCHAR(16) NOT NULL, 
	message TEXT NOT NULL, 
	sent_to VARCHAR(64) NOT NULL, 
	sent_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	metadata JSONB NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX idx_alerts_region_time ON alerts (region, sent_at);

CREATE TABLE feed_runs (
	id VARCHAR(36) NOT NULL, 
	feed VARCHAR(32) NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	duration_s FLOAT NOT NULL, 
	ok BOOLEAN NOT NULL, 
	events INTEGER NOT NULL, 
	detail TEXT NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX idx_feed_runs_feed_time ON feed_runs (feed, started_at);

CREATE TABLE feedback (
	id VARCHAR(36) NOT NULL, 
	alert_id VARCHAR(36) NOT NULL, 
	user_feedback VARCHAR(32) NOT NULL, 
	market_reaction VARCHAR(64) NOT NULL, 
	notes TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE raw_events (
	id VARCHAR(36) NOT NULL, 
	source VARCHAR(32) NOT NULL, 
	event_type VARCHAR(32) NOT NULL, 
	region VARCHAR(16) NOT NULL, 
	timestamp TIMESTAMP WITH TIME ZONE NOT NULL, 
	lat FLOAT, 
	lon FLOAT, 
	severity FLOAT NOT NULL, 
	raw_payload JSONB NOT NULL, 
	metadata JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX idx_raw_events_region_time ON raw_events (region, timestamp);

CREATE INDEX idx_raw_events_type_time ON raw_events (event_type, timestamp);

CREATE INDEX idx_raw_events_source_time ON raw_events (source, timestamp);

CREATE TABLE risk_snapshots (
	id VARCHAR(36) NOT NULL, 
	region VARCHAR(16) NOT NULL, 
	score INTEGER NOT NULL, 
	label VARCHAR(16) NOT NULL, 
	active_signals JSONB NOT NULL, 
	details JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX idx_snapshots_region_time ON risk_snapshots (region, created_at);

CREATE TABLE setting_changes (
	id VARCHAR(36) NOT NULL, 
	ts TIMESTAMP WITH TIME ZONE NOT NULL, 
	actor VARCHAR(64) NOT NULL, 
	key VARCHAR(64) NOT NULL, 
	"old" JSONB NOT NULL, 
	"new" JSONB NOT NULL, 
	note VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_setting_changes_ts ON setting_changes (ts);

CREATE TABLE setting_overrides (
	key VARCHAR(64) NOT NULL, 
	value JSONB NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_by VARCHAR(64) NOT NULL, 
	PRIMARY KEY (key)
);

CREATE TABLE signals (
	id VARCHAR(36) NOT NULL, 
	signal_type VARCHAR(32) NOT NULL, 
	region VARCHAR(16) NOT NULL, 
	window_start TIMESTAMP WITH TIME ZONE NOT NULL, 
	window_end TIMESTAMP WITH TIME ZONE NOT NULL, 
	score INTEGER NOT NULL, 
	evidence JSONB NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX idx_signals_region_type_time ON signals (region, signal_type, window_end);

CREATE TABLE vessels (
	mmsi SERIAL NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	ship_type INTEGER, 
	lat FLOAT, 
	lon FLOAT, 
	sog FLOAT, 
	nav_status INTEGER, 
	last_seen TIMESTAMP WITH TIME ZONE NOT NULL, 
	first_seen TIMESTAMP WITH TIME ZONE NOT NULL, 
	positions INTEGER NOT NULL, 
	last_underway TIMESTAMP WITH TIME ZONE, 
	stationary_since TIMESTAMP WITH TIME ZONE, 
	last_underway_zone VARCHAR(48) NOT NULL, 
	PRIMARY KEY (mmsi)
);
