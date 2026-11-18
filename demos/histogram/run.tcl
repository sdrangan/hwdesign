# Vitis HLS script for the histogram demo -- written by hand, not generated.
#
# One stage of one version per invocation, from environment variables:
#
#   HIST_STAGE    csim   compile tb_<top>.cpp against <top>.cpp and run it
#                 synth  synthesize <top>, the RTL the XSI testbench drives
#   HIST_TOP      the top function, and the stem of its source: histogram_stream
#                 (histogram_mm later)
#   HIST_PROJ     the Vitis project directory, one per version: proj_stream, proj_mm
#   HIST_IN_DIR   csim: where the testbench reads mem_in.bin and cmds.bin
#   HIST_OUT_DIR  csim: where it writes mem_out.bin and resp.bin
#
# The projects are created in the directory Vitis runs in, which hist_build.py sets to this
# one.  The sources are read from beside this script; the generated headers from include/.
#
# Run a stage by hand, from this directory (after `python hist_build.py --through gen_include`):
#
#   $env:HIST_STAGE="synth"; $env:HIST_TOP="histogram_stream"; $env:HIST_PROJ="proj_stream"
#   vitis-run --mode hls --tcl run.tcl

set script_dir [file dirname [file normalize [info script]]]

proc env_or {name default} {
    if {[info exists ::env($name)]} {
        return $::env($name)
    }
    return $default
}

set stage   [env_or HIST_STAGE   "csim"]
set top     [env_or HIST_TOP     "histogram_stream"]
set proj    [env_or HIST_PROJ    "proj_stream"]
set in_dir  [env_or HIST_IN_DIR  [file join $script_dir results stream vectors]]
set out_dir [env_or HIST_OUT_DIR [file join $script_dir results stream csim]]
set period  [env_or HIST_PERIOD  "10"]
set part    [env_or HIST_PART    "xc7z020clg484-1"]

if {$stage ni {csim synth}} {
    puts "HIST_ERROR: unknown stage '$stage' (expected csim or synth)."
    exit 1
}

# Absolute paths: Vitis rewrites a relative path in the project file relative to wherever it
# last ran.
set cflags "-I$script_dir -I[file join $script_dir include] -std=c++14"
# C simulation gets a project of its own, so it never resets the synthesized one.
if {$stage eq "csim"} {
    set proj "csim_$proj"
}
open_project -reset $proj
set_top $top
add_files [file join $script_dir $top.cpp] -cflags $cflags
add_files -tb [file join $script_dir tb_$top.cpp] -cflags $cflags
open_solution -reset -flow_target vivado sol
set_part $part
create_clock -period $period

switch -- $stage {
    csim {
        file mkdir $out_dir
        puts "HIST_CSIM: $top"
        if {[catch {csim_design -argv "$in_dir $out_dir"} res]} {
            puts "HIST_ERROR: C simulation of $top failed."
            puts $res
            exit 1
        }
    }
    synth {
        puts "HIST_SYNTH: $top"
        if {[catch {csynth_design} res]} {
            puts "HIST_ERROR: C synthesis of $top failed."
            puts $res
            exit 1
        }
    }
}

close_project
puts "HIST_SUCCESS: stage '$stage' of $top completed."
exit 0
