# Vitis HLS script for the in-class exercise -- written by hand; the
# exercise does not touch it.  sqsum_build.py runs it once per stage, named by
# the SQ_STAGE environment variable:
#
#   csim    compile the testbench against your kernel, sqsum.cpp, and run it
#   synth   synthesize the reference (proj_ref) and your kernel (proj_yours)
#   cosim   re-run the testbench against your synthesized kernel
#
# Both kernels define the same function, sqsum, so each is a project of its
# own, with one solution, sol.  The projects are created in the directory
# Vitis runs in, which sqsum_build.py sets to this one.

set script_dir [file dirname [file normalize [info script]]]

proc env_or {name default} {
    if {[info exists ::env($name)]} {
        return $::env($name)
    }
    return $default
}

set stage   [env_or SQ_STAGE   "csim"]
set out_dir [env_or SQ_OUT_DIR [file join $script_dir results $stage]]
set period  [env_or SQ_PERIOD  "10"]
set part    [env_or SQ_PART    "xc7z020clg484-1"]

# Absolute paths: Vitis rewrites a relative testbench path relative to
# wherever it last ran.
proc open_kernel {name src reset} {
    global script_dir
    if {$reset} {
        open_project -reset proj_$name
    } else {
        open_project proj_$name
    }
    set_top sqsum
    add_files [file join $script_dir $src] -cflags "-I$script_dir"
    add_files -tb [file join $script_dir tb_sqsum.cpp] -cflags "-I$script_dir"
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
        open_kernel csim sqsum.cpp 1
        new_solution
        if {[catch {csim_design -argv "$out_dir"} res]} {
            puts "SQ_ERROR: C simulation failed."
            puts $res
            exit 1
        }
        close_project
    }
    synth {
        foreach {name src} {ref sqsum_ref.cpp yours sqsum.cpp} {
            puts "SQ_SYNTH: $name"
            open_kernel $name $src 1
            new_solution
            if {[catch {csynth_design} res]} {
                puts "SQ_ERROR: C synthesis failed for $name."
                puts $res
                exit 1
            }
            close_project
        }
    }
    cosim {
        open_kernel yours sqsum.cpp 0
        open_solution sol
        if {[catch {cosim_design -argv "$out_dir" -trace_level port} res]} {
            puts "SQ_ERROR: RTL co-simulation failed."
            puts $res
            exit 1
        }
        close_project
    }
    default {
        puts "SQ_ERROR: unknown stage '$stage' (expected csim, synth or cosim)."
        exit 1
    }
}

puts "SQ_SUCCESS: stage '$stage' completed."
exit 0
