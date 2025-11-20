"""
xsim_vcd.py — Run Vivado simulation with VCD output

This script re-runs a Vivado HLS RTL simulation using `xsim` and generates a VCD (Value Change Dump) file
for waveform analysis. It is intended for use on Windows systems where Vivado is installed.

Usage (CLI):
First, run the RTL simulation in Vitis HLS to generate the necessary simulation files.
In that simulation ensure that you have selected `trace=all` in the simulation settings.
Then, run this script from the command line:
```bash
    python xsim_vcd.py --top <top_function> [--comp <component_name>] [--out <output_file>]
```

Arguments:
    --top    (required) Name of the top-level function to simulate
    --comp   (optional) Name of the HLS component directory (default: 'hls_component')
    --out    (optional) Output VCD filename (default: 'dump.vcd')

Example:
```bash
    python xsim_vcd.py --top add  --out wave.vcd
```

This will run the simulation for the top function `add` in the component directory `hls_component`
and output the VCD file as `vcd/wave.vcd`.
"""

import os
import sys
import shutil
import subprocess
import re
import argparse


def modify_tcl(tcl_path, tcl_vcd_path):
    with open(tcl_path, 'r') as f:
        lines = f.readlines()

    # Insert VCD commands before log_wave
    for i, line in enumerate(lines):
        if 'log_wave -r /' in line:
            lines = lines[:i] + ['open_vcd\n', 'log_vcd *\n'] + lines[i:]
            break

    # Replace final lines
    for i in range(len(lines)):
        if lines[i].strip() == 'run all' and i + 1 < len(lines) and lines[i + 1].strip() == 'quit':
            lines[i + 1] = 'close_vcd\nquit\n'
            break

    with open(tcl_vcd_path, 'w') as f:
        f.writelines(lines)

def create_vcd_batch(top_name, original_bat, new_bat):
    with open(original_bat, 'r') as f:
        for line in f:
            if 'xsim' in line:
                xsim_line = line.replace(f'{top_name}.tcl', f'{top_name}_vcd.tcl')
                break
        else:
            raise RuntimeError("No xsim line found in batch file.")

    with open(new_bat, 'w') as f:
        f.write('cd /d "%~dp0"\n')
        f.write(xsim_line)

def run_batch(batch_path):
    subprocess.run(batch_path, shell=True, check=True)

def copy_vcd(sim_dir, base_dir, component_path, output_vcd):
    src = os.path.join(sim_dir, 'dump.vcd')
    if not os.path.exists(src):
        print("⚠️ dump.vcd not found.")
        return

    vcd_dir = os.path.join(base_dir, 'vcd')
    os.makedirs(vcd_dir, exist_ok=True)

    dst = os.path.join(vcd_dir, output_vcd)
    shutil.copyfile(src, dst)
    print(f"✅ VCD copied to {dst}")

def parse_args():
    parser = argparse.ArgumentParser(description="Process VCD dump options.")

    parser.add_argument(
        "--comp",
        type=str,
        default="hls_component",
        help="Component name (default: hls_component)"
    )
    parser.add_argument(
        "--top",
        type=str,
        required=True,
        help="Top-level function name (required)"
    )
    parser.add_argument(
        "--out",
        type=str,
        default="dump.vcd",
        help="Output VCD filename (default: dump.vcd)"
    )
    return parser.parse_args()


def main():

    # Check if OS is Windows.  If not declare error and exit.
    if os.name != 'nt':
        print("❌ This script only works on Windows.  I will try to add a linux version later.")
        sys.exit(1)

    # Get arguments
    args = parse_args()
    component_name = args.comp
    top_name = args.top
    output_vcd = args.out

    # Get directory paths
    component_path = os.path.join(component_name, top_name)
    base_dir = os.getcwd()
    sim_dir = os.path.join(base_dir, component_path, 'hls', 'sim', 'verilog')


    tcl_path = os.path.join(sim_dir, f'{top_name}.tcl')
    tcl_vcd_path = os.path.join(sim_dir, f'{top_name}_vcd.tcl')
    bat_path = os.path.join(sim_dir, 'run_xsim.bat')
    bat_vcd_path = os.path.join(sim_dir, 'run_xsim_vcd.bat')

    if 1:
        if not os.path.exists(sim_dir):
            raise FileNotFoundError(f"Simulation directory not found: {sim_dir}")

        modify_tcl(tcl_path, tcl_vcd_path)
        create_vcd_batch(top_name, bat_path, bat_vcd_path)
        run_batch(bat_vcd_path)
        copy_vcd(sim_dir, base_dir, component_path, output_vcd)

if __name__ == "__main__":
    main()