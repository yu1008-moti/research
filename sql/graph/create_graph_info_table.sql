CREATE OR REPLACE TABLE node(
  node_id   VARCHAR NOT NULL,
  is_target BOOL    NOT NULL,
  ticker    VARCHAR,
  node_type VARCHAR NOT NULL,
  time_id   INTEGER NOT NULL
);

CREATE OR REPLACE TABLE edge(
  edge_id            VARCHAR NOT NULL,
  edge_type          VARCHAR NOT NULL,
  src_node_id        VARCHAR NOT NULL,
  dst_node_id        VARCHAR NOT NULL,
  edge_weight        DOUBLE  NOT NULL,
  observable_time_id INTEGER NOT NULL
);

CREATE OR REPLACE TABLE feats(
  node_id   VARCHAR  NOT NULL,
  feats     JSON NOT NULL,
  feats_num INTEGER  NOT NULL,
);