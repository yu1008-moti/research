# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.
Language used to display plain texts is **Japanese** unless the user explicitly requests otherwise.

A Japanese translation of this file lives at `CLAUDE.ja.md` (for human readers; this file, `CLAUDE.md`, is authoritative for Claude Code). **Whenever you change the content of this file, mirror the same change into `CLAUDE.ja.md` in the same turn** — do not leave the two out of sync.

## Project overview

Personal research repository (Japanese equities/derivatives). The pipeline goes:

1. **Download** market data from the J-Quants API (Premium plan assumed).
2. **Build** raw CSV/API data into SQLite, then convert to DuckDB (`db/duckdb/*.duckdb`, one file per data domain: equities bars, derivatives bars, financials, margin/short data, etc.), and synthesize into a single `db/synthesis/synthesis.duckdb` (schemas `imp`/`raw`/`store_others`).
3. **Construct graphs**: a PyTorch Geometric heterogeneous graph (`HeteroData`) is built from `synthesis.duckdb` for GNN-based stock return/movement prediction.
4. **Model**: GNN training/evaluation on the constructed graph (under `model/`). **The graph-construction pipeline and the model code are currently being rebuilt from scratch** — the old `data_pipeline.py`-based pipeline and `model/baseline/` no longer exist; `claude_output/graph_spec.md` documents what is actually in the working tree.

Raw data is never committed — `.gitignore` excludes `**/*.duckdb`, `**/*.db`, `**/*.sqlite`, `**/*.csv`, `**/*.parquet`, `**/*.json`, etc. (only `.gitkeep` placeholders survive). A J-Quants API key must be supplied via the `jq_api_key` environment variable — never hardcode it.

## Commands

This project uses `uv` for dependency/venv management (Python >= 3.11, see `pyproject.toml`; `.venv` already exists).

