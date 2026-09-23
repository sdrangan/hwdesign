# Vitis HLS script for the scalar_fun demo -- written by hand, not generated.
#
# One stage per invocation, named by the SCALAR_FUN_STAGE environment
# variable:
#
#   csim    compile the testbench against the C++ kernel and run it
#   csynth  synthesize the kernel to RTL
#   cosim   re-run the same testbench against the synthesized RTL
#
# The stages share one project, so `csim` -- the first -- is the only one
# that resets it; the later stages re-open what it built.  Running them
# separately is what lets the build script check the results after C
# simulation and again after co-simulation.
#
# You can also run a stage by hand:
#
#   SCALAR_FUN_STAGE=csim vitis-run --mode hls run.tcl        (bash)
#   $env:SCALAR_FUN_STAGE="csim"; vitis-run --mode hls run.tcl  (PowerShell)

set script_dir [file dirname [file normalize [info script]]]

proc env_or {name default} {
    if {[info exists ::env($name)]} {
        return $::env($name)
    }
    return $default
}

set stage       [env_or SCALAR_FUN_STAGE        "csim"]
set out_dir     [env_or SCALAR_FUN_OUT_DIR      [file join $script_dir results $stage]]
set trace_level [env_or SCALAR_FUN_TRACE_LEVEL  "all"]
set clk_period  [env_or SCALAR_FUN_CLK_PERIOD_NS 10]
set part        [env_or SCALAR_FUN_PART         "xc7z020clg484-1"]

if {$stage ni {csim csynth cosim}} {
    puts "SCALAR_FUN_ERROR: unknown stage '$stage' (expected csim, csynth or cosim)."
    exit 1
}

if {$stage eq "csim"} {
    open_project -reset scalar_fun_proj
} else {
    open_project scalar_fun_proj
}

set_top simp_fun
add_files src/scalar_fun.cpp -cflags "-Isrc"
add_files -tb testbench/tb_scalar_fun.cpp -cflags "-Isrc"

if {$stage eq "csim"} {
    open_solution -reset "solution1"
} else {
    open_solution "solution1"
}
set_part $part
create_clock -period $clk_period

# The testbench writes results.json here, so it has to exist before the
# testbench runs -- co-simulation runs it from deep inside the solution
# directory, not from here.
file mkdir $out_dir

switch -- $stage {
    csim {
        if {[catch {csim_design -argv "$out_dir"} res]} {
            puts "SCALAR_FUN_ERROR: C simulation failed."
            puts $res
            exit 1
        }
    }
    csynth {
        if {[catch {csynth_design} res]} {
            puts "SCALAR_FUN_ERROR: C synthesis failed."
            puts $res
            exit 1
        }
    }
    cosim {
        if {[catch {cosim_design -argv "$out_dir" -trace_level $trace_level} res]} {
            puts "SCALAR_FUN_ERROR: RTL co-simulation failed."
            puts $res
            exit 1
        }
    }
}

puts "SCALAR_FUN_SUCCESS: stage '$stage' completed."
exit 0
