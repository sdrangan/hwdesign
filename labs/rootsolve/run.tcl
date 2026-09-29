# Vitis HLS script for the rootsolve lab.
#
# One stage per invocation, named by the ROOTSOLVE_STAGE environment variable:
#
#   csim    compile tb_fsolve.cpp against fsolve.cpp and run it
#   csynth  synthesize fsolve() to RTL
#   cosim   re-run the same testbench against the synthesized RTL
#
# rootsolve_build.py runs these for you, one at a time, and checks what each
# produced before starting the next.  The stages share one project, so
# `csim` -- the first -- is the only one that resets it; the later stages
# re-open what it built.
#
# You can also run a stage by hand, from this directory:
#
#   ROOTSOLVE_STAGE=csim vitis-run --mode hls --tcl run.tcl           (bash)
#   $env:ROOTSOLVE_STAGE="csim"; vitis-run --mode hls --tcl run.tcl   (PowerShell)
#
# On the older 2023.2 tools the command is `vitis_hls -f run.tcl`.

proc env_or {name default} {
    if {[info exists ::env($name)]} {
        return $::env($name)
    }
    return $default
}

set stage      [env_or ROOTSOLVE_STAGE         "csim"]
set clk_period [env_or ROOTSOLVE_CLK_PERIOD_NS 10]
# The FPGA on the Pynq-Z2 board.  Nothing in this lab is deployed, but
# synthesis needs a part to target.
set part       [env_or ROOTSOLVE_PART          "xc7z020clg400-1"]

if {$stage ni {csim csynth cosim}} {
    puts "ROOTSOLVE_ERROR: unknown stage '$stage' (expected csim, csynth or cosim)."
    exit 1
}

if {$stage eq "csim"} {
    open_project -reset fsolve_proj
} else {
    open_project fsolve_proj
}

set_top fsolve
add_files fsolve.cpp
add_files -tb tb_fsolve.cpp

if {$stage eq "csim"} {
    open_solution -reset "solution1"
} else {
    open_solution "solution1"
}
set_part $part
create_clock -period $clk_period

# The testbench's one argument names the file it writes: vectors/tv_csim.csv
# or vectors/tv_cosim.csv.
switch -- $stage {
    csim {
        if {[catch {csim_design -argv "csim"} res]} {
            puts "ROOTSOLVE_ERROR: C simulation failed."
            puts $res
            exit 1
        }
    }
    csynth {
        if {[catch {csynth_design} res]} {
            puts "ROOTSOLVE_ERROR: C synthesis failed."
            puts $res
            exit 1
        }
    }
    cosim {
        if {[catch {cosim_design -argv "cosim"} res]} {
            puts "ROOTSOLVE_ERROR: RTL co-simulation failed."
            puts $res
            exit 1
        }
    }
}

puts "ROOTSOLVE_SUCCESS: stage '$stage' completed."
exit 0
