# Backend CI on Windows and macOS: predicted failures and triage guide

> **Historical — reviewed 2026-09-03.** This is the triage record written while
> the Windows and macOS legs were being brought up; it is not a description of
> today's CI. All three legs (`ubuntu-latest`, `windows-latest`, `macos-14`) now
> gate merges and run with `-x`, and `pytest-timeout` is installed with
> `timeout = 600` set in `pytest.ini`, so a hung test fails instead of eating the
> job. Check `.github/workflows/backend-ci.yml` and `backend/pytest.ini` before
> acting on anything below.

Until #335, `backend-ci.yml` ran `pytest` on `ubuntu-latest` and nowhere else. Two
of the three platforms we ship a backend for had no automated signal at all, and
that gap was not theoretical: #331 was a POSIX-only test assumption found by
running the suite on Windows by hand, and #313 and #321 were Windows-only defects
that reached a release candidate.

This document exists so the **first** run of the new legs can be triaged fast
instead of read cold. Everything below is a prediction made by reading the code
before the legs ever ran. Treat it as a hypothesis list to check off, not as
truth — where the real CI output disagrees with this document, the CI output
wins, and this document should be corrected.

## First real run: the two dominant causes, now fixed

The first run of the new legs reported 32 Windows failures and 21 macOS
failures. Neither of the two causes that dominate them appears anywhere in the
predictions below — a reminder that this document is a hypothesis list.

**Windows: the harness ran an event loop policy production never uses.** 25+ of
the 32 failures were `psycopg.InterfaceError: Psycopg cannot use the
'ProactorEventLoop' to run in async mode`, taking out every test that touches
the async checkpointer or the vector store. Production is fine —
`run.py:set_event_loop_policy` installs `WindowsSelectorEventLoopPolicy` — but
`tests/conftest.py` never did, so pytest-asyncio built its loops under Windows'
default Proactor policy. `conftest.py` now calls `run.set_event_loop_policy()`
at **import time** (a session-scoped autouse fixture is too late: pytest-asyncio
has already created a loop from whatever policy was in effect). Pinned by
`tests/test_event_loop_policy.py`.

**macOS: MPS is available on the runner but cannot allocate.** All 21 failures
were `RuntimeError: MPS backend out of memory (MPS allocated: 0 bytes ...)`
raised from `SentenceTransformer.__init__` moving the e5 weights onto Metal, so
every path that builds the embedder died. `macos-14` runners are virtualised
with no usable Metal allocation, yet `torch.backends.mps.is_available()` still
answers True — availability is not usability, and a real Mac under memory
pressure hits exactly the same wall. Forcing CPU everywhere was rejected
(Apple Silicon is the primary desktop platform): `embedding_model.py` now
resolves the device once, prefers MPS, and on an MPS allocation failure logs a
warning and falls back to CPU for the rest of the process. Pinned by
`tests/test_embedding_device.py`, which mocks torch so the coverage is real on
Linux too.

## The matrix

| Leg | Requirements | Gates merges? | `-x`? |
|---|---|---|---|
| `ubuntu-latest` | `entrypoints/dev/linux-cpu.txt` | **Yes** | yes |
| `windows-latest` | `entrypoints/dev/win-cpu.txt` | **Yes** | yes |
| `macos-14` (Apple Silicon) | `entrypoints/dev/mac-silicon.txt` | **Yes** | yes |

All three legs are gates. Windows and macOS were advisory while their failures
were triaged; that work finished when #358 fixed the last ten Windows failures,
and all three have been green on `main` since — see *Promoting the legs to
blocking* below for what the promotion consisted of.

## Decisions taken, and why

**`defaults.run.shell: bash` on all three legs.** Windows runners default to
PowerShell, where `cd backend && ...` and multi-line `run:` blocks behave
differently from POSIX shells. Git-bash ships on the hosted Windows image and
gives consistent forward-slash paths, which is the same choice
`app-build-smoke.yml` already made for the same reason. One set of step bodies,
three platforms.

