#!/usr/bin/env python3
import argparse
import subprocess
import os
import sys
import shutil
from pathlib import Path

def run(cmd, cwd=None):
    print(f"\n>>> {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd)
    if result.returncode != 0:
        print(f"Error: command failed\n{cmd}")
        sys.exit(result.returncode)

def main():
    parser = argparse.ArgumentParser(description="Simple Vivado SystemVerilog simulator wrapper")

    parser.add_argument("--source", "-s", nargs="+", required=True,
                        help="SystemVerilog source files (one or more)")
    parser.add_argument("--tb", required=True,
                        help="Testbench file (single file)")
    parser.add_argument("--top", default=None,
                        help="Optional top module name (defaults to testbench filename without extension)")
    parser.add_argument("--sim", default="sim",
                        help="Simulation directory (default: sim)")
    parser.add_argument("--keep", action="store_true",
                        help="Keep existing sim directory (default: False, deletes before running)")

    args = parser.parse_args()

    # Determine top module name
    top = args.top
    if top is None:
        top = os.path.splitext(os.path.basename(args.tb))[0]

    # Create simulation directory
    sim_dir = Path(args.sim)
    
    # Delete sim directory if keep is not set
    if not args.keep and sim_dir.exists():
        shutil.rmtree(sim_dir)
    
    # Make the sim directory
    sim_dir.mkdir(parents=True, exist_ok=True)

    # Create logs directory inside sim/
    logs_dir = sim_dir / "logs"
    logs_dir.mkdir(exist_ok=True)

    # Build commands
    vlog_cmd = "xvlog -sv " + " ".join(
        [str(Path("..") / f) for f in (args.source + [args.tb])]
    )

    elab_cmd = (
        f"xelab {top} -s {top}_sim -debug typical "
        f"-log logs/xelab.log"
    )

    sim_cmd = (
        f"xsim {top}_sim -t ../run.tcl "
        f"-log logs/xsim.log"
    )

    # Run commands inside sim directory
    run(vlog_cmd, cwd=sim_dir)
    run(elab_cmd, cwd=sim_dir)
    run(sim_cmd, cwd=sim_dir)

if __name__ == "__main__":
    main()