"""Measure each job's phases from the XSI waveform, and draw them.

The traced XSI run dumps every signal in the top scope (``vcd_dumper_<top>.v``): the ports and
the strobes of every FIFO between the tasks.  This module samples them once per clock, just
before each rising edge -- when a handshake is decided -- and turns the beats into one row per
job:

    cmd        the HistCmd's first and last word accepted on s_cmd
    read       the first AR request, the first R beat, and the last R beat
    compute    the compute task's first sample read, and its last count written
    write      the first AW request, the last W beat, and the B response
    resp       the HistResp's first and last word on s_done

Cycles are 1-based from the end of reset: the same count the XSI bus models keep, so a
response's cycle here equals its cycle in ``vectors/s_done/cycles.bin``.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

#: The XSI clock: XsiSim drives a 10 ns period, rising edges at 5 ns + 10 ns * k.
PERIOD_PS = 10_000
FIRST_EDGE_PS = 5_000
RESET_CYCLES = 16          # XsiSim.reset() default


def _sample(tv: list[tuple[int, str]], times: np.ndarray) -> np.ndarray:
    """A signal's value at each of *times*, as integers (X/Z read as 0)."""
    t = np.array([a for a, _ in tv], dtype=np.int64)
    vals = []
    for _, s in tv:
        try:
            vals.append(int(s, 2))
        except ValueError:
            vals.append(0)
    idx = np.searchsorted(t, times, side="right") - 1
    return np.where(idx >= 0, np.asarray(vals, dtype=np.int64)[np.maximum(idx, 0)], 0)


def load_trace(vcd_path: Path, top: str, signals: list[str]) -> dict[str, np.ndarray]:
    """Each named top-scope signal, sampled once per cycle.  Index 0 is cycle 1."""
    from vcdvcd import VCDVCD

    full = {}
    v = VCDVCD(str(vcd_path), only_sigs=True)
    for s in signals:
        hits = [n for n in v.signals if n == f"{top}.{s}" or n.startswith(f"{top}.{s}[")]
        if not hits:
            raise RuntimeError(f"no signal {top}.{s} in {vcd_path}")
        full[s] = hits[0]
    v = VCDVCD(str(vcd_path), signals=list(full.values()), store_tvs=True)
    end = max(tv[-1][0] for tv in (v[n].tv for n in full.values()))
    first = FIRST_EDGE_PS + RESET_CYCLES * PERIOD_PS
    times = np.arange(first, end + PERIOD_PS, PERIOD_PS) - 1_000     # 1 ns before each edge
    return {s: _sample(v[n].tv, times) for s, n in full.items()}


#: The beats that are measured: name -> (valid, ready) or a single strobe.
BEATS = {
    "cmd":     ("s_cmd_TVALID", "s_cmd_TREADY"),
    "ar":      ("m_axi_gmem0_ARVALID", "m_axi_gmem0_ARREADY"),
    "r":       ("m_axi_gmem0_RVALID", "m_axi_gmem0_RREADY"),
    "cmp_in":  ("hist_compute_U0_rd_data_read",),
    "cmp_out": ("hist_compute_U0_wr_data_write",),
    "aw":      ("m_axi_gmem1_AWVALID", "m_axi_gmem1_AWREADY"),
    "w":       ("m_axi_gmem1_WVALID", "m_axi_gmem1_WREADY"),
    "b":       ("m_axi_gmem1_BVALID", "m_axi_gmem1_BREADY"),
    "resp":    ("s_done_TVALID", "s_done_TREADY"),
}
EXTRA = ["m_axi_gmem0_ARLEN", "m_axi_gmem1_AWLEN"]


