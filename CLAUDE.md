# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.
Language used to display plain texts is **Japanese** unless the user explicitly requests otherwise.

A Japanese translation of this file lives at `CLAUDE.ja.md` (for human readers; this file, `CLAUDE.md`, is authoritative for Claude Code). **Whenever you change the content of this file, mirror the same change into `CLAUDE.ja.md` in the same turn** — do not leave the two out of sync.

## Project overview

Personal research repository (Japanese equities/derivatives). The pipeline goes:

1. **Download** market data from the J-Quants API (Premium plan assumed).
2. **Build** raw CSV/API data into SQLite, then convert to DuckDB (`db/duckdb/*.duckdb`, one file per data domain: equities bars, derivatives bars, financials, margin/short data, etc.), and synthesize into a single `db/synthesis/synthesis.duckdb` (schemas `imp`/`raw`/`store_others`).
3. **Construct graphs**: a PyTorch Geometric heterogeneous graph (`HeteroData`) is built from `synthesis.duckdb` for GNN-based stock return/movement prediction.
4. **Model**: GNN training/evaluation on the constructed graph (currently minimal/WIP, under `model/`).

Raw data is never committed — `.gitignore` excludes `**/*.duckdb`, `**/*.db`, `**/*.sqlite`, `**/*.csv`, `**/*.parquet`, `**/*.json`, etc. (only `.gitkeep` placeholders survive). A J-Quants API key must be supplied via the `jq_api_key` environment variable — never hardcode it.

## Commands

This project uses `uv` for dependency/venv management (Python >= 3.11, see `pyproject.toml`; `.venv` already exists).

```bash
uv run download_data_main.py           # fetch data from J-Quants API
uv run build_db_main.py -b <type> [-f|-o]   # build sqlite db from csv, e.g. -b drv -f (futures)
uv run build_db_main.py -c <type> [-f|-o]   # convert sqlite db -> duckdb, e.g. -c drv -f
uv run build_graph_main.py             # legacy/older graph construction entrypoint (scripts/construct_graph.py)
```

`black`, `ruff`, and `pytest` are available as a `dev` dependency group (`[dependency-groups] dev` in `pyproject.toml`):

```bash
uv run ruff check .     # lint
uv run black .          # format
uv run pytest           # run tests
```

`ruff` and `black` have no dedicated config (no `[tool.ruff]`/`[tool.black]`, no `ruff.toml`) and none is needed — both exclude `.venv`/`.git`/etc. by default and run fine as-is (verified).

`pytest` **does** have config now, in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

This exists because of a real footgun: the repo root has a `test_temp.py` (not a real test — it's a throwaway script whose top-level code calls `mock_code(serial_id=9999)`, which runs the *entire* graph pipeline with real DB side effects). Its filename matches pytest's default `test_*.py` discovery glob, so a bare `uv run pytest` from the repo root used to import and execute it during collection, silently kicking off a long-running pipeline run. `testpaths = ["tests"]` scopes default collection to the `tests/` directory so this can't happen by accident (explicitly running `uv run pytest test_temp.py` still executes it, which is fine since that's deliberate). `pythonpath = ["."]` puts the repo root on `sys.path` during test runs so `tests/*.py` can `import scripts...` without needing `__init__.py` packages. A minimal smoke test lives at `tests/test_smoke.py` (import-only, no DB access) — real coverage beyond that doesn't exist yet.

## Directory map

- `scripts/api/` — low-level J-Quants API download helpers (sync + async).
- `scripts/download.py`, `scripts/build_db.py`, `scripts/construct_graph.py` — top-level orchestration called from the root `*_main.py` entrypoints.
- `scripts/datap/db/` — CSV/API -> SQLite -> DuckDB construction (`constructor.py`, `cons.py`, `base/{cvt,hetero,homo,scratch}.py`).
- `scripts/datap/graph/` — **the active graph-construction pipeline** (PyG `HeteroData`). This is where most current work happens. Key files:
  - `data_pipeline.py` — node/edge registration (`preprocess` class), `HeteroData` assembly (`graphDataSet`), `NeighborLoader` setup (`get_loaders`).
  - `capm_corr.py` — `stock__corr__stock` edges via CAPM-residual rolling correlation (52-week window; needs a real market-portfolio proxy, hence stock-only).
  - `derivative_corr.py` — `option__corr__option` / `future__corr__future` edges via peer-group (same `UndSSO`/`ProdCat`) raw-return rolling correlation (shorter window; derivatives are short-lived and have no market-portfolio equivalent).
  - `cons.py` — `rel_sql` (DB/SQL file paths, pointing into `sql/graph/` — not a hyperparameter store) and `graph_params` (**the single place for all user-tunable hyperparameters**: correlation windows/thresholds, vocab dir, split ratios, `NeighborLoader` batch size/hops, etc. — every function in this pipeline defaults to `graph_params.*` and can be overridden via kwargs).
  - `sql.py` — `fetch.*`/`insert.*`/`create.*` static methods wrapping the SQL files under `sql/graph/` (see below).
  - `DS/vocab/` — persisted categorical vocabularies for graph node features.
  - `store/` — cached intermediate artifacts (e.g. CAPM residual matrix parquet).
