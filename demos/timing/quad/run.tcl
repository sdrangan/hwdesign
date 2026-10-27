# Vitis HLS script for the quad demo -- written by hand, not generated.
#
# One stage per invocation, named by the QUAD_STAGE environment variable:
#
#   csim    compile the testbench against the C++ kernel and run it
#   sweep   synthesize the kernel once per clock period in QUAD_PERIODS,
#           each into its own solution, unpipelined and pipelined
#   cosim   re-run the testbench against one synthesized solution,
#           named by QUAD_SOLUTION
#
# Every solution is built for the Vivado IP flow (-flow_target vivado).  That
# is what keeps AXI out of it: scalar arguments become plain wires, and the
# only control is the ap_start / ap_done handshake.  The Vitis kernel flow
# would put every argument on an AXI4-Lite register map instead.
#
# Solutions are named for their clock period: p10 is 10 ns, p3_33 is 3.33 ns,
# and pipe_p10 is the same at 10 ns with the function pipelined, II = 1.
# The pipelined ones get the directive here rather than a pragma in
# quad.cpp, so one source serves both.  The directive is exactly
#
#   #pragma HLS PIPELINE II=1
#
# written at the top of quad().
#
# Run a stage by hand, from this directory:
#
#   $env:QUAD_STAGE="sweep"; $env:QUAD_PERIODS="10 5"; vitis-run --mode hls --tcl run.tcl

set script_dir [file dirname [file normalize [info script]]]

proc env_or {name default} {
    if {[info exists ::env($name)]} {
        return $::env($name)
    }
    return $default
}

set stage       [env_or QUAD_STAGE       "csim"]
set out_dir     [env_or QUAD_OUT_DIR     [file join $script_dir results $stage]]
set periods     [env_or QUAD_PERIODS     "20 10 6.67 5 4 3.33 2.5"]
set solution    [env_or QUAD_SOLUTION    "p10"]
set trace_level [env_or QUAD_TRACE_LEVEL "port"]
set part        [env_or QUAD_PART        "xc7z020clg484-1"]

if {$stage ni {csim sweep cosim}} {
    puts "QUAD_ERROR: unknown stage '$stage' (expected csim, sweep or cosim)."
    exit 1
}

# p3_33 for 3.33 ns: a solution name is a directory, and a dot reads badly there.
proc solution_name {period pipelined} {
    set name "p[string map {. _} $period]"
    if {$pipelined} {
        return "pipe_$name"
    }
    return $name
}

if {$stage eq "csim"} {
    open_project -reset quad_proj
} else {
    open_project quad_proj
}
set_top quad
# Absolute paths.  Vitis rewrites a relative testbench path in the project
# file relative to wherever it last ran it, and the next stage's relative
# add_files then disagreed with it: co-simulation failed at "Instrumenting C
# test bench" whenever the stages ran in a particular order.
set src_dir [file join $script_dir src]
add_files [file join $src_dir quad.cpp] -cflags "-I$src_dir"
add_files -tb [file join $script_dir testbench tb_quad.cpp] -cflags "-I$src_dir"

file mkdir $out_dir

switch -- $stage {
    csim {
        open_solution -reset -flow_target vivado csim
        set_part $part
        create_clock -period 10
        if {[catch {csim_design -argv "$out_dir"} res]} {
            puts "QUAD_ERROR: C simulation failed."
            puts $res
            exit 1
        }
    }
    sweep {
        foreach pipelined {0 1} {
            foreach period $periods {
                set name [solution_name $period $pipelined]
                puts "QUAD_SWEEP: $name, clock period $period ns"
                open_solution -reset -flow_target vivado $name
                set_part $part
                create_clock -period $period
                # Multiplies on DSP blocks, additions on LUTs.  Left to itself,
                # Vitis fuses a multiply and the add after it into one DSP
                # "multiply-add" with a fixed number of pipeline stages,
                # whatever the clock, which hides the scheduling this demo is
                # about.  With the additions kept out of the DSP blocks, each
                # multiply is its own DSP, and -latency -1 lets the scheduler
                # choose how many of the DSP's internal registers to use: none
                # at a slow clock, three at a fast one.
                config_op mul -impl dsp -latency -1
                config_op add -impl fabric
                if {$pipelined} {
                    set_directive_pipeline -II 1 quad
                }
                if {[catch {csynth_design} res]} {
                    puts "QUAD_ERROR: C synthesis failed for $name."
                    puts $res
                    exit 1
                }
                close_solution
            }
        }
    }
    cosim {
        open_solution $solution
        if {[catch {cosim_design -argv "$out_dir" -trace_level $trace_level} res]} {
            puts "QUAD_ERROR: RTL co-simulation of $solution failed."
            puts $res
            exit 1
        }
    }
}

puts "QUAD_SUCCESS: stage '$stage' completed."
exit 0