def beat_cycles(trace: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """The 1-based cycles on which each kind of beat happened."""
    out = {}
    for name, sigs in BEATS.items():
        hit = np.ones_like(trace[sigs[0]], dtype=bool)
        for s in sigs:
            hit &= trace[s] != 0
        out[name] = np.flatnonzero(hit) + 1
    return out


def _split(cycles: np.ndarray, sizes: list[int]) -> list[np.ndarray]:
    """Consecutive runs of *sizes* beats: one per job, in order."""
    out, k = [], 0
    for n in sizes:
        out.append(cycles[k:k + n])
        k += n
    return out


def _requests(cycles: np.ndarray, lens: np.ndarray, sizes: list[int]) -> list[np.ndarray]:
    """AR/AW requests per job: a request of ARLEN+1 beats belongs to the job its beats do."""
    out, k = [], 0
    beats = lens + 1
    for n in sizes:
        got, start = 0, k
        while got < n and k < len(cycles):
            got += int(beats[k])
            k += 1
        out.append(cycles[start:k])
    return out


def job_table(trace: dict[str, np.ndarray], jobs, nbins: int, cmd_words: int,
              resp_words: int) -> list[dict]:
    """One row per job: the cycle each phase began and ended."""
    b = beat_cycles(trace)
    nread = [j.n if j.ok else 0 for j in jobs]
    nwrite = [nbins if j.ok else 0 for j in jobs]
    cmd = _split(b["cmd"], [cmd_words] * len(jobs))
    resp = _split(b["resp"], [resp_words] * len(jobs))
    r, w = _split(b["r"], nread), _split(b["w"], nwrite)
    cin, cout = _split(b["cmp_in"], nread), _split(b["cmp_out"], nwrite)
    ar = _requests(b["ar"], trace["m_axi_gmem0_ARLEN"][b["ar"] - 1], nread)
    aw = _requests(b["aw"], trace["m_axi_gmem1_AWLEN"][b["aw"] - 1], nwrite)
    bresp = _split(b["b"], [len(x) for x in aw])

    def first(x):
        return int(x[0]) if len(x) else None

    def last(x):
        return int(x[-1]) if len(x) else None

    rows = []
    for k, j in enumerate(jobs):
        rows.append({
            "job_id": j.job_id, "n": j.n, "status": j.status().name,
            "cmd_first": first(cmd[k]), "cmd_last": last(cmd[k]),
            "rd_req": first(ar[k]), "rd_bursts": len(ar[k]),
            "rd_first": first(r[k]), "rd_last": last(r[k]),
            "cmp_first": first(cin[k]), "cmp_last": last(cout[k]),
            "wr_req": first(aw[k]), "wr_bursts": len(aw[k]),
            "wr_first": first(w[k]), "wr_last": last(w[k]), "wr_bresp": last(bresp[k]),
            "resp_first": first(resp[k]), "resp_last": last(resp[k]),
        })
    for row in rows:
        c = row["cmd_last"]
        row["latency_L"] = row["rd_first"] - c if row["rd_first"] else None
        row["cmd_to_resp"] = row["resp_last"] - c if row["resp_last"] else None
    return rows


def format_table(rows: list[dict]) -> str:
    cols = [("job", "job_id"), ("n", "n"), ("status", "status"), ("cmd", "cmd_last"),
            ("AR", "rd_req"), ("R first", "rd_first"), ("R last", "rd_last"),
            ("cmp first", "cmp_first"), ("cmp last", "cmp_last"), ("AW", "wr_req"),
            ("W first", "wr_first"), ("W last", "wr_last"), ("B", "wr_bresp"),
            ("resp", "resp_last"), ("L", "latency_L"), ("cmd->resp", "cmd_to_resp")]
    lines = ["| " + " | ".join(h for h, _ in cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        lines.append("| " + " | ".join("-" if r[k] is None else str(r[k]) for _, k in cols) + " |")
    return "\n".join(lines)


def format_relative(rows: list[dict]) -> str:
    """The same events, in cycles after the command's last word was accepted."""
    cols = [("AR", "rd_req"), ("first sample (L)", "rd_first"), ("last sample", "rd_last"),
            ("compute first", "cmp_first"), ("last count", "cmp_last"), ("AW", "wr_req"),
            ("last W", "wr_last"), ("last B", "wr_bresp"), ("response", "resp_last")]
    lines = ["| job | n | " + " | ".join(h for h, _ in cols) + " |", "|" + "---|" * (len(cols) + 2)]
    for r in rows:
        c = r["cmd_last"]
        cells = ["-" if r[k] is None else f"+{r[k] - c}" for _, k in cols]
        lines.append(f"| {r['job_id']} | {r['n']} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


# ------------------------------------------------------------------- figure --
#: Row label, start key, end key.  A command is drawn at its LAST word: the s_cmd port has a
#: two-word register slice, which accepts the start of the next command while the control task
#: is still busy, so a command's first word says nothing about when its job began.
PHASES = [
    ("command", "cmd_last", "cmd_last"),
    ("read (m_rd)", "rd_req", "rd_last"),
    ("compute", "cmp_first", "cmp_last"),
    ("write (m_wr)", "wr_req", "wr_bresp"),
    ("response", "resp_first", "resp_last"),
]
JOB_COLORS = ["#2F6FA8", "#B4530F", "#00857C", "#8E8E8E", "#7A4FA3", "#A8862F"]


def _draw_jobs(ax, rows: list[dict], xlim: tuple[int, int], label_rows: bool) -> None:
    """A row per phase, a colour per job, on *ax* over cycles *xlim*."""
    nrow = len(PHASES)
    min_w = (xlim[1] - xlim[0]) * 0.006           # so a one-cycle event still shows
    for k, r in enumerate(rows):
        color = JOB_COLORS[k % len(JOB_COLORS)]
        for i, (_, a, b) in enumerate(PHASES):
            if r[a] is None or r[b] is None:
                continue
            y = nrow - 1 - i
            width = max(r[b] - r[a] + 1, min_w)
            left = r[b] + 1 - width if a == b else r[a]
            ax.barh(y, width, left=left, height=0.62, color=color, edgecolor="white",
                    linewidth=0.6)
            if i == 2 and label_rows:
                ax.text(r[a] + width / 2, y, f"job {r['job_id']}\nn={r['n']}", ha="center",
                        va="center", fontsize=8.5, color="white")
    ax.set_yticks(range(nrow))
    ax.set_yticklabels([p[0] for p in PHASES][::-1])
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color="#DDDDDD", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_xlim(*xlim)
    ax.set_facecolor("white")


def draw_timeline(rows: list[dict], png: Path, title: str) -> Path:
    """Top: every job.  Bottom: the first job alone, and the start of the second."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7.2))
    fig.patch.set_facecolor("white")

    end = max(r["resp_last"] for r in rows)
    _draw_jobs(ax1, rows, (0, end + 60), label_rows=True)
    for k, r in enumerate(rows):
        if r["status"] != "OK":
            color = JOB_COLORS[k % len(JOB_COLORS)]
            ax1.annotate(f"job {r['job_id']}: refused (n={r['n']})", xy=(r["resp_last"], 0),
                         xytext=(r["resp_last"] + 40, 0.55), fontsize=8.5, color=color,
                         arrowprops={"arrowstyle": "-", "color": color})
    ax1.set_title(title, loc="left", fontsize=12)

    j1, j2 = rows[0], rows[1]
    hi = j1["wr_bresp"] + 40
    _draw_jobs(ax2, rows[:2], (0, hi), label_rows=False)
    y_cmp, y_rd, y_cmd = 2, 3, 4
    ax2.text(j1["cmp_first"] + 8, y_cmp, f"job 1 (n={j1['n']})", va="center", fontsize=9,
             color="white")
    ax2.text(j2["rd_req"] + 4, y_rd, "job 2", va="center", fontsize=9, color="white")
    ax2.text(j2["cmd_last"] + 4, y_cmd, f"commands in: job 1 at {j1['cmd_last']}, job 2 at "
             f"{j2['cmd_last']} (queued behind job 1)", fontsize=8.5, color="#333333",
             va="center")
    ax2.text(j1["resp_first"] - 3, 0, f"response: {j1['resp_last']}", fontsize=8.5,
             color="#333333", va="center", ha="right")
    notes = [  # (x, y, text, ha): under each bar, in the gap to the next row
        (j1["rd_first"], y_rd, f"first sample: {j1['rd_first']}  (L = {j1['latency_L']})", "left"),
        (j1["rd_last"], y_rd, f"last sample: {j1['rd_last']}", "right"),
        (j1["cmp_last"], y_cmp, f"last count: {j1['cmp_last']}", "right"),
        (j1["wr_req"], 1, f"first AW: {j1['wr_req']}", "right"),
        (j1["wr_bresp"], 1, f"last B: {j1['wr_bresp']}", "left"),
    ]
    for x, y, text, ha in notes:
        ax2.text(x, y - 0.35, text, fontsize=8.5, color="#333333", va="top", ha=ha)
    ax2.set_xlabel("clock cycle (100 MHz), from the end of reset")
    ax2.set_title(f"zoom: job 1, and job 2's read starting as job 1's compute ends",
                  loc="left", fontsize=11)
    fig.tight_layout()
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, dpi=200, metadata={"Software": None, "Date": None})
    plt.close(fig)
    return png


def measure(vcd_path: Path, top: str, jobs, nbins: int, cmd_words: int, resp_words: int,
            out_dir: Path, name: str, figure: bool) -> dict:
    """timing_<name>.json and .md into *out_dir*; with *figure*, timeline.png too."""
    trace = load_trace(vcd_path, top, sorted({s for v in BEATS.values() for s in v} | set(EXTRA)))
    rows = job_table(trace, jobs, nbins, cmd_words, resp_words)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"timing_{name}.json").write_text(json.dumps(rows, indent=2) + "\n",
                                                 encoding="utf-8")
    table = (f"Absolute cycles ({name}):\n\n{format_table(rows)}\n\n"
             f"Cycles after each job's command ({name}):\n\n{format_relative(rows)}")
    (out_dir / f"timing_{name}.md").write_text(table + "\n", encoding="utf-8")
    png = None
    if figure:
        png = draw_timeline(rows, out_dir / "timeline.png",
                            f"{top}: each job's phases, measured from the RTL (XSI)")
    return {"rows": rows, "table": table, "png": png}