**The venv path is parameterised, and everything runs through `python -m`.**
POSIX venvs put executables in `venv/bin`, Windows in `venv/Scripts`, so the
matrix carries a `venv_bin` value. Console scripts (`venv/bin/ruff`,
`venv/bin/pytest`) were replaced by `python -m ruff` / `python -m pytest` so the
steps never depend on git-bash resolving a `.exe` suffix. If that resolution
failed, the Windows leg would die at the lint step and produce **zero** test
signal, which is exactly the outcome this PR is trying to avoid. Both tools are
importable as modules: `meta/dev.txt` pins `pytest==8.3.4` and `ruff==0.8.4`, and
all three dev entrypoints compose it, so all three legs have them.

**`-m "not mlx_only"` is kept on every leg, macos-14 included.** `macos-14` is
the first runner where these tests *could* execute. They pull a ~280 MB fixture
model through `_download_mlx_model` (`backend/tests/conftest.py:298`), which
calls `snapshot_download` and only skips when `is_mlx_platform()` is false
(`backend/tests/conftest.py:311`) — on `macos-14` it is true, so nothing else
would stop the download. Every consumer of `mlx_test_model_path` /
`mlx_thinking_model_path` is `mlx_only`-marked
(`backend/tests/test_mlx_engine_server.py:1127,1241,1313,1375,1417` and
`backend/tests/test_tool_capability.py:231`), so the exclusion is airtight. The
goal of #335 is signal on the **shared** suite; adding a model download to CI is
a separate decision with its own cost, and should be made deliberately rather
than inherited by accident.

**`-x` is dropped on the advisory legs only.** With `-x`, pytest stops at the
first failure, so an untriaged platform reports one failure per run. There are
reportedly ~44 remaining Windows failures; at one per run that is 44 round trips.
The advisory legs need the whole list in a single run, which is also why
`fail-fast: false` is set on the matrix. Ubuntu keeps `-x` exactly as before,
because a gate should fail fast.

**`PYTHONUTF8` is deliberately *not* set on the CI legs.** The repo has two
UTF-8 guarantees — `("X utf8_mode=1", None, "OPTION")` in `backend/backend.spec`
for frozen builds, and `PYTHONUTF8: "1"` in the Electron dev spawn — and neither
reaches `pytest`. So the Windows leg runs a plain cp1252 interpreter. Setting
`PYTHONUTF8: 1` in the workflow would make several predicted failures below
disappear, but it would also hide production defects that ship to real Windows
users. We want the leg to show them.

**`ERUDI_FORCE_CPU` is deliberately *not* set.** `BaseEngine.get_engine()`
(`backend/src/engines/base_engine.py:584`) honours it as a testing override, and
`app-build-smoke.yml` does set it. Setting it here would force `macos-14` onto
`CPU_Engine`, which would skip exactly the MLX-gated tests that make the macOS
leg worth having, and would misrepresent the engine real macOS users get. If the
macOS leg turns out to be dominated by MLX hardware-probe noise, setting
`ERUDI_FORCE_CPU: 1` **on that leg only** is the escape hatch — but that should
be a reaction to evidence, not a preemptive guess.

## Predicted Windows failures

### Tier 1 — near certain

**`str(Path)` uses backslashes, so joined-argv substring asserts fail.**
`backend/tests/test_cpu_engine_server.py:59` builds
`llama_server=Path("/bin/llama-server")`, `:67` joins the argv into a string,
and `:68,69` assert `"/bin/llama-server" in joined` and `"-m /m.gguf" in
joined`. On Windows `str(WindowsPath("/bin/llama-server"))` is
`\bin\llama-server`, so both fail.
`backend/tests/test_cuda_engine_server.py:68,77,78` has the identical shape.
→ **Test fix**: build the expected substring from `str(Path(...))`, or assert on
argv elements rather than a joined string.

