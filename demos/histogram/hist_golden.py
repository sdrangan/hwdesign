"""The test jobs, the memory they run in, and the NumPy golden they are checked against.

Every design runs the same jobs over the same memory image and is checked
against the same golden.  The memory is one array of 32-bit words: the
samples of every job, then a block of NBINS counts per job, pre-filled with a sentinel so a
count the kernel never wrote is caught, not read as zero.

    words [0, SAMPLES_END)                 samples, job after job
    words [COUNTS_BASE, ...)               NBINS counts per job, sentinel-filled
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from hist_schema import MEM_DW, HistCmd, HistResp, HistStatus

#: Must match hist_types.h.
NBINS = 32
MAX_N = 65535

MEM_WORDS = 8192
COUNTS_BASE = 6144
SENTINEL = 0xDEADBEEF


@dataclass
class Job:
    job_id: int
    n: int
    shift: int
    data_addr: int
    cnt_addr: int
    x: np.ndarray = field(repr=False)     # the samples (empty for a refused job)

    @property
    def ok(self) -> bool:
        return self.n <= MAX_N

    def counts(self) -> np.ndarray:
        """The golden: how many samples land in each bin."""
        bins = np.minimum(self.x.astype(np.int64) >> self.shift, NBINS - 1)
        return np.bincount(bins, minlength=NBINS).astype(np.uint32)

    def cmd(self) -> HistCmd:
        return HistCmd(job_id=self.job_id, data_addr=self.data_addr, n=self.n,
                       cnt_addr=self.cnt_addr, shift=self.shift)

    def status(self) -> HistStatus:
        return HistStatus.OK if self.ok else HistStatus.N_TOO_LARGE


def test_jobs(seed: int = 7) -> list[Job]:
    """Five jobs back to back: three sizes, one that saturates the top bin, one refused."""
    rng = np.random.default_rng(seed)
    specs = [  # (n, shift, the samples)
        (256, 11, lambda n: rng.integers(0, 1 << 16, n)),                      # uniform
        (1024, 11, lambda n: np.clip(rng.normal(30000, 9000, n), 0, 65535)),   # a bell
        (700, 10, lambda n: rng.integers(0, 1 << 16, n)),                      # half saturate
        (70000, 11, lambda n: np.zeros(0)),                                    # n > MAX_N
        (1024, 11, lambda n: np.minimum(rng.exponential(12000, n), 65535)),    # a decay
    ]
    jobs, addr = [], 0
    for k, (n, shift, gen) in enumerate(specs):
        x = gen(n).astype(np.uint32)
        jobs.append(Job(job_id=k + 1, n=n, shift=shift, data_addr=addr,
                        cnt_addr=COUNTS_BASE + NBINS * k, x=x))
        addr += len(x)
    assert addr <= COUNTS_BASE and COUNTS_BASE + NBINS * len(jobs) <= MEM_WORDS
    return jobs


def memory_image(jobs: list[Job]) -> np.ndarray:
    mem = np.zeros(MEM_WORDS, dtype=np.uint32)
    for j in jobs:
        mem[j.data_addr:j.data_addr + len(j.x)] = j.x
        mem[j.cnt_addr:j.cnt_addr + NBINS] = SENTINEL
    return mem


def cmd_bursts(jobs: list[Job]) -> list[np.ndarray]:
    """Each job's HistCmd, as the words that go on the command stream."""
    return [np.asarray(j.cmd().serialize(word_bw=MEM_DW), dtype=np.uint32) for j in jobs]


def cmd_words(jobs: list[Job]) -> np.ndarray:
    return np.concatenate(cmd_bursts(jobs))


def resp_nwords() -> int:
    return len(HistResp(job_id=0, status=HistStatus.OK).serialize(word_bw=MEM_DW))


def parse_responses(words: np.ndarray) -> list[tuple[int, int]]:
    k = resp_nwords()
    out = []
    for i in range(len(words) // k):
        r = HistResp().deserialize(np.asarray(words[i * k:(i + 1) * k]), word_bw=MEM_DW)
        out.append((int(r.job_id), int(r.status)))
    return out


def check(jobs: list[Job], mem_out: np.ndarray, resp_words: np.ndarray,
          by_id: bool = False) -> list[str]:
    """Every count, every untouched region and every response.  Returns the failures.

    *by_id*: match each response to its job by ``job_id``, in any order -- what a host that
    queues several jobs at once must do -- instead of requiring them in command order.  Each
    job must still get exactly one response, with its status."""
    fails = []
    for j in jobs:
        got = mem_out[j.cnt_addr:j.cnt_addr + NBINS]
        if j.ok:
            exp = j.counts()
            if not np.array_equal(got, exp):
                bad = np.flatnonzero(got != exp)
                fails.append(f"job {j.job_id}: {len(bad)} counts wrong, first bin {bad[0]}: "
                             f"got {got[bad[0]]:#x}, expected {exp[bad[0]]}")
            if int(exp.sum()) != j.n:
                fails.append(f"job {j.job_id}: golden counts sum to {exp.sum()}, not n={j.n}")
        elif not np.all(got == SENTINEL):
            fails.append(f"job {j.job_id}: refused, but its counts were written")
    if not np.array_equal(mem_out[:COUNTS_BASE], memory_image(jobs)[:COUNTS_BASE]):
        fails.append("the sample region changed")
    resps = parse_responses(resp_words)
    exp_resps = [(j.job_id, int(j.status())) for j in jobs]
    if len(resp_words) != len(jobs) * resp_nwords():
        fails.append(f"{len(resp_words)} response words, expected {len(jobs) * resp_nwords()} "
                     f"({len(jobs)} responses)")
    if by_id:
        seen: dict[int, list[int]] = {}
        for job_id, status in resps:
            seen.setdefault(job_id, []).append(status)
        for j in jobs:
            got_st = seen.pop(j.job_id, [])
            if got_st != [int(j.status())]:
                fails.append(f"job {j.job_id}: responses with status {got_st}, "
                             f"expected one with {int(j.status())}")
        if seen:
            fails.append(f"responses for unknown job ids {sorted(seen)}")
    elif resps != exp_resps:
        fails.append(f"responses {resps}, expected {exp_resps}")
    return fails


def write_raw(path: Path, words: np.ndarray) -> Path:
    """Raw little-endian uint32: what the C simulation testbench reads."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.asarray(words, dtype="<u4").tofile(path)
    return path


def read_raw(path: Path) -> np.ndarray:
    return np.fromfile(path, dtype="<u4")


def summary(jobs: list[Job]) -> str:
    rows = ["  job  n      shift  data_addr  cnt_addr  status"]
    for j in jobs:
        rows.append(f"  {j.job_id:<4} {j.n:<6} {j.shift:<6} {j.data_addr:<10} {j.cnt_addr:<9} "
                    f"{j.status().name}")
    return "\n".join(rows)
