# Vitis HLS script for the poly demo -- written by hand, not generated.
#
# One stage per invocation, named by the POLY_STAGE environment variable:
#
#   csim    compile tb_poly.cpp against poly.cpp and run it
#   csynth  synthesize poly() to RTL
#   cosim   re-run the same testbench against the synthesized RTL
#
# poly_build.py runs these for you, one at a time, and compares what each
# produced against the Python model before starting the next.  The stages
# share one project, so `csim` -- the first -- is the only one that resets
# it; the later stages re-open what it built.
#
# You can also run a stage by hand, from this directory, once the build's
# `gen_include` and `pysim` steps have run:
#
#   POLY_STAGE=csim vitis-run --mode hls --tcl run.tcl            (bash)
#   $env:POLY_STAGE="csim"; vitis-run --mode hls --tcl run.tcl    (PowerShell)

set script_dir [file dirname [file normalize [info script]]]

proc env_or {name default} {
    if {[info exists ::env($name)]} {
        return $::env($name)
    }
    return $default
}

set stage      [env_or POLY_STAGE         "csim"]
# Which version of the kernel to build -- each defines the same poly():
#   poly32   poly32.cpp, everything written out, for a 32-bit stream
#   poly64   poly64.cpp, everything written out, for a 64-bit stream
#   general  poly.cpp, any width, with the generated headers
set kernel     [env_or POLY_KERNEL        "general"]
# The stream word width: 32 (one float sample per word) or 64 (two).  The
# kernel and the testbench are both compiled with it.
set word_bw    [env_or POLY_WORD_BW       32]
set clk_period [env_or POLY_CLK_PERIOD_NS 10]
# Which signals co-simulation records: `port` is the IP's ports, which is
# what the timing diagram shows.
set trace      [env_or POLY_TRACE_LEVEL   "port"]
# The FPGA on the Pynq-Z2 board.  Nothing in this demo is deployed, but
# synthesis needs a part to target.
set part       [env_or POLY_PART          "xc7z020clg400-1"]

if {$stage ni {csim csynth cosim}} {
    puts "POLY_ERROR: unknown stage '$stage' (expected csim, csynth or cosim)."
    exit 1
}
switch -- $kernel {
    poly32  { set kernel_file poly32.cpp }
    poly64  { set kernel_file poly64.cpp }
    general { set kernel_file poly.cpp }
    default {
        puts "POLY_ERROR: unknown kernel '$kernel' (expected poly32, poly64 or general)."
        exit 1
    }
}

if {$stage eq "csim"} {
    open_project -reset poly_proj
} else {
    open_project poly_proj
}

set cflags "-DWORD_BW=$word_bw"
set_top poly
add_files $kernel_file -cflags $cflags
add_files -tb tb_poly.cpp -cflags $cflags
# Defines the one non-inline symbol in the generated stream utilities.
add_files -tb include/streamutils.cpp

if {$stage eq "csim"} {
    open_solution -reset "solution1"
} else {
    open_solution "solution1"
}
set_part $part
create_clock -period $clk_period

# The testbench reads the golden model's vectors from one directory and
# writes what came back to another.  Absolute paths, because co-simulation
# runs the testbench from inside poly_proj/solution1/sim/, not from here.
set in_dir  [file join $script_dir vectors]
set out_dir [file join $script_dir results $stage]
file mkdir $out_dir

switch -- $stage {
    csim {
        if {[catch {csim_design -argv "$in_dir $out_dir"} res]} {
            puts "POLY_ERROR: C simulation failed."
            puts $res
            exit 1
        }
    }
    csynth {
        if {[catch {csynth_design} res]} {
            puts "POLY_ERROR: C synthesis failed."
            puts $res
            exit 1
        }
    }
    cosim {
        if {[catch {cosim_design -argv "$in_dir $out_dir" -trace_level $trace} res]} {
            puts "POLY_ERROR: RTL co-simulation failed."
            puts $res
            exit 1
        }
    }
}

puts "POLY_SUCCESS: stage '$stage' completed ($kernel_file, WORD_BW=$word_bw)."
exit 0