**Quantizer-binary fixtures omit the `.exe` suffix.** Production correctly
branches: `backend/src/engines/cpu_engine.py:356` picks
`"llama-quantize.exe" if os.name == "nt" else "llama-quantize"`, and
`backend/src/engines/cuda_engine.py:460` does the same. The fixtures do not —
`backend/tests/test_cpu_engine_hardware.py:254` writes a bare `llama-quantize`,
as does `backend/tests/test_cuda_engine_hardware.py:529` — so the lookup misses
and `quant_and_save_from_hf_format` raises `Quantizer binary not found`. This
takes out the convert/quantize success tests, the Q8 method test, and the
cleanup test. Note that `backend/tests/test_cpu_engine_hardware.py:309`
(`.unlink()`, "binary missing") would pass for the *wrong reason*, and
`:316`'s rename-to-legacy-name test fails too.
→ **Test fix**: name fixture binaries with the platform suffix.
(Historical: `quant_and_save_from_hf_format` and these fixtures were removed
altogether with #408 — the app only downloads pre-built quants.)

**`sleep` is not a Windows executable.**
`backend/tests/test_postgres_runtime.py:93` does
`subprocess.Popen(["sleep", "0"])` → `FileNotFoundError: [WinError 2]`, so
`test_stale_handle_pids_are_pruned` errors before it reaches its assertion.
→ **Test fix**: `[sys.executable, "-c", "pass"]`, the pattern
`backend/tests/test_launcher.py:306` already uses.

**`Path.unlink()` on a directory symlink is illegal on Windows.**
`backend/src/launcher/runtime_paths.py:142-143` calls `data_dir.unlink()` when
`data_dir.is_symlink()`; Windows requires `os.rmdir` for a symlink-to-directory
and raises `PermissionError [WinError 5]` otherwise. This is exercised by
`backend/tests/test_runtime_paths.py:99-101`, and it is the **dev** path, which
is what CI itself runs.
→ **Production fix**: branch on `is_dir()` and use `rmdir`.

**A Darwin-only production path is executed on the Windows runner.**
`backend/tests/test_runtime_paths.py:345` (`test_darwin_prod_swaps_payload_for_symlink`)
forces `platform.system()` to `"Darwin"`, which drives
`backend/src/launcher/runtime_paths.py:222` (`packaged_path.unlink()`, the bug
above) and `:228` (`os.symlink(...)`, which needs
`SeCreateSymbolicLinkPrivilege` and omits `target_is_directory=True`).
→ **Explicit skip**: `pytest.mark.skipif(os.name == "nt")`. The production path
genuinely is macOS-only, so a test-side skip is right here — but the `unlink`
bug above still needs the production fix.

### Tier 2 — likely, and two are real Windows-only production bugs

**`_pick_free_port` still encodes the POSIX meaning of `SO_REUSEADDR` — the #331
class, which #332 did *not* fix.**
`backend/src/engines/base_chat_server_engine.py:200` sets `SO_REUSEADDR` on its
probe socket before binding. #332 (`1fde6e5`) changed only the `_occupied_port`
helper in `backend/tests/test_base_chat_server_engine.py`; the production probe
is untouched. On Windows, `SO_REUSEADDR` *permits* binding a port another socket
is actively bound to — so the probe reports a port free while another process is
serving on it, and `_spawn_child` then hands that port to `llama-server`.
→ **Production fix**: use `SO_EXCLUSIVEADDRUSE` on win32, mirroring what the
test helper already does, or set no option at all on a pure availability probe.

**`_wait_port_closed` has the same bug, and worse consequences.**
`backend/src/engines/base_chat_server_engine.py:222`. The function's entire
purpose is to block until the OS releases a port. On Windows the `SO_REUSEADDR`
bind succeeds immediately even while the old server still holds it, so the
function always returns "free" at once and model-swap teardown races become
silent. Unlike `_pick_free_port`, this has no `TestPickFreePort`-style coverage
at all, so **no test will go red for it** — it needs a deliberate fix, not a
triage entry.
→ **Production fix**, same shape.

**`proc.terminate()` leaks an embedded Postgres on Windows.**
`backend/tests/test_launcher.py:413` terminates a child spawned at `:387-392`
that is the real `run.py`, and therefore has booted a real postmaster. On POSIX,
`terminate()` is SIGTERM and the handler at `backend/run.py:587` runs the
lifespan shutdown. On Windows there is no SIGTERM; `TerminateProcess` runs
neither the handler, nor the lifespan shutdown, nor `atexit`. Expect an orphaned
`postgres.exe` holding a data dir and a port for the rest of the job.
→ **Test fix**: use the stdin-EOF graceful-quit contract
`backend/run.py:315-361` already implements (`ERUDI_WATCH_STDIN=1` + close
stdin), then fall back to `kill()`.

**Undrained `stderr=PIPE` can hang the job rather than fail it.**
`backend/tests/test_launcher.py:387-399` opens the child with `stderr=PIPE` and
never reads it, then blocks in `proc.stdout.readline()`. Windows anonymous pipes
default to roughly 4 KB versus 64 KB on Linux, and the child imports the whole
ML stack. If stderr fills, both sides block forever; the `while time.time() <
deadline` guard is only evaluated *between* reads. `backend/pytest.ini` declares
no timeout plugin, so this is an unbounded hang. **If the Windows leg times out
with no summary, look here first.**
→ **Test fix**: `stderr=subprocess.DEVNULL`, or drain it on a thread.

**`test_parent_alive_probe_posix_tracks_ppid` is not skipped off POSIX.**
`backend/tests/test_launcher.py:280-289` asserts on `os.getppid()` behaviour, but
on Windows `run._parent_alive_probe` takes the psutil branch
(`backend/run.py:390-404`), not the ppid branch the test names. Its second
assertion then passes only by luck — it depends on `ppid + 12345` not being a
live pid — while the POSIX branch gets zero coverage on that leg and the test
still reports green.
→ **Explicit skip** plus an always-run test that forces the branch.

**Console log-path shortening is a no-op on Windows, and the guard test hides it.**
`backend/src/core/logging.py:180` does `record.pathname.find("backend/")`. On
Windows the pathname contains `backend\`, `find` returns `-1`, and every console
line gets the full absolute path. The test does not catch it because it feeds a
hardcoded POSIX literal (`backend/tests/test_logging_config.py:41`) and asserts
on a POSIX substring (`:139`).
→ **Production fix** (normalise via `os.sep` or `Path(...).parts`) plus a test
parametrised per-OS.

**`open()` without `encoding=` on a bundled catalog.**
`backend/src/database/seed.py:171` reads `base_models_fallback.json` with a bare
`open(..., 'r')`. The file is ASCII today so CI passes, but the surrounding
`except` clauses only catch `FileNotFoundError` and `json.JSONDecodeError` — the
first non-ASCII byte added to that catalog becomes an uncaught
`UnicodeDecodeError` at boot on a cp1252 host. This is precisely the #149 failure
mode (`alembic.ini` em dash under an ASCII locale) in a second, unguarded place.
→ **Production fix**: `encoding="utf-8"`. Cheap, and worth doing before it bites.

### Tier 3 — plausible, but these are guesses

Labelled as guesses because the mechanism is real but whether it *fires* depends
on runtime conditions we cannot check from here.

- **pgserver boot is the single point of failure for the whole leg — the
  highest-variance unknown on Windows.** `backend/tests/conftest.py:66` boots one
  real cluster per session, so a single boot failure ERRORs hundreds of tests at
  once and makes the output unreadable. Several things were checked and are
  *fine*: pgserver 0.1.4 ships a `cp312` `win_amd64` wheel, its Windows code path
  uses TCP rather than unix sockets, and the symbols imported at
  `backend/src/launcher/postgres_runtime.py:35-36` are exported on Windows too,
  so there is no `ImportError`. Both `psutil` and `pgserver` reach the Windows
  leg via `meta/base.txt`. The genuine unknown is that `postgres.exe` refuses to
  run with Administrator rights and must re-exec under a restricted token, and
  the GitHub runner account is in Administrators. This normally works. **If the
  Windows leg shows hundreds of errors with one root cause, check this first**;
  the fix would be a skip-gated DB tier, not a patch.
- **`_space_safe_socket_dir` is unix-socket logic on a platform with no unix
  sockets.** `backend/src/launcher/postgres_runtime.py:62-71`. It is only reached
  when the pgdata path contains a space, and runner temp paths do not, so it
  should not fire in CI — but it is a live landmine for any developer running
  from a home directory with a space in it.
  → **Production fix**: short-circuit on `os.name == "nt"`.
- **`_recover_corrupt_pgdata` may hand a dirty directory to `initdb`.**
  `backend/src/launcher/postgres_runtime.py:161-168` uses
  `shutil.rmtree(entry, ignore_errors=True)`. Windows refuses to unlink files a
  just-stopped postmaster still holds; `ignore_errors=True` swallows that, and
  pgserver's `initdb` then refuses a non-empty target.
  → **Production fix**: retry with backoff and fail loudly rather than silently
  proceeding.
- **`subprocess` with `text=True` and no `encoding=`**, at
  `backend/src/database/backup.py:64-65` (pg_dump stderr, which is localised on
  non-English Windows), `backend/src/engines/cuda_engine.py:481-482`, and
  `backend/src/engines/mlx_engine.py:570-571`; and in tests at
  `backend/tests/test_utils_lazy_init.py:60-61` and
  `backend/tests/test_lazy_langchain_imports.py:52-53`, both of which capture a
  child importing the entire ML stack. A single non-ASCII byte in a warning
  becomes a `UnicodeDecodeError` in the parent.
- **`monkeypatch.setenv("HOME", ...)` is a no-op on Windows.**
  `backend/tests/test_runtime_paths.py:23` — `ntpath.expanduser` prefers
  `USERPROFILE`. Individual tests are saved because they patch `Path.home`
  directly, but the autouse sandbox does not actually sandbox, so a future test
  relying on it alone would write into the runner's real profile.
- **`kill_port_process` is silently inert on Windows.** `backend/run.py:259-277`
  shells out to `lsof` and `kill`, both absent on Windows, and the failures are
  swallowed by a bare `except`. The `NO_PORT_AVAILABLE` last-resort recovery
  therefore does nothing there. No test covers it, so nothing goes red — a gap,
  not a failure.
- **CRLF is real but currently harmless.** There is no `.gitattributes` in the
  repo and the hosted Windows image sets `core.autocrlf=true`, so text files
  check out with CRLF. No byte-length, hash, or line-count assertion over a repo
  file appears to depend on that: `backend/tests/test_migrations.py:137` only
  asserts ASCII-decodability, and `backend/tests/test_spec_files.py:20` reads
  with an explicit encoding and does substring checks.

### Ruled out — do not spend triage time here

- **No POSIX process-group code exists in the backend.** Zero hits for
  `os.setsid`, `os.killpg`, `os.getpgid`, `preexec_fn`, or `start_new_session`
  under `backend/`. That logic lives only in `frontend/src/main.js`, which the
  Python CI never touches.
- **`backend/run.py:587-588`** registers `SIGTERM`/`SIGINT` handlers; both
  constants exist and are settable on Windows. Not a failure.
- **`backend/tests/test_parent_watchdog_spawn.py`** is skipped wholesale off
  POSIX by a module-level `pytestmark` at `:43`. It will not fail or hang on
  Windows — but see the coverage note below.

## Predicted macOS failures

The macOS leg is expected to be quieter than Windows, because the developers who
wrote the suite run it on Apple Silicon daily. Two things nevertheless change:

**`is_mlx_platform()` flips to true, so MLX-gated tests execute for the first
time in CI.** The helper resolves `BaseEngine.get_engine().__name__ ==
"MLX_Engine"` (`backend/tests/_helpers.py:13`), which is true on `macos-14`
(`backend/src/engines/base_engine.py:588-590`). Most MLX-gated tests are *also*
`mlx_only`-marked and therefore still excluded. **Exactly three tests are
Linux-skipped but macos-14-executing under `-m "not mlx_only"`:**

1. `backend/tests/test_engines.py:74` (`test_mlx_specific_fields`) — gated only
   by `is_mlx_platform()` at `:70-73`, no `mlx_only` marker. Calls the real
   `MLX_Engine.get_flat_hardware_data()` and asserts on `mlx_chip_model`,
   `mlx_gpu_cores`, `mps_available`, `neural_engine_tops`, `unified_memory`.
2. `backend/tests/test_wire_tool_capability.py:147` and
3. `backend/tests/test_wire_tool_capability.py:155` — gated by
   `pytest.importorskip("mlx_vlm")` at `:148` and `:156`, which is a *runtime*
   skip invisible to marker selection.

All three were executed on a real Apple Silicon host while preparing this
change and **all three pass**. Confidence that the macOS leg is green on these
is correspondingly high.

The residual risk is hardware probing on a *virtualised* runner:
`_detect_apple_silicon_chip` (`backend/src/engines/mlx_engine.py:556-590`)
shells out to `system_profiler`, and if the reported chip string is not a key in
`_APPLE_SILICON_SPECS` the specs dict is empty and GPU fields zero out. The
assertions are range- and type-based, and `cpu_model` falls back to a literal at
`backend/src/engines/mlx_engine.py:667`, so they should still hold. If one goes
red, the fix is a test fix (assert on presence rather than on probed values) —
resist the urge to weaken the production probe.

**Five more `test_engines.py` tests silently change what they cover.**
`backend/tests/test_engines.py:24,46,53,100,113` call `get_engine()` unmocked,
so on macos-14 they exercise `MLX_Engine.get_flat_hardware_data()` where Ubuntu
exercises `CPU_Engine`'s. They pass on real hardware; the point is that a green
macOS leg is testing a *different* code path under the same test names.

**A session-scoped engine global leaks on macOS.** `backend/tests/conftest.py:172-173`
sets the module global `config.LLM_Engine` once per session and never restores
it, so on macos-14 it stays `MLX_Engine` for every later test. Unpatched
consumers (`backend/src/domains/llms/repository.py:454,474,492` and
`backend/src/domains/llms/services.py:462`) would take the MLX branch instead of
the GGUF one. Mitigated in practice because those helpers swallow exceptions
(`backend/src/domains/llms/repository.py:459-461`) and nearly every affected test
patches explicitly. → **Test fix** if it bites: scope the assignment with
`monkeypatch`.

**CPU-gated tests now skip on macOS.** `is_cpu_platform()` is false there, so
some coverage that Ubuntu provides is simply absent on the macOS leg. That is
expected and correct; it just means a green macOS leg is a weaker statement than
a green Ubuntu one.

**Install size and time.** `entrypoints/dev/mac-silicon.txt` composes
`meta/mac-silicon-specs.txt`, which pulls `mlx-vlm==0.6.17` (with `mlx` pinned) and transitively
torch, opencv, Pillow and mlx-audio. Every wheel in both new trees was checked
against PyPI for cp312: all resolve, none is source-only, and no C or Rust
toolchain is needed (even `llguidance`, `miniaudio` and `opencv-python` ship
arm64 wheels). Expect roughly 450-700 MB downloaded and 2.5-3.5 GB installed —
slow on a cold pip cache, not broken.

**`macos-14` is the correct floor, and `macos-13` would not have worked.** mlx's
payload lives in `mlx-metal`, whose wheel is `macosx_14_0_arm64` — macos-14
satisfies it exactly. Do not "simplify" this leg to an older runner image.

**The mac tree does not include `meta/cpu.txt`.** Unlike win-cpu and linux-cpu,
`entrypoints/prod/mac-silicon-prod.txt` composes only `meta/base.txt` and
`meta/mac-silicon-specs.txt`, so `gguf` is absent on the macOS leg. Nothing in
the suite exercises a real GGUF tokenizer load (all `compute_supports_tools`
paths are patched), so this is latent rather than breaking.

**Shared-memory exhaustion when clusters leak.** Observed while validating this
change locally on macOS: `initdb` failed with *"all available shared memory IDs
have been taken ... SHMMNI"* while `ipcs -m` showed 32 segments against a
`kern.sysv.shmmni` limit of 32 and **zero** postgres processes alive — i.e. the
System V table was full of orphans from earlier killed clusters. On a fresh CI
runner this should not occur, since each job gets a clean VM. It is recorded here
because it produces a spectacular and totally misleading failure (a dozen
unrelated DB tests erroring at setup) and because it is a standing hazard for
anyone running the suite repeatedly on their own Mac. Remedy on a dev machine:
reclaim the orphaned segments with `ipcrm -m <id>`, or reboot.

## Two things that affect all three legs

**Every leg downloads a ~470 MB embedding model on a cold cache.**
`backend/tests/test_ingestion_embeddings.py:18` marks the module `integration`
(not `mlx_only`), and `:23` instantiates `E5Embeddings()`, which reaches
`SentenceTransformer(E5_MODEL_NAME, ..., local_files_only=embedding_model_available())`
at `backend/src/ingestion/embeddings.py:65-68`. On a cold cache that flag is
false and the model is fetched from the Hub. This is already true of the Ubuntu
leg today — #335 does not introduce it — but it now happens **three times per
run** instead of once, and it is the suite's single largest flakiness surface,
since an HF hiccup turns a leg red for reasons unrelated to the code. There is
no HuggingFace cache step in the workflow. → **CI fix**: cache
`~/.cache/huggingface` per leg. Deliberately left out of this PR to keep the
diff to the matrix, but it is the first follow-up worth doing.

**There is no `pytest-timeout`.** `backend/pytest.ini` declares no timeout
plugin, so any test that hangs consumes the full job limit instead of failing.
That matters much more now: the predicted `stderr=PIPE` deadlock above is a
Windows *hang*, not a Windows failure, and a hung advisory leg produces no list
of failures at all — the exact opposite of what this PR is for. → **Recommended
before promoting the legs to blocking**: add `pytest-timeout` to `meta/dev.txt`
and set a per-test timeout.

**A note for whoever writes the skips.** `backend/pytest.ini:5` sets
`--strict-markers`, so an undeclared `@pytest.mark.<name>` is a hard collection
error, not a warning. Adding `pytest.mark.skipif` is always safe; introducing a
*new* marker (say `windows_only`) requires adding it to the `markers` list at
`backend/pytest.ini:6-11` in the same commit, or the whole leg dies at
collection.

## Green does not mean covered

Adding the Windows leg does **not** close the parent-death watchdog gap. The
psutil branch (`backend/run.py:393-404`) is covered only by the unit test at
`backend/tests/test_launcher.py:293-308`; the real end-to-end proof
(`backend/tests/test_parent_watchdog_spawn.py`) is POSIX-only by construction
(`:43`), and its own docstring defers Windows to the stdin-EOF watcher plus that
unit test. A green Windows leg says the suite passes on Windows, not that
Windows-specific behaviour is tested.

The same caution applies to the two `SO_REUSEADDR` production bugs above: one has
weak coverage and the other has none, so neither will show up as a red test.

## Promoting the legs to blocking

**Done.** Recorded here as history, and as the checklist for any leg added later.

Per #335's definition of done, each remaining failure had to be either fixed or
explicitly skipped with a stated reason — `pytest.mark.skipif` with a real
`reason=` string, never a silent deselection. Every one was **fixed**; nothing
was skipped to reach green. The last ten went in #358: a hardcoded POSIX path
literal asserted against `str(Path(...))` in the spawn-argv tests, and a shared
quantizer fixture writing a binary named `llama-quantize` with no extension when
both engines correctly look for `llama-quantize.exe` on Windows.

The promotion itself was three changes:

1. `experimental` dropped from the matrix and `continue-on-error` removed from
   the job, so a red leg fails the run.
2. `-x` restored on all three legs. Dropping it was right for an untriaged
   platform — you want the whole failure list per run — but a gate should fail
   fast, and a triaged platform's failures are regressions, which come one at a
   time.
3. `pytest-timeout` added (`meta/dev.txt`) with `timeout = 600` in
   `pytest.ini`, which the section above listed as recommended **before**
   promotion. The reason is specific: the failure mode that worried us most on
   Windows is a *hang*, not a failure, and a hung blocking leg produces no
   signal at all while consuming the whole job limit. The ceiling is deliberately
   generous — it is there to catch a deadlock, not to police slow tests. The
   session-scoped pgserver fixture, which runs inside the first test's setup, is
   the longest legitimate stretch under it.

Still open, and deliberately not addressed here: the pip/HuggingFace cache
sharing noted above, and branch protection, which needs repo-admin rights.

## Branch protection

At the time of writing, `backend-ci` was **not** among the required status checks
on `main`. The only required contexts were the two `app-smoke` matrix legs, which
matches the open question already recorded in
`docs/dev/release-engineering-audit.md:126`. Renaming the backend check to
`backend-ci (ubuntu-latest)` therefore orphans nothing today.

Two consequences for whoever owns repo settings:

1. If `backend-ci` is added to branch protection later, the context to require is
   `backend-ci (ubuntu-latest)` — the bare `backend-ci` name no longer exists.
2. The `windows-latest` and `macos-14` contexts are no longer advisory and are
   now safe to require. Until they are added to branch protection, a red leg
   fails the run and is visible on the PR, but does not by itself block the
   merge button — the gate is only as strong as the required-contexts list.
   The three contexts to require are `backend-ci (ubuntu-latest)`,
   `backend-ci (windows-latest)` and `backend-ci (macos-14)`.
