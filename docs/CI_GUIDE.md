# CI/CD & Reliability Guide

How to understand the optimized CI pipeline, reproduce failures locally, and understand every mount and cache involved.

---

## 1. Local CI Gates — Three Levels

There is no magic here. Every level is documented so that agents and humans can reason about what runs where, on which filesystem, and why.

### Level 0 — Git Hooks (fast, no Docker)

Installed by `make install-hooks`. Both `pre-commit` and `pre-push` run:
```bash
make lint && make test-unit
```
**Directly in the current shell** — no `docker run` involved.

Why no Docker: the devcontainer is built from the same `devenv-base` image that GitHub CI uses. Running directly in it gives identical toolchain coverage without the CARGO_HOME conflict that corrupted Cargo's fingerprint cache in earlier designs (see §5 for the full story).

Bypass when needed: `git commit --no-verify` / `git push --no-verify`.

### Level 1 — `make ci-local` (GitHub Tier 1 simulation, ~5-10 min)

Builds the `devenv-base` image locally (or uses a cached layer), then runs the **exact same three `docker run` commands** that `.github/workflows/ci.yml` executes:

```
make lint          (ruff, clippy -D warnings, check-ffi, hadolint, …)
make build-tools   (virtmcu-tools Python wheel validation)
make test-unit     (Rust unit tests + Python unit tests, no QEMU)
```

Run this before opening a pull request.

### Level 2 — `make ci-full` (authoritative parity, ~40-50 min cold)

`ci-local` + `ci-asan` + `ci-miri` + full `builder` Docker image build (QEMU compiled inside) + every smoke phase run sequentially inside that image via `scripts/ci-phase.sh all`.

This is the authoritative "will GitHub be green?" answer. Run this before merging to main.

---

## 2. Mount Strategy — What Lives Where

Every `docker run devenv-base` call in the Makefile uses these mounts. There is no `.cargo-cache` host-path bind-mount anymore.

| Mount | Host side | Container path | Type | Purpose |
|---|---|---|---|---|
| Workspace | `$(CURDIR)` | `/workspace` | bind | Source code, test scripts, generated `.venv-docker`, `test-results/` |
| Cargo registry | Docker named volume `ci-cargo-registry` | `/usr/local/cargo/registry` | named volume | Downloaded crate source tarballs. Persists across runs; never touches the host filesystem |
| Compiled artifacts | (none — ephemeral) | `/tmp/ci-target` via `CARGO_TARGET_DIR` | tmpfs inside container | Rust `.rlib`/binary outputs. Disappears when the container exits |
| Python venv | `$(CURDIR)/.venv-docker` (inside workspace bind) | `/workspace/.venv-docker` via `UV_PROJECT_ENVIRONMENT` | bind (subdir) | Isolated Python environment so host `.venv` and container venv never mix |

**What is explicitly NOT mounted into the container:**
- `$(CURDIR)/target/` — the host's Cargo target directory. This is the critical exclusion. Sharing it between the host (CARGO_HOME=/usr/local/cargo) and the container would cause fingerprint corruption (see §5).
- `$(CURDIR)/.cargo-cache/` — the old host-path registry cache. Replaced by the `ci-cargo-registry` named volume.

**The builder-image smoke tests** (in `ci-full` and `test-integration-docker`) use the same bind-mount for `/workspace` but target the `builder` image instead of `devenv-base`. The `builder` image already has QEMU, all `.so` plugins, and the test tools (`zenoh_coordinator`, `mujoco_bridge`, `resd_replay`) baked into `/opt/virtmcu/`. No source compilation happens during smoke tests.

### Named Docker Volume Lifecycle

```bash
# Inspect
docker volume inspect ci-cargo-registry

# Prune if corrupted or you need a clean slate
docker volume rm ci-cargo-registry

# ci-local will recreate it automatically on next run
```

---

## 3. Docker Image Hierarchy

```
rust-builder          (Stage 0)  Rust toolchain + bindgen + cargo-audit etc.
base                  (Stage 1)  Debian slim + vscode user + uv + gh CLI
toolchain             (Stage 2)  base + build deps + ARM toolchain + Python + CMake + FlatBuffers
flatcc-builder        (Stage 3)  Temporary: builds flatcc from source
simulation-toolchain  (Stage 4)  toolchain + flatcc + zenoh-c + Rust (from rust-builder)
qemu-builder          (Stage 5)  simulation-toolchain + QEMU cloned + base QEMU compiled
builder               (Stage 6)  qemu-builder + hw/ plugins + tools binaries → installed to /opt/virtmcu
devenv-base           (Stage 7)  toolchain + Rust + Node.js + Python deps (NO QEMU baked in)
devenv                (Stage 8)  devenv-base + /opt/virtmcu copied from builder
runtime               (Stage 9)  base + Python deps + /opt/virtmcu (lean runtime image)
```

