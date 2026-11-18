"""Write xbar_zynq7020_100mhz.csv from waveflow's crossbar sweep.

The area in this demo is measured once, beforehand, by waveflow's
examples/xbar_profile (out-of-context synthesis, place and route: ~4 min a
configuration, 20 configurations).  In the waveflow repo:

    python -m examples.xbar_profile.xbar_profile_sweep --part xc7z020clg400-1 --clk-mhz 100
    python -m examples.xbar_profile.xbar_profile_table --part xc7z020clg400-1 --clk-mhz 100

The table step writes results/7z020_xbar_100mhz/xbar_profile.json; this script
turns it into the CSV the demo reads:

    python xbar_import.py <waveflow>/examples/xbar_profile/results/7z020_xbar_100mhz/xbar_profile.json
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "xbar_zynq7020_100mhz.csv"

AREA = ("lut", "ff", "bram", "lutram", "srl", "dsp", "wns_ns", "met")
LATENCY = ("w1", "r1", "w16", "r16", "par_w16", "par_r16", "same_w16", "same_r16")


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("profile_json", type=Path, help="xbar_profile.json from the waveflow sweep")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    rows = json.loads(args.profile_json.read_text(encoding="utf-8"))
    rows.sort(key=lambda r: (r["dw"], r["shape"], r["mode"]))
    with args.out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["shape", "dw", "mode", *AREA, *LATENCY])
        for r in rows:
            if not r.get("routed"):
                raise SystemExit(f"{r['shape']} {r['mode']} d{r['dw']} was not placed and routed")
            area = ["" if r.get(k) is None else
                    (f"{r[k]:.3f}" if k == "wns_ns" else r[k]) for k in AREA]
            w.writerow([r["shape"], r["dw"], r["mode"], *area,
                        *("" if r["latency"].get(k) is None else r["latency"][k] for k in LATENCY)])
    print(f"{len(rows)} configuration(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
