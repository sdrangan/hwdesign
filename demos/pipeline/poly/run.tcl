# Vitis HLS script for the pipelining demo -- written by hand, not generated.
#
# One stage per invocation, named by the POLY_STAGE environment variable:
#
#   csim    compile the testbench against the C++ kernel and run it
#   synth   synthesize each variant in POLY_VARIANTS, one project each
#   cosim   re-run the testbench against one synthesized variant, named by
#           POLY_VARIANT
#
# A variant is the same source, poly.cpp, built with different loop
# optimizations.  Its spec is name:pipeline:unroll:partition, for example
#
#   nopipe:0:1:0    the loop as written, with pipelining switched off
#   pipe:1:1:0      pipelined, II = 1
#   u4:1:4:1        pipelined, unrolled by 4, arrays split over 4 memories
#   u4_nopart:1:4:0 the same, with each array left in one memory
#
# The three numbers become the macros POLY_PIPELINE, POLY_UNROLL and
# POLY_PARTITION, which decide which pragmas poly.cpp contains.  A -D flag
# belongs to a project, not to a solution, so each variant is a project of
# its own, proj_<name>, with one solution, sol.  poly_build.py passes the
# variant list; see VARIANTS there.
#
# Every project is built for the Vivado IP flow (-flow_target vivado): the
# arrays become ap_memory ports, as poly.cpp explains, rather than AXI.
#
# The projects are created in the directory Vitis runs in, which
# poly_build.py sets to this one.  The sources are always read from beside
# this script.
#
# Run a stage by hand, from this directory:
#
#   $env:POLY_STAGE="synth"; $env:POLY_VARIANTS="pipe:1:1:0"; vitis-run --mode hls --tcl run.tcl

set script_dir [file dirname [file normalize [info script]]]

proc env_or {name default} {
    if {[info exists ::env($name)]} {
        return $::env($name)
    }
    return $default
}

set stage       [env_or POLY_STAGE       "csim"]
set out_dir     [env_or POLY_OUT_DIR     [file join $script_dir results $stage]]
set variants    [env_or POLY_VARIANTS    "nopipe:0:1:0 pipe:1:1:0"]
set variant     [env_or POLY_VARIANT     "pipe"]
set period      [env_or POLY_PERIOD      "10"]
set trace_level [env_or POLY_TRACE_LEVEL "port"]
set part        [env_or POLY_PART        "xc7z020clg484-1"]

if {$stage ni {csim synth cosim}} {
    puts "POLY_ERROR: unknown stage '$stage' (expected csim, synth or cosim)."
    exit 1
}

# Open (or, with reset, create) one variant's project, with its -D flags.
# Absolute paths: Vitis rewrites a relative testbench path in the project
# file relative to wherever it last ran, which broke co-simulation in the
# quad demo.
proc open_variant {name pipeline unroll partition reset} {
    global script_dir
    set cflags "-I$script_dir -DPOLY_PIPELINE=$pipeline -DPOLY_UNROLL=$unroll -DPOLY_PARTITION=$partition"
    if {$reset} {
        open_project -reset proj_$name
    } else {
        open_project proj_$name
    }
    set_top poly
    add_files [file join $script_dir poly.cpp] -cflags $cflags
    add_files -tb [file join $script_dir tb_poly.cpp] -cflags $cflags
}

file mkdir $out_dir

switch -- $stage {
    csim {
        # C simulation does not depend on the pragmas, so one build covers
        # every variant.
        open_variant csim 1 1 0 1
        open_solution -reset -flow_target vivado sol
        set_part $part
        create_clock -period $period
        if {[catch {csim_design -argv "$out_dir"} res]} {
            puts "POLY_ERROR: C simulation failed."
            puts $res
            exit 1
        }
        close_project
    }
    synth {
        foreach spec $variants {
            lassign [split $spec :] name pipeline unroll partition
            puts "POLY_SYNTH: $name (pipeline=$pipeline unroll=$unroll partition=$partition)"
            open_variant $name $pipeline $unroll $partition 1
            open_solution -reset -flow_target vivado sol
            set_part $part
            create_clock -period $period
            if {[catch {csynth_design} res]} {
                puts "POLY_ERROR: C synthesis failed for $name."
                puts $res
                exit 1
            }
            close_project
        }
    }
    cosim {
        # The variant's flags again, so the testbench is compiled as it was.
        set spec ""
        foreach s $variants {
            if {[lindex [split $s :] 0] eq $variant} {
                set spec $s
            }
        }
        if {$spec eq ""} {
            puts "POLY_ERROR: variant '$variant' is not in POLY_VARIANTS ($variants)."
            exit 1
        }
        lassign [split $spec :] name pipeline unroll partition
        open_variant $name $pipeline $unroll $partition 0
        open_solution sol
        if {[catch {cosim_design -argv "$out_dir" -trace_level $trace_level} res]} {
            puts "POLY_ERROR: RTL co-simulation of $name failed."
            puts $res
            exit 1
        }
        close_project
    }
}

puts "POLY_SUCCESS: stage '$stage' completed."
exit 0