**devenv-base vs devenv:**
- `devenv-base` is what GitHub Tier 1 and `make ci-local` use — it has the full toolchain but no QEMU binary. Fast to build, used for lint + unit tests.
- `devenv` is the developer-facing image used in `.devcontainer/`. It includes the pre-built QEMU from `builder`.

**Why test tools are built in Stage 6 (`builder`), not in a separate stage:**
A previous design had a `test-tools-builder` stage that copied a subset of the workspace and used `sed` to prune `Cargo.toml` members. This was fragile: new workspace members broke it silently, and the wrong binary name (`cyber_bridge` package produces `mujoco_bridge` + `resd_replay`, not a binary called `cyber_bridge`). Stage 6 already has the full workspace under `/build/virtmcu/{hw,tools}`, so all members are present and no pruning is needed.

---

## 4. Pipeline Overview (GitHub CI Tiers)

```mermaid
graph TD
    subgraph Tier 1 [Fast Checks]
        lint[make lint]
        bt[make build-tools]
        ut[make test-unit]
        lint --> bt --> ut
    end

    subgraph Tier 2 [Emulator Build - both arches in parallel]
        bq[docker buildx bake builder]
    end

    subgraph Tier 3 [Smoke Tests - 20 phases × 2 arches]
        smoke[bash scripts/ci-phase.sh PHASE inside builder image]
    end

    subgraph Tier 4 [Coverage]
        pcov[Peripheral C coverage]
        fcov[Guest firmware coverage]
    end

    subgraph Tier 5 [Publish]
        pub[Push devenv + runtime multi-arch manifests]
    end

    Tier 1 --> Tier 3
    Tier 2 --> Tier 3
    Tier 3 --> Tier 4
    Tier 4 --> Tier 5
```

### Tier 1 — Static Analysis & Unit Tests
GitHub runs three `docker run devenv-base` commands sequentially with no `CARGO_HOME` override. `make ci-local` mirrors this exactly using the same image, same flags, and same command sequence.

### Tier 2 — Build QEMU
`docker buildx bake builder` compiles QEMU and all Rust plugins inside the multi-stage Dockerfile. The resulting image is pushed to GHCR and tagged with the commit SHA so Tier 3 runners can pull it without rebuilding.

### Tier 3 — Smoke Tests
Each phase is an independent `docker run builder bash scripts/ci-phase.sh <phase>` job. The phases run in parallel across 40 GitHub runners (20 phases × 2 arches). `scripts/ci-phase.sh` is the single source of truth for what each phase does — it is used by both GitHub and `make ci-full`.

### Tier 4 — Coverage
Collects `.gcda` files produced during Tier 3 (via `GCOV_PREFIX`) and runs `gcovr` inside the builder image to produce unified reports.

---

## 5. The CARGO_HOME Corruption Story (Why the Design Is What It Is)

This section exists so agents and humans never repeat the same mistake.

**The old design** had three Cargo environments sharing the same `target/` directory:

| Context | CARGO_HOME | target/ |
|---|---|---|
| Direct `cargo` in devcontainer | `/usr/local/cargo` (baked) | `/workspace/target` |
| `make ci-local` docker run | `/workspace/.cargo-cache` (overridden) | `/workspace/target` (bind-mounted) |
| GitHub CI docker run | no override → `/usr/local/cargo` | `/workspace/target` |

Cargo embeds the registry source path in every `.rlib` fingerprint. When `make ci-local` overrode `CARGO_HOME` to `/workspace/.cargo-cache` but mounted the same `/workspace/target` that the devcontainer had compiled against `/usr/local/cargo`, Cargo saw the existing `.rlib` files as belonging to a different registry and tried to recompile. Partial downloads (from interrupted runs) left the registry in an inconsistent state. Result: "can't find crate for `proc_macro2`" errors that disappeared after `rm -rf /workspace/.cargo-cache/registry` — until the next interrupted run.

**The fix has two parts:**
1. `CARGO_TARGET_DIR=/tmp/ci-target` — compiled artifacts stay inside the container and vanish on exit. The host `target/` is never touched.
2. Named volume `ci-cargo-registry` at `/usr/local/cargo/registry` — crate downloads persist across `docker run` invocations without a host-path bind that the devcontainer also writes to.

**Rule:** Never add `-e CARGO_HOME=<host-path>` to a `docker run` that also mounts the workspace. If you need to cache downloads across runs, use a named Docker volume.

---

## 6. Reliability Architecture (The "Safe Workspace")

