# Plan: rebuild `labs/subc` on labkit and the build DAG

> **Status: built and verified, 2026-09-15.** Phases 1–8 are done except the
> Gradescope re-upload, which is a manual step. Measured outcomes: the solution
> scores **30/30**; an untouched publish scores **0/30** in 6 s; a touched but
> still-stubbed lab scores **3/30**; a module that never handshakes scores
> **0/10** on `svsim` in 7 s. The autograder returns **30.0** on the real zip.
>
> Three things the build changed about this plan, each of which only showed up
> by running it:
>
> * **`$fatal` cannot be used in the watchdog.** It leaves `xsim.exe` and
>   `xsimk.exe` alive on Windows, and `run_sv_sim(capture_output=True)` then
>   blocks on a pipe that never closes — a failure that should take 7 seconds
>   took **10 min 28 s**. The watchdog ends with `$finish`, and
>   `compare_hardware` scores the resulting short CSV. See
>   [The watchdog](#the-watchdog).
> * **Watchdog time is not wall-clock time.** A stalled design propagates X on
>   every clock edge and simulates far more slowly than a working one. 10 ms of
>   simulated time was minutes of real time; the value is now 500 µs, against a
>   26 µs correct run.
> * **The latency check had a loophole.** An untouched testbench records
>   `cycles = 0`, which is "within `nbits + 2`" and collected all 4 points. It
>   is now credited only on cases that were answered correctly.
>
> Two defects found in the existing material and fixed in passing: the error
> bound was written backwards in `subc_divide.py`'s docstring
> (`qhat < a/b <= qhat + 2^-nbits`), and `theory.md` gave `z`'s range as
> `2**(nbits-1) - 1`. One pre-existing bug is **not** fixed and is reported
> separately: `hwdesign/grading.py` crashes with `UnicodeEncodeError` when
> stdout is not UTF-8, which affects `prng` identically.

Bring the Unit 2 conditional-subtraction divider up to the shape `labs/prng` now
has: one annotated solution in `hwdesign-soln`, the student tree **generated**
by `labkit`, and the lab run as a graded `BuildDag` instead of a pair of
hand-run scripts.

Reference: [docs/instructor/labs.md](../docs/instructor/labs.md) (annotation,
`lab.toml`, publishing) and
[docs/instructor/gradescope.md](../docs/instructor/gradescope.md) (graded steps,
`Checks`, the submission zip). The worked example throughout is
`hwdesign-soln/labs/prng`.

## Decisions taken up front

* **Three graded stages**, 10 points each, mirroring prng: `pysim` → `pyeval` →
  `svsim`. Today's lab has two tests worth 10 + 20; the total stays 30.
  `pyeval` is new content — students measure the approximation error themselves
  and plot it against `nbits` before any hardware exists.
* **`tb_subc_divide.sv` is a student file** (`partial`). The lab's own stated
  objective is "implement a handshaking protocol between a testbench module and
  the DUT", and today the testbench hands that over complete. Students will
  write the drive loop: assert `invalid`, wait for `outvalid`, pulse `outready`.

## Where things stand

```
hwdesign-soln/labs/subc/         the solution, but in the pre-labkit shape
    subc_divide.py               complete; one "# TODO" comment, no markers
    subc_divide.sv               complete; no markers
    tb_subc_divide.sv            complete; hardcodes ../test_outputs/*.csv
    test_subc_divide.py          generates random vectors AND is student-facing
    submit.py                    scores and zips, standalone
    run.tcl                      xsim leftover
    autograder_config.xml        lists 2 files

hwdesign/labs/subc/              hand-maintained, drifts from the solution
    tb_subc_divide.sv  test_subc_divide.py  submit.py  run.tcl
    partial/subc_divide.py       redacted by hand
    partial/subc_divide.sv       redacted by hand
```

Everything above is replaced except the two `subc_divide.*` implementations,
which become the annotated solution.

## Target

```
hwdesign-soln/labs/subc/
    lab.toml
    subc_build.py         full     — the DAG, the spec constants, the grading
    subc_divide.py        partial  — the golden model
    subc_eval.py          partial  — NEW: the student's error analysis
    subc_divide.sv        partial  — the FSM
    tb_subc_divide.sv     partial  — the handshake drive loop
    autograder_config.xml private  — input to build_lab_autograder, not shipped

hwdesign/labs/subc/
    subc_build.py
    partial/{subc_divide.py, subc_eval.py, subc_divide.sv, tb_subc_divide.sv}
```

---

## Phase 1 — Move the lab's spec out of the student's files

The random test vectors are generated today inside `test_subc_divide.py`, which
students edit and submit. Per the instructor guide, the spec belongs to the lab:
a submission that fails to import must not take the grader down with it, and a
student must not be able to change what they are graded against.

1. In `subc_build.py`, pin the spec as module constants: `NTEST`, a `SEED` for a
   `np.random.default_rng`, the `b` range, the `nbits` range (4–16), and the
   tolerance and latency margins. Generate `(a, b, nbits)` from the seeded RNG.

   The seed is **not** needed to make the two stages agree — `svsim` reads the
   `vectors/tv_python.csv` that `pysim` wrote, inputs and expected `z` together,
   so whatever cases `pysim` chose are the cases the hardware is run against.
   It is there so that a score is reproducible: with a fresh draw every run, a
   design that is wrong on a rare input passes one invocation and fails the
   next, and neither you nor the student can reproduce what the other saw. It
   also means "case 37 disagrees" names the same case on your machine as on
   theirs.
2. Delete `test_subc_divide.py`, `submit.py` and `run.tcl` from the solution.
   Their jobs move into `subc_build.py` (vector generation, scoring) and
   `GradeReportStep` (the zip).

**Watch for:** today's `subc_divide` signature takes `nbits` per call and the
vectors vary it per row. Keep that — the per-row `nbits` is what the SV module's
runtime `nbits` port exists to exercise.

## Phase 2 — Write `subc_build.py`

Model it on `hwdesign-soln/labs/prng/prng_build.py` throughout. Four
`StudentSourceStep`s, three `GradedStep`s, one `GradeReportStep`.

```python
divide_src = StudentSourceStep(artifact="subc_divide_src", path=Path("subc_divide.py"))
eval_src   = StudentSourceStep(artifact="subc_eval_src",   path=Path("subc_eval.py"))
sv_src     = StudentSourceStep(artifact="subc_sv_src",     path=Path("subc_divide.sv"))
tb_src     = StudentSourceStep(artifact="subc_tb_src",     path=Path("tb_subc_divide.sv"))
```

Every graded stage gets `starts_from=[...]` naming its own sources, so an
untouched lab reports **not started** rather than a page of ✗ marks. This is not
optional — see "Tell each graded stage which files are its own" in the
instructor guide.

### `pysim` — 10 pts, the golden model

`outputs = {"py_vectors": Path("vectors/tv_python.csv")}`

Import `subc_divide` inside the `try` (a syntax error is a zero, not a halted
build), run it over the seeded vector set, and **always write the CSV** even
when nothing was produced, so `pyeval` and `svsim` have a file to read.

| pts | check | fails when |
|---|---|---|
| 3 | Produced a result for all `NTEST` cases | the function raised or returned `None` |
| 4 | `z/2**nbits` meets the error bound on every case | the algorithm is wrong |
| 3 | Your `z` actually depends on the inputs | the stub returns a constant |

#### The stub is checked for by name, not tuned around

`subc_divide.py`'s `BEGIN STUB` returns `np.uint32(0)`, and **`z = 0` satisfies
the error bound on every case where `a/b < 2**-nbits`.** At `nbits = 4` that is
one input pair in sixteen, so an untouched submission collects a fraction of the
4-point bound check for implementing nothing — the same shape of bug as prng's
18-out-of-20 empty run.

Test for it directly rather than drawing the vectors so it cannot happen:

```python
# The untouched template returns a constant.  Detected explicitly, because a
# constant z passes the error bound on any case whose true quotient is smaller
# than one ulp -- so the bound check alone pays for a stub.
is_constant = len(z) > 0 and int(np.unique(z).size) == 1

if is_constant:
    note = (f"every case returned z = {int(z[0])}, so your result does not depend "
            f"on a or b — open subc_divide.py and look for the TODO")
    checks.zero(4, "Your quotient meets the error bound", note)
    checks.zero(3, "Your z actually depends on the inputs", note)
else:
    ...          # the real bound check
```

Zeroing the bound check as well is the point: a constant `z` has not met the
bound, it has dodged the question. One note is attached to both so the student
is told once, plainly.

Two reasons to prefer this over adjusting the `a`/`b` ranges. It is legible —
someone reading the grader sees the degenerate case named and handled, rather
than inferring it from the bounds of a random draw. And it stays correct if the
ranges or `nbits` ever change, where a tuned draw silently stops protecting
anything.

**Pin it with a test.** In `tests/`, feed an all-zero `z` column through the
check function and assert the stage scores 0/10 — tier 0, no Vivado, runs in
milliseconds:

```python
def test_the_untouched_stub_scores_zero():
    z = np.zeros(NTEST, dtype=np.uint32)
    assert subc_build.check_vectors(a, b, nbits, z).result().points == 0.0
```

This is the check that is easiest to weaken by accident later, and the only one
whose failure mode is silent — it hands out points rather than raising.

### `pyeval` — 10 pts, measuring before building

New file `subc_eval.py`. Students write:

* `quant_error(a, b, z, nbits)` — the signed error `a/b - z/2**nbits`
* `max_error_by_nbits(df)` — the worst error at each `nbits` present
* `plot_error(...)` — saves `results/subc_error.png`, error vs. `nbits` on a log
  axis against the `2**-nbits` bound

Split exactly as prng does — *can you measure it* is a different question from
*is the design any good*:

| pts | check |
|---|---|
| 3 | Your `quant_error` matches the true value (tolerance `1e-12`) |
| 3 | Your per-`nbits` maxima are right |
| 2 | The error is one-sided and within `2**-nbits` — the bound actually holds |
| 2 | You produced a figure (existence only) |

Plot the values the *student* computed, not recomputed ones, so a wrong
measurement is visible. `unlink(missing_ok=True)` the figure first so a stale
PNG cannot earn the point, and write a placeholder if none was drawn —
`GradeReportStep` fails on a missing bundled file.

**Note the labkit trap:** prng needed `allow_shared` for two matplotlib lines
that appeared both in a solution block and in a shipped-whole placeholder. Write
the placeholder here with `plt.figure(...)`, not `plt.subplots(...)`, and keep
the solution's plotting call distinct, so `allow_shared` stays empty.

### `svsim` — 10 pts, the hardware

`consumes = ["subc_sv_src", "subc_tb_src", "py_vectors"]`

Run `waveflow.scripts.sv_sim.run_sv_sim` **inside `evaluate()`**, not as a
separate DAG node: as its own node a compile error raises, halts the build, and
leaves the student with a traceback and no submission. Inside, a compile error
is a scored zero with the tool output as feedback.

```python
run_sv_sim([root / "subc_divide.sv"], root / "tb_subc_divide.sv",
           sim_dir=root / "sim", plusargs={"vecdir": root / "vectors"},
           capture_output=True)
```

| pts | check |
|---|---|
| 6 | `z` from the simulation equals your Python `z`, case for case (`Checks.fraction`, first mismatch named) |
| 4 | Each case completes within `nbits + LATENCY_MARGIN` cycles |

Apply the same consistency floor prng needed: **two untouched stubs agree
perfectly.** If the Python `z` column is constant, the agreement check scores
zero with "fix `subc_divide.py` first" rather than paying full marks for two
implementations of nothing.

### `submit`

```python
GradeReportStep(name="submit", graded=[pysim, pyeval, svsim],
                bundle=[Path("subc_divide.py"), Path("subc_eval.py"),
                        Path("subc_divide.sv"), Path("tb_subc_divide.sv"),
                        Path("vectors/tv_python.csv"), Path("vectors/tv_sv.csv"),
                        Path("results/subc_error.png")])
```

`vectors/tv_sv.csv` only belongs in the bundle if it **always** exists — a
student whose simulation never ran must still get a zip. Have `svsim` write an
empty CSV on the failure path, as `pysim` does; the SV vectors are worth having
for a human reader.

## Phase 3 — Rework the testbench

`tb_subc_divide.sv` needs three changes before it can be annotated:

1. **Plusargs, not `../`.** It currently hardcodes
   `"../test_outputs/tv_python.csv"`, which only works from inside the sim
   directory. Take `vecdir` as a plusarg with a sensible default, as
   `tb_prng.sv` does.
2. **A watchdog.** Spelled out below — it is the change that makes the other two
   safe.
3. **Mark the drive loop as the student's.** `BEGIN SOLUTION` around the
   `invalid` / `outvalid` / `outready` handshake sequence, with a `BEGIN TODO`
   explaining the protocol in the terms `docs/labs/subc/sv.md` already uses. The
   CSV reading, writing and summary stay outside the block, shipped as-is.

The cycle count the testbench records is what `svsim` grades on latency, so it
must be counted *outside* the solution block — otherwise a student who writes a
wrong drive loop gets a latency score that measures their own testbench.

### The watchdog

This lab has **two** unbounded waits, and both are reachable from the published
tree on day one:

```systemverilog
while (!outvalid) begin ... end     // never ends if the FSM never reaches DONE
wait (inready);                     // never returns if it never reaches IDLE
```

An unedited `subc_divide.sv` hits both — with the `always_ff` inside a solution
block, `state` never leaves its initial value and `inready`/`outvalid` may not
be driven at all. And a student who gets the `count_next == nbits` comparison
wrong hits the first one with a working-looking design. In every case the
symptom is a simulator that does not return, which is indistinguishable from a
simulator that is working hard. This is worse than prng, where only the sample
loop could run away.

Add a watchdog `initial` block, outside any solution marker, modelled on
`tb_prng.sv`:

```systemverilog
// A wrong loop bound or an FSM that never leaves IDLE makes this testbench
// wait forever, and a simulator that never returns looks exactly like one
// working hard.  The real run needs about N us, so this only fires when
// something is genuinely stuck.
initial begin
    #WATCHDOG_TIME;
    $display("FATAL: still running after ... of simulated time.");
    $display("       The testbench is waiting on inready or outvalid and neither");
    $display("       arrived.  Check that your FSM leaves RUN after nbits");
    $display("       iterations and returns to IDLE once outready is seen.");
    $fatal(1);
end
```

Three things to get right:

* **Set `WATCHDOG_TIME` from the measured solution runtime**, with a wide
  margin, not from a guess. `NTEST` cases at up to 16 iterations plus handshake
  overhead, times the clock period — take the number Phase 5 prints and give it
  an order of magnitude.
* **The message names the FSM, not the loop.** For prng the runaway was the
  student's own loop bound; here the usual cause is the DUT never asserting a
  handshake signal, so that is what the text should send them to look at.
* **`$fatal(1)` must surface as a scored zero.** `svsim` runs the simulator
  inside `evaluate()`, so confirm `run_sv_sim` turns the non-zero exit into an
  `SvSimError` and that the `checks.zero(...)` path attaches the tool output.
  Verify this in Phase 5 by running the published tree untouched — a hang there
  means the watchdog is not wired to the grade, and the student's build stops
  dead with no submission zip.

There is a cheaper second line of defence worth adding alongside it: bound the
wait loop by an iteration count as well as by time —
`while (!outvalid && cycle_count < MAX_CYCLES)` — and let the latency check
report the overrun as an ordinary failed case. The time-based watchdog then only
catches what that cannot, which is a DUT that never reaches `IDLE` at all.

## Phase 4 — Annotate, and write `lab.toml`

Markers per `docs/instructor/labs.md`. The `TODO` comment sits **outside**
`BEGIN SOLUTION`; it is harmless in the solution and cannot drift from the code
it describes.

**`subc_divide.py`** — this is the guide's own worked `BEGIN STUB` example.
Without the stub the student file is `def subc_divide(...):` with nothing after
the guard clauses, which imports but returns `None` and takes `pyeval` and
`svsim` down with it:

```python
    # TODO: Implement the conditional subtraction division algorithm
# BEGIN SOLUTION
    z = np.uint32(0)
    for _ in range(nbits):
        ...
    return z
# BEGIN STUB
#     return np.uint32(0)
# END SOLUTION
```

Also drop the unused `import matplotlib.pyplot as plt` at the top — plotting now
lives in `subc_eval.py`.

**`subc_divide.sv`** — the port list and the `typedef enum` stay (they are the
interface the testbench binds to). The solution block covers the `always_comb`
next-state logic and the `always_ff`. It likely needs a `BEGIN STUB` too: a
module with neither block still elaborates, but leaves `z`, `inready` and
`outvalid` undriven, and the testbench then hangs on `wait (inready)` — which
the Phase 3 watchdog turns into a legible failure rather than a hang, though a
stub driving them to constants is kinder. Settle it in Phase 5.

**`tb_subc_divide.sv`** — the drive loop, per Phase 3.

**`subc_eval.py`** — one solution block per function, each with a `BEGIN STUB`
returning a shape-correct zero so the module imports.

```toml
[lab]
name   = "subc"
public = "../../../hwdesign/labs/subc"

full    = ["subc_build.py"]
partial = ["subc_divide.py", "subc_eval.py", "subc_divide.sv", "tb_subc_divide.sv"]
private = ["autograder_config.xml"]
```

Check how prng classifies `autograder_config.xml` before copying this — it is
the input to `build_lab_autograder`, not a student file, so it must be listed
somewhere but must not be published.

## Phase 5 — Publish to a scratch tree and run it untouched

**Do not skip this.** It is the step that found three invisible bugs in prng,
where an empty submission scored 18/20.

```bash
cd hwdesign-soln
python -m hwdesign.labkit lint labs/subc
python -m hwdesign.labkit publish labs/subc --dry-run

cp -r labs/subc /tmp/soln/labs/subc
sed -i 's|public = .*|public = "/tmp/pub/labs/subc"|' /tmp/soln/labs/subc/lab.toml
python -m hwdesign.labkit publish /tmp/soln/labs/subc
cd /tmp/pub/labs/subc && python subc_build.py
```

The specific things to look at, all of which prng got wrong the first time:

* **The untouched score must be zero, and it must not crash.** Every point it
  does collect needs a reason. The known candidate — `z = 0` passing the error
  bound on small quotients — is now checked for explicitly in `pysim`, so this
  run is confirming that check fires, not discovering whether it is needed.
* **`svsim` must not pay for two stubs agreeing.**
* **The unedited SV must fail legibly, not hang.** Watch the wall clock. The
  watchdog should fire within seconds and the stage should report a scored zero
  with the simulator output attached — if instead the build sits there, or stops
  with a traceback and no zip, the watchdog is not wired to the grade.
* **Note the solution's real simulated runtime** while you are here; it is what
  sets `WATCHDOG_TIME`.

Then run the **solution** end to end from the private side. It must score 30/30.
If the rubric cannot be satisfied by the reference implementation, the rubric is
wrong.

## Phase 6 — Autograder

1. Update `autograder_config.xml` to the bundle's **base names** — the zip
   flattens paths: `subc_divide.py`, `subc_eval.py`, `subc_divide.sv`,
   `tb_subc_divide.sv`, `tv_python.csv`, `tv_sv.csv`, `subc_error.png`. Add the
   comment prng's config carries, noting the list must stay in step with the
   `GradeReportStep` bundle.
2. `cd labs/subc && build_lab_autograder` to regenerate `autograder_build/` and
   `autograder.zip`.
3. Re-upload under **Configure Autograder** on Gradescope, and test it with the
   zip the scratch run produced.

## Phase 7 — Documentation

Rewrite `hwdesign/docs/labs/subc/` against the prng pages, which are the model
for tone and structure.

| Page | Work |
|---|---|
| `index.md` | Rewrite the **Files** tree (no `submit.py`, no `test_subc_divide.py`, four files in `partial/`), add the "you do not need to copy anything by hand" section with real `STARTED` / `not started` output, and add the **Build steps** table. Keep the existing overview and objectives — they are good. |
| `theory.md` | Largely unchanged. **Remove the full Python implementation** from the middle of the page — it is now the answer to `pysim`, and it is currently printed verbatim. Replace it with the recurrence in prose plus the `a=3, b=10` worked table, which is what the theory actually needs. |
| `python.md` | Rewrite around `python subc_build.py --through pysim`. Drop `test_subc_divide.py` entirely. |
| `evaluate.md` | **New.** Why you measure the error before building hardware; what `subc_eval.py` asks for; the error-vs-`nbits` figure. Model on `docs/labs/prng/evaluate.md`. `nav_order: 3`. |
| `sv.md` | Replace the `sv_sim --source ...` command with `python subc_build.py --through svsim`. **Deletes the last two `xilinxutils` references in the lab docs** (see `plans/migration_tracker.md`). Keep the handshake and FSM sections — they are the best part of the current docs — and add a short section on the drive loop students now write in the testbench. |
| `submit.md` | Rewrite around `--grades` and the `submit` step. Model on `docs/labs/prng/submit.md`, including the warning that Gradescope reports the score inside the uploaded zip. |

Also: bump `nav_order` on `sv.md` (3→4) and `submit.md` (4→5) for the inserted
`evaluate.md`, and mark the `docs/labs/subc/sv.md` row **integrated** in
`plans/migration_tracker.md`.

`docs/labs/index.md` already describes subc accurately; no change needed.

## Phase 8 — Publish for real, and commit

```bash
cd hwdesign-soln
python -m hwdesign.labkit publish labs/subc
python -m hwdesign.labkit check  labs/subc     # exits 1 if the trees disagree
```

**`publish` writes files; it never deletes them,** and `check` only compares
files the solution declares — so it will not notice the leftovers. Remove these
from `hwdesign` by hand:

```bash
git rm labs/subc/submit.py labs/subc/run.tcl labs/subc/test_subc_divide.py \
       labs/subc/tb_subc_divide.sv
```

(`tb_subc_divide.sv` is deleted from the top level and reappears under
`partial/`.) Check for a stale `test_outputs/` directory too — the new build
writes `vectors/` and `results/`.

Then read the `hwdesign` diff by hand before pushing. It is the last human look
at what becomes public, and the one place a leaked solution block would still be
visible.

Commit the two repositories separately.

## Open questions to settle while building

1. **How much latency margin?** Today's testbench allows `nbits + 2`, and the
   reference FSM spends one cycle in `IDLE`, `nbits` in `RUN` and one in `DONE`.
   Confirm the reference's exact count and set the margin from it, so a correct
   design is not scraping the limit. Same measurement sets `MAX_CYCLES` for the
   bounded wait loop.
2. **What is `WATCHDOG_TIME`?** Phase 5 — take the solution's simulated runtime
   and give it an order of magnitude.
3. **Does an un-driven `subc_divide.sv` elaborate?** Decides whether the SV
   `BEGIN STUB` is needed. Answer it in Phase 5 rather than by reasoning.
4. **What else belongs in `tests/`?** The stub-scores-zero test is settled
   (Phase 2) and should be written alongside the grader, not after. Beyond it, a
   tier-0 test that imports `subc_build.py` and asserts the DAG's total is 30
   would be cheap. A check-the-published-tree test cannot run in CI because it
   needs both repositories.