- `sql/` — every hand-authored `.sql` file in the repo, grouped by pipeline stage (previously scattered across `db/sql/`, `scripts/datap/graph/sql/`, etc.):
  - `sql/synthesis/` — DuckDB scripts that turn raw tables (`db/duckdb`) into `synthesis.imp.*` intermediate tables/feature views. Run manually (not orchestrated by any Python entrypoint yet). `sql/synthesis/_description.md` documents each file's input/output table and raw-column semantics (e.g. the `Mkt` market-code mapping: `0000`=旧東証一部, `0500`=プライム, etc.).
  - `sql/graph/` — queries used by `scripts/datap/graph/sql.py` to build the `HeteroData` graph: weekly-aggregation queries per node type (`get_table_to_CAPM.sql` for stocks, `get_table_to_option.sql`, `get_table_to_future.sql`, `get_fin_data_by_week.sql`), the graph-info table DDL (`create_graph_info_table.sql`), and node/edge/feats insert templates (`insert_to_*_table.sql`). Paths are centralized in `scripts/datap/graph/cons.py`'s `rel_sql` class — change them there, don't hardcode paths elsewhere.
- `db/duckdb/`, `db/sqlite/`, `db/synthesis/` — the DB layer described above (raw `.sql` scripts that build/populate it now live under `sql/synthesis/`).
- `model/` — GNN model code (currently a minimal WIP `Dataset` wrapper).
- `notebooks/`, `graph_lab/`, `to_visualize_graph.ipynb` — exploratory/scratch notebooks. `graph_lab/sql/archive/` holds early draft queries superseded by `sql/graph/` — kept for reference only, not used by any code.
- `claude_output/` — Markdown reports/specs written by Claude Code sessions documenting implementation work (e.g. `graph_spec.md`, `derivative_nodes_edges_implementation.md`, `heterodata_batch_output_explained.md`). When the user asks for a written summary/spec of work done, put it here unless told otherwise.
- `csv/`, `masks/`, `images/`, `md/` — data/output scratch directories (gitignored contents).
- `logs/` — split into two subdirectories so plain log files and TensorBoard runs don't clutter each other:
  - `logs/text/` — plain `*.log` text log files (see the "Log output location" convention below).
  - `logs/tensorboard/` — TensorBoard run directories (event files), written by `model/baseline/train.py`.

## Conventions and gotchas specific to this repo

- **Historical `graph_v2` -> `graph` rename**: the graph pipeline directory used to be `scripts/datap/graph_v2/`. Several stale `graph_v2` references (import paths, cache file paths) have caused real bugs (silent cache misses, `ModuleNotFoundError`) when missed during the rename. If you see `graph_v2` anywhere, it's very likely a leftover bug, not intentional.
- **DuckDB bulk insert convention**: `insert.*` helpers in this pipeline rely on `INSERT INTO table (SELECT * FROM data_list)`, where DuckDB scans the *calling Python frame* for a local variable literally named `data_list`. This is undocumented but load-bearing — don't rename that variable when touching insert call sites.
- **Never loop per-code with per-row DB inserts** when building edges/features across many stock/option/future codes — this pipeline has hit real ~30-minute performance regressions from that pattern. Prefer vectorized `groupby()/shift()`/pivot-based approaches (see `derivative_corr.py`, `_prev_chain_preprocess` in `data_pipeline.py`) plus a single bulk insert.
- **`HeteroData` repr**: fields like `x=[258, 12]` in printed `HeteroData`/`NeighborLoader` batches denote tensor *shape*, not value.
- Node/edge type strings in the DuckDB graph-info tables (`node_type`, `edge_type`) are free-text VARCHAR — adding a new node or edge type is schema-agnostic; extend the Python-side registries (`REVERSE_RELATIONS`, `CATEGORICAL_COLUMNS`, `using_df_list` in `data_pipeline.py`) instead.
- **Log output location**: any plain-text log file written by a script or ad-hoc run must go under `./logs/text/` (e.g. `logs/text/<script>_<timestamp>.log`), never at the repo root, directly under `./logs/`, or elsewhere. `scripts/api/download_util_async.py` already follows this (`logging.basicConfig(filename=f"logs/text/{...}.log", ...)`) — use it as the pattern for new logging setup. TensorBoard runs are a separate case and go under `./logs/tensorboard/` instead (see `model/baseline/train.py`'s `--log-dir` default). Both subdirectories are gitignored (see Directory map) so this never pollutes commits.