```bash
uv run download_data_main.py           # fetch data from J-Quants API (see --help for date-range/rate-limit overrides)
uv run build_db_main.py build <type> [-f|-o]   # build sqlite db from csv, e.g. build drv -f (futures)
uv run build_db_main.py convert <type> [-f|-o]   # convert sqlite db -> duckdb, e.g. convert drv -f
uv run build_graph_cache_main.py     # graph cache build entrypoint (being rebuilt; see claude_output/graph_spec.md)
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

`testpaths = ["tests"]` scopes default collection to `tests/` (the repo root once held a throwaway `test_temp.py` that ran the whole graph pipeline at import time, so keep throwaway scripts out of `test_*.py` names at the root). `pythonpath = ["."]` puts the repo root on `sys.path` so `tests/*.py` can `import scripts...` without `__init__.py` packages. `tests/test_db_connect.py` currently targets an older `db_connect` API and is out of sync with the code (see `claude_output/graph_spec.md` §7).

## Directory map

- `scripts/api/` — low-level J-Quants API download helpers (sync + async).
- `scripts/download.py`, `scripts/build_db.py`, `scripts/construct_graph.py` — top-level orchestration called from the root `*_main.py` entrypoints.
- `scripts/datap/db/` — CSV/API -> SQLite -> DuckDB construction (`constructor.py`, `cons.py`, `base/{cvt,hetero,homo,scratch}.py`).
- `scripts/datap/graph/` — **graph-construction pipeline (PyG `HeteroData`), being rebuilt.** Authoritative description: `claude_output/graph_spec.md`. Files:
  - `db_connect.py` — `week`/`day` classes; `get_table(name)` runs a SQL file (`string.Template`, `$START_DATE`/`$END_DATE`) against `db/synthesis/synthesis.duckdb` (read-only) and returns a DataFrame.
  - `dataset.py` — `MarketDataset` (PyG `InMemoryDataset`); `time_frame_mode` `'w'` (weekly) / `'d'` (daily).
  - `preprocess/` — `node_utils.py` (`node_to_idx`, `varchar_to_idx`, `date_to_idx`, listed-stock dicts) and per-edge/node-type modules (`stock_corr_stock.py`, `stock_report_statement.py`, `stock_madeup_index.py`, `index_derivative_future.py`) exposing `set_info(data, ...)`.
  - `loader.py` — `NeighborLoader` setup (stub).
  - `dscribe.md` — personal notes on how the training data is built.
- `sql/` — every hand-authored `.sql` file in the repo, grouped by pipeline stage (previously scattered across `db/sql/`, `scripts/datap/graph/sql/`, etc.):
  - `sql/synthesis/` — DuckDB scripts that turn raw tables (`db/duckdb`) into `synthesis.imp.*` intermediate tables/feature views. Run manually (not orchestrated by any Python entrypoint yet). `sql/synthesis/_description.md` documents each file's input/output table and raw-column semantics (e.g. the `Mkt` market-code mapping: `0000`=旧東証一部, `0500`=プライム, etc.).
  - `sql/graph/` — older weekly-aggregation queries per node type (still referenced by `db_connect.week`).
  - `sql/graph_v2/` — new daily-frequency fetch queries (`fetch_*.sql`, referenced by `db_connect.day`) and label-design notes (`get_y.sql.md`).
- `db/duckdb/`, `db/sqlite/`, `db/synthesis/` — the DB layer described above (raw `.sql` scripts that build/populate it now live under `sql/synthesis/`).
- `model/` — GNN model code. Currently only `model/common/` (early stopping, visualization helpers) remains; see `model/README.md` for conventions.
- `notebooks/`, `graph_lab/`, `to_visualize_graph.ipynb` — exploratory/scratch notebooks. `graph_lab/sql/archive/` holds early draft queries superseded by `sql/graph/` — kept for reference only, not used by any code.
- `claude_output/` — Markdown reports/specs written by Claude Code sessions documenting implementation work (currently `graph_spec.md`, the spec of the rebuilt data-construction flow). When the user asks for a written summary/spec of work done, put it here unless told otherwise.
- `csv/`, `masks/`, `images/`, `md/` — data/output scratch directories (gitignored contents).
- `logs/` — split into subdirectories so plain log files, TensorBoard runs, and model training-run logs don't clutter each other:
  - `logs/text/` — plain `*.log` text log files (see the "Log output location" convention below).
  - `logs/tensorboard/` — TensorBoard run directories (event files), written by `model/<alias>/train.py` (default `--log-dir`).
  - `logs/model_result/` — one `*.log` file per `model/<alias>/train.py` run, mirroring everything printed to stdout during that run (parsed hyperparameters, per-epoch train/val loss & acc, save paths). See the "Log output location" convention below.

## Conventions and gotchas specific to this repo

- **`graph_v2` naming**: `sql/graph_v2/` is the *new* (daily-frequency) SQL directory used by the rebuilt pipeline — intentional. But `scripts/datap/graph_v2/` (the old Python package path) no longer exists; any `scripts.datap.graph_v2` import is a leftover bug.
- **Never loop per-code with per-row DB inserts** when building edges/features across many stock/option/future codes — this pipeline has hit real ~30-minute performance regressions from that pattern. Prefer vectorized `groupby()/shift()`/pivot-based approaches plus a single bulk insert.
- **`HeteroData` repr**: fields like `x=[258, 12]` in printed `HeteroData`/`NeighborLoader` batches denote tensor *shape*, not value.
- **Log output location**: any plain-text log file written by a script or ad-hoc run must go under `./logs/text/` (e.g. `logs/text/<script>_<timestamp>.log`), never at the repo root, directly under `./logs/`, or elsewhere. `scripts/api/download_util_async.py` already follows this (`logging.basicConfig(filename=f"logs/text/{...}.log", ...)`) — use it as the pattern for new logging setup. TensorBoard runs are a separate case and go under `./logs/tensorboard/` instead. Per-run model training logs are a third, separate case and go under `./logs/model_result/` instead, one file per run named `<timestamp>_<alias>.log` (a `logging.basicConfig(handlers=[StreamHandler, FileHandler(...)])` setup that mirrors everything printed to stdout — including a `[params]` line with all parsed CLI args — into that file; `--no-file-log` disables the file handler only, console output is unaffected). All three subdirectories are gitignored (see Directory map) so this never pollutes commits.
