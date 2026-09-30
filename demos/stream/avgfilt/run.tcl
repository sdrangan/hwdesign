# Vitis HLS script for the avgfilt demo -- written by hand, not generated.
#
# One stage per invocation, named by the AVGFILT_STAGE environment variable:
#
#   csim    compile tb_avgfilt.cpp against avgfilt.cpp and run it
#   csynth  synthesize avgfilt() to RTL
#   cosim   re-run the same testbench against the synthesized RTL
#
# avgfilt_build.py runs these for you, one at a time, and compares what each
# produced against the Python model before starting the next.  The stages
# share one project, so `csim` -- the first -- is the only one that resets
# it; the later stages re-open what it built.
#
# You can also run a stage by hand, from this directory, once the build's
# `pysim` step has written vectors/tv_python.csv:
#
#   AVGFILT_STAGE=csim vitis-run --mode hls --tcl run.tcl            (bash)
#   $env:AVGFILT_STAGE="csim"; vitis-run --mode hls --tcl run.tcl    (PowerShell)

set script_dir [file dirname [file normalize [info script]]]

proc env_or {name default} {
    if {[info exists ::env($name)]} {
        return $::env($name)
    }
    return $default
}

set stage      [env_or AVGFILT_STAGE         "csim"]
set clk_period [env_or AVGFILT_CLK_PERIOD_NS 10]
# Which signals co-simulation records: `port` is the IP's ports -- the two
# AXI4-Stream interfaces -- which is what the timing diagram shows.  The
# VCD step replays whatever is recorded here, so `none` leaves it nothing.
set trace      [env_or AVGFILT_TRACE_LEVEL   "port"]
# The FPGA on the Pynq-Z2 board.  Nothing in this demo is deployed, but
# synthesis needs a part to target.
set part       [env_or AVGFILT_PART          "xc7z020clg400-1"]

if {$stage ni {csim csynth cosim}} {
    puts "AVGFILT_ERROR: unknown stage '$stage' (expected csim, csynth or cosim)."
    exit 1
}

if {$stage eq "csim"} {
    open_project -reset avgfilt_proj
} else {
    open_project avgfilt_proj
}

set_top avgfilt
add_files avgfilt.cpp
add_files -tb tb_avgfilt.cpp

if {$stage eq "csim"} {
    open_solution -reset "solution1"
} else {
    open_solution "solution1"
}
set_part $part
create_clock -period $clk_period

# The testbench reads the golden model's vectors and writes what the kernel
# returned.  Absolute paths, because co-simulation runs the testbench from
# inside avgfilt_proj/solution1/sim/, not from here.
set vec_dir  [file join $script_dir vectors]
set in_path  [file join $vec_dir tv_python.csv]
set out_path [file join $vec_dir tv_$stage.csv]

switch -- $stage {
    csim {
        if {[catch {csim_design -argv "$in_path $out_path"} res]} {
            puts "AVGFILT_ERROR: C simulation failed."
            puts $res
            exit 1
        }
    }
    csynth {
        if {[catch {csynth_design} res]} {
            puts "AVGFILT_ERROR: C synthesis failed."
            puts $res
            exit 1
        }
    }
    cosim {
        if {[catch {cosim_design -argv "$in_path $out_path" -trace_level $trace} res]} {
            puts "AVGFILT_ERROR: RTL co-simulation failed."
            puts $res
            exit 1
        }
    }
}

puts "AVGFILT_SUCCESS: stage '$stage' completed."
exit 0