### Workspace-Scoped Cleanup (`cleanup-sim.sh`)
Inspects `/proc/<pid>/cwd` and `/proc/<pid>/cmdline`. Only kills orphaned QEMU/Zenoh processes that originated from the active workspace directory — other agents' simulations in other directories are untouched.

### The FFI Gate (`check-ffi.py`)
Uses `pahole` to extract struct offsets directly from the compiled `qemu-system-arm` binary and compares them against the `assert!` statements in Rust. Layout drift → loud failure before any simulation starts.

### Dynamic Port Allocation (`get-free-port.py`)
Tests never use hardcoded ports. Every parallel worker gets its own ephemeral Zenoh router via the `zenoh_router` pytest fixture or `scripts/get-free-port.py` in bash.

---

## 7. Test Script Conventions

| Assumption | Safe / Recommended | Banned |
| :--- | :--- | :--- |
| Ports | `scripts/get-free-port.py`, `zenoh_router` fixture | Hardcoded numbers (7447, 1234) |
| File generation | `tmp_path` fixture, `mktemp -d` | Writing to `workspace_root` or `test/phaseX/` |
| Uniqueness | `os.getpid()`, `worker_id` | `random.randint()` |
| Daemons | Reusable `pytest` fixtures | `subprocess.Popen("cargo run...")` |
| Temp dirs | `tempfile.mkdtemp()` or `/tmp/virtmcu-test-*` | Fixed `/tmp/my_test_data` |
| Process kill | Trust workspace scoping | `pkill qemu` (global kill) |
| QEMU path | `scripts/run.sh` | `/opt/virtmcu/bin/...` (absolute) |
| Cleanup | Fixture / Makefile | `make clean-sim` inside a fixture |

---

## 8. Reproducing a GitHub CI Failure Locally

1. `make check-ffi` — verify FFI layout is valid.
2. `make ci-local` — reproduce Tier 1 failures (lint/build-tools/unit-tests).
3. For a specific smoke phase:
   ```bash
   # Build or pull the builder image first
   bash scripts/docker-build.sh builder
   # Run the failing phase
   docker run --rm \
     -v "$(pwd):/workspace" -w /workspace \
     -e PYTHONPATH=/workspace \
     -e VIRTMCU_STALL_TIMEOUT_MS=120000 \
     -e USER=vscode \
     ghcr.io/refractsystems/virtmcu/builder:dev-amd64 \
     bash scripts/ci-phase.sh <PHASE_NUMBER>
   ```
4. For the full matrix: `make ci-full` (runs phases sequentially, same script as GitHub).

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| `can't find crate for proc_macro2` / `rand` / etc. | Cargo fingerprint corruption (CARGO_HOME mismatch with shared target/) | `docker volume rm ci-cargo-registry` then re-run. Never use `-e CARGO_HOME=<host-path>` with a mounted workspace. |
| `SIGSEGV` in plugin | FFI layout drift | `scripts/check-ffi.py --fix` |
| `Address already in use` | Hardcoded port | Switch to `scripts/get-free-port.py` |
| `Permission denied` in /workspace | UID mismatch in container | `sudo chown -R 1000:1000 .` |
| CI STALL | Runner load spike or ASan overhead | The system automatically scales `VIRTMCU_STALL_TIMEOUT_MS` to 300s under ASan. If stalls persist, check logs for deadlocks or manually raise the env var. |
| `cyber_bridge` binary not found | Wrong binary name | The `cyber_bridge` package produces `mujoco_bridge` and `resd_replay` — never a binary called `cyber_bridge`. |

---

## 10. Clock Sync & Stall Timeouts

To maintain deterministic co-simulation, `zenoh-clock` enforces a **Stall Timeout**. If QEMU fails to reach a virtual-time boundary within a certain wall-clock window, it reports a STALL (error code 1).

### Enterprise Policy: Environment-Driven Timeouts
We avoid hardcoding `stall-timeout` in test files. Instead, the system uses a centralized scaling policy:

1. **Default**: 5 seconds (`VIRTMCU_STALL_TIMEOUT_MS=5000`).
2. **ASan/UBSan**: 300 seconds (5 minutes). This is automatically injected by `tests/conftest.py` when `VIRTMCU_USE_ASAN=1` is detected.
3. **Manual Override**: You can override this globally by setting the `VIRTMCU_STALL_TIMEOUT_MS` environment variable.

### Why we don't hardcode in tests
- **Portability**: Different runners have different performance profiles.
- **Fail-Fast**: Standard runs should fail quickly if a deadlock occurs.
- **Maintenance**: Changing the global timeout policy happens in one place (`conftest.py`), not in 50 test files.

If you encounter a `RuntimeError: Node X reported CLOCK STALL`, it means QEMU stopped making progress. Check the QEMU logs for BQL deadlocks or extremely slow TCG translation.
