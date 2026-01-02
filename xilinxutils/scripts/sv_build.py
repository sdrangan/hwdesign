#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path


# ------------------------------------------------------------
# Shared helper: run a shell command
# ------------------------------------------------------------
def run(cmd, cwd=None):
    print(f"\n>>> {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd)
    if result.returncode != 0:
        print(f"Error: command failed\n{cmd}")
        sys.exit(result.returncode)


# ------------------------------------------------------------
# Shared helper: ensure directory exists
# ------------------------------------------------------------
def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    return path


# ------------------------------------------------------------
# Synthesis entry point
# ------------------------------------------------------------
def run_synth():
    parser = argparse.ArgumentParser(description="Vivado synthesis wrapper")

    parser.add_argument("--source", "-s", nargs="+", required=True,
                        help="SystemVerilog/Verilog source files (one or more)")
    parser.add_argument("--top", required=True,
                        help="Top module name for synthesis")
    parser.add_argument("--part", default="xc7z020clg400-1",
                        help="FPGA part number (default: xc7z020clg400-1)")
    parser.add_argument("--out", default="synth",
                        help="Output directory for synthesis artifacts (default: synth)")

    args = parser.parse_args()

    out_dir = ensure_dir(Path(args.out))

    # Build TCL script
    tcl_lines = []

    # Read source files (relative paths from synth directory)
    for src in args.source:
        rel = Path("..") / src
        tcl_lines.append(f"read_verilog {rel.as_posix()}")

    # Synthesis command
    tcl_lines.append(f"synth_design -top {args.top} -part {args.part}")

    # Outputs
    tcl_lines.append("write_checkpoint -force synth.dcp")
    tcl_lines.append("write_verilog -force synth_netlist.v")
    tcl_lines.append("write_edif -force synth.edf")

    # Reports
    tcl_lines.append("report_utilization -file util.rpt")
    tcl_lines.append("report_timing_summary -file timing.rpt")

    tcl_lines.append("exit")

    # Write TCL file
    tcl_path = out_dir / "synth.tcl"
    tcl_path.write_text("\n".join(tcl_lines))

    # Run Vivado
    run("vivado -mode batch -source synth.tcl", cwd=out_dir)


# ------------------------------------------------------------
# Implementation entry point
# ------------------------------------------------------------
def run_impl():
    parser = argparse.ArgumentParser(description="Vivado implementation wrapper")

    parser.add_argument("--dcp", default="synth/synth.dcp",
                        help="Input synthesis checkpoint (synth.dcp)")
    parser.add_argument("--xdc", default="constraints.xdc",
                        help="Constraints file (XDC)")
    parser.add_argument("--out", default="impl",
                        help="Output directory for implementation artifacts (default: impl)")

    args = parser.parse_args()

    out_dir = ensure_dir(Path(args.out))

    # Build TCL script
    tcl_lines = []

    dcp_path = Path(args.dcp).resolve()
    xdc_path = Path(args.xdc).resolve()

    if not dcp_path.exists():
        print(f"ERROR: DCP file not found: {dcp_path}")
        sys.exit(1)

    if not xdc_path.exists():
        print(f"ERROR: XDC file not found: {xdc_path}")
        sys.exit(1)

    tcl_lines.append(f"open_checkpoint {dcp_path.as_posix()}")
    tcl_lines.append(f"read_xdc {xdc_path.as_posix()}")

    # Implementation steps
    tcl_lines.append("opt_design")
    tcl_lines.append("place_design")
    tcl_lines.append("route_design")

    # Reports
    tcl_lines.append("report_timing_summary -file timing.rpt")
    tcl_lines.append("report_utilization -file util.rpt")

    # Bitstream
    tcl_lines.append("write_bitstream -force design.bit")

    tcl_lines.append("exit")

    # Write TCL file
    tcl_path = out_dir / "impl.tcl"
    tcl_path.write_text("\n".join(tcl_lines))

    # Run Vivado
    run("vivado -mode batch -source impl.tcl", cwd=out_dir)


# ------------------------------------------------------------
# Optional: allow direct execution for debugging
# ------------------------------------------------------------
if __name__ == "__main__":
    print("This file provides two entry points:")
    print("  sv_synth → run_synth()")
    print("  sv_impl  → run_impl()")
    print("Use those commands instead of running this file directly.")