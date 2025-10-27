set unroll_factors {1 2 4}

foreach uf $unroll_factors {
    set sol_name "sol_uf$uf"
    open_project vmult_hls -reset
    set_top vec_mult

    # Pass UNROLL_FACTOR as a macro
    add_files -cflags "-Iinclude -DUNROLL_FACTOR=$uf" src/vmult.cpp
    add_files -tb testbench/tb_vmult.cpp

    open_solution $sol_name -reset
    set_part {xczu48dr-ffvg1517-2-e}
    create_clock -period 10 -name default

    # Optional: run C simulation
    # csim_design

    csynth_design

    # Optional: run co-simulation
    # cosim_design

    # Optional: export IP
    # export_design -format ip_catalog

    close_project
}
