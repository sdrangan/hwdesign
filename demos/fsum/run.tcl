# Vitis HLS script for the float-sum demo -- written by hand, not generated.
#
# One stage per invocation, named by the FSUM_STAGE environment variable:
#
#   csim    compile the testbench against each variant in FSUM_VARIANTS and
#           run it, into FSUM_OUT_DIR/<name>
#   synth   synthesize each variant in FSUM_VARIANTS, one project each
#   cosim   re-run the testbench against one synthesized variant, named by
#           FSUM_VARIANT
#
# A variant is the same source, fsum.cpp, with its loop written one of four
# ways.  Its spec is name:number, for example tree:2; the number becomes the
# macro FSUM_VARIANT (see fsum.h).  A -D flag belongs to a project,
# not to a solution, so each variant is a project of its own, proj_<name>,
# with one solution, sol.  fsum_build.py passes the variant list.
#
# The projects are created in the directory Vitis runs in, which fsum_build.py
# sets to this one.  The sources are always read from beside this script.
#
# Run a stage by hand, from this directory:
#
#   $env:FSUM_STAGE="synth"; $env:FSUM_VARIANTS="tree:2"; vitis-run --mode hls --tcl run.tcl

set script_dir [file dirname [file normalize [info script]]]

proc env_or {name default} {
    if {[info exists ::env($name)]} {
        return $::env($name)
    }
    return $default
}

set stage       [env_or FSUM_STAGE       "csim"]
set out_dir     [env_or FSUM_OUT_DIR     [file join $script_dir results $stage]]
set variants    [env_or FSUM_VARIANTS    "rolled:0 pragma:1 tree:2 lanes:3"]
set variant     [env_or FSUM_VARIANT     "tree"]
set period      [env_or FSUM_PERIOD      "10"]
set trace_level [env_or FSUM_TRACE_LEVEL "port"]
set part        [env_or FSUM_PART        "xc7z020clg484-1"]

if {$stage ni {csim synth cosim}} {
    puts "FSUM_ERROR: unknown stage '$stage' (expected csim, synth or cosim)."
    exit 1
}

# Absolute paths: Vitis rewrites a relative testbench path in the project
# file relative to wherever it last ran.
proc open_variant {prefix name number reset} {
    global script_dir
    set cflags "-I$script_dir -DFSUM_VARIANT=$number"
    if {$reset} {
        open_project -reset ${prefix}$name
    } else {
        open_project ${prefix}$name
    }
    set_top fsum
    add_files [file join $script_dir fsum.cpp] -cflags $cflags
    add_files -tb [file join $script_dir tb_fsum.cpp] -cflags $cflags
}

proc new_solution {} {
    global part period
    open_solution -reset -flow_target vivado sol
    set_part $part
    create_clock -period $period
}

file mkdir $out_dir

switch -- $stage {
    csim {
        # Each variant is different C++, so each is checked.
        foreach spec $variants {
            lassign [split $spec :] name number
            set dir [file join $out_dir $name]
            file mkdir $dir
            file copy -force [file join $out_dir cases.txt] [file join $dir cases.txt]
            puts "FSUM_CSIM: $name"
            open_variant csim_ $name $number 1
            new_solution
            if {[catch {csim_design -argv "$dir"} res]} {
                puts "FSUM_ERROR: C simulation failed for $name."
                puts $res
                exit 1
            }
            close_project
        }
    }
    synth {
        foreach spec $variants {
            lassign [split $spec :] name number
            puts "FSUM_SYNTH: $name"
            open_variant proj_ $name $number 1
            new_solution
            if {[catch {csynth_design} res]} {
                puts "FSUM_ERROR: C synthesis failed for $name."
                puts $res
                exit 1
            }
            close_project
        }
    }
    cosim {
        set spec ""
        foreach s $variants {
            if {[lindex [split $s :] 0] eq $variant} {
                set spec $s
            }
        }
        if {$spec eq ""} {
            puts "FSUM_ERROR: variant '$variant' is not in FSUM_VARIANTS ($variants)."
            exit 1
        }
        lassign [split $spec :] name number
        open_variant proj_ $name $number 0
        open_solution sol
        if {[catch {cosim_design -argv "$out_dir" -trace_level $trace_level} res]} {
            puts "FSUM_ERROR: RTL co-simulation of $name failed."
            puts $res
            exit 1
        }
        close_project
    }
}

puts "FSUM_SUCCESS: stage '$stage' completed."
exit 0
