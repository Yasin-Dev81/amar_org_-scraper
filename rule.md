# Project Rules & Environment Constraints

## 1. Target Hardware & OS
- **OS:** Debian 12 (Bookworm) `i386` (32-bit), headless (no GUI / no X11 / no Wayland).
- **Architecture:** `i686-unknown-linux-gnu` (32-bit x86).
- **RAM:** 2 GB DDR2 (hard-capped at ~2048 MB).
- **Execution Mode:** All workflows must run via CLI/SSH (use `tmux`, `screen`, or `nohup` for long-running processes). Never assume a browser, display server, or GUI tools are available.

## 2. Python & `uv` Configuration
- **Package Manager:** `uv` (`0.13.x`, `i686-unknown-linux-gnu`).
- **Python Version:** Use the system CPython `3.11.2` (`/usr/bin/python3.11`).
  - **Do NOT** request Python `>=3.12` in `pyproject.toml` or `.python-version`, because `uv` (`python-build-standalone`) does not provide prebuilt managed Python binaries for 32-bit `i686` Linux.
  - Keep `requires-python = ">=3.11"` in `pyproject.toml` and `3.11` in `.python-version`.
  - Always run scripts and tools through `uv run` (or `uvx`) rather than global `pip` or system Python directly.
- **No Auto-Downloads for Python:** Pass `--no-python-downloads` (or configure `python-downloads = "manual"` in `uv.toml`) when automating commands.

## 3. Dependency & Memory Guardrails (2 GB RAM + 32-bit)
- **Prefer Pure-Python or Lightweight Packages:** Many modern PyPI packages do not publish `i686` (`manylinux_*_i686`) wheels. Avoid heavy packages with C/C++/Rust extensions that require compiling from source on-device, as source builds can exhaust 2 GB RAM (OOM).
- **Limit Build Concurrency:** If compiling from source is unavoidable, restrict concurrency (`UV_CONCURRENT_BUILDS=1`, `make -j1` or `-j2`) and avoid memory-heavy compiler flags (such as LTO or `--enable-optimizations`).
- **No Heavy Frameworks:** Do not introduce heavy ML/AI runtimes (e.g., PyTorch, TensorFlow), headless browsers (Playwright/Chromium), or Docker-in-project dependencies on this host. Offload heavy APIs to external endpoints instead of local inference.
- **Runtime Memory Hygiene:** Stream large files, SQLite batches, or network payloads in chunks instead of loading full datasets into memory.

## 4. Development & Deployment Conventions
- **Paths & Storage:** Keep caches and virtual environments clean (`uv cache prune` when disk space is tight). Never commit `.venv/`, `__pycache__/`, or `.env` files.
- **Configuration:** Store secrets and environment variables in `.env` (loaded via `uv run --env-file .env`) and keep a sanitized `.env.example` in the repository.
- **Logging:** Log to `stdout`/`stderr` or rotating log files with bounded size so disk space is not exhausted during unattended background runs.

