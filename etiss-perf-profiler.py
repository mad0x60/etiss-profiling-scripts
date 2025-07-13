#!/usr/bin/python3
import os
import argparse
from pathlib import Path
import subprocess

# Fixed paths
ETISS_INSTALL_DIR = Path(os.getenv("ETISS_INSTALL_DIR", "/home/mohamed/thesis/etiss/build_dir/"))
ETISS_EXE = ETISS_INSTALL_DIR / "bin" / "bare_etiss_processor"
ETISS_EXAMPLES_DIR = Path(os.getenv("ETISS_EXAMPLES_DIR", "/home/mohamed/thesis/etiss_riscv_examples"))
OUTPUT_DIR = Path("perf_results")

def setup_ini(ini_path: Path, jit: str, fast_jit: str = None, block_size: int = 100):
    """Create ETISS configuration INI file."""
    content = f"""
[StringConfigurations]
jit.type={jit}JIT
"""
    if fast_jit:
        content += f"jit.fast_type={fast_jit}JIT\n"

    content += f"""
[IntConfigurations]
etiss.max_block_size={block_size}
etiss.loglevel=1
"""
    ini_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ini_path, "w") as f:
        f.write(content)

def compile_prog(prog: str, toolchain: str = "gcc", arch: str = "rv32gc", abi: str = "ilp32d", build_type: str = "Release", n_iter: int = 1):
    """Compile the target program."""
    command = f"scripts/compile_example.sh {prog} {toolchain} {arch} {abi} {build_type} {n_iter}"
    print(f"Compiling {prog}...")
    proc = subprocess.run(command, text=True, shell=True, capture_output=True)
    proc.check_returncode()

def get_etiss_cmd(extra_ini: Path, prog: str, etiss_arch: str = "RV32IMACFD", block_size: int = 100, jit: str = "GCC", fast_jit: str = None, n_iter: int = 1):
    """Construct full ETISS command with all parameters."""
    etiss_cmd = f"{ETISS_EXE} -i{ETISS_EXAMPLES_DIR}/build/install/ini/{prog}.ini -i{extra_ini} --arch.cpu={etiss_arch}"
    
    # Create output directory structure for time tracker
    out_dir = OUTPUT_DIR / prog
    out_dir.mkdir(exist_ok=True)
    fast_jit_str = fast_jit if fast_jit else "None"
    out_file = out_dir / f"{block_size}_{jit}_{fast_jit_str}_{n_iter}_time_tracker.log"
    etiss_cmd += f" --time_tracker.enable=true --time_tracker.out_path={out_file}"
    
    print("$ etiss_cmd:", etiss_cmd)
    return etiss_cmd

def run_perf_profile(prog: str, jit: str = "GCC", fast_jit: str = None, block_size: int = 100, n_iter: int = 1, etiss_arch: str = "RV32IMACFD"):
    """Run ETISS with perf profiling."""
    # Create output directory
    output_dir = OUTPUT_DIR / prog
    output_dir.mkdir(parents=True, exist_ok=True)

    # Setup extra INI file
    extra_ini = output_dir / "extra.ini"
    setup_ini(extra_ini, jit, fast_jit, block_size)

    # Get full ETISS command with all parameters
    etiss_cmd = get_etiss_cmd(extra_ini, prog, etiss_arch=etiss_arch, block_size=block_size, jit=jit, fast_jit=fast_jit, n_iter=n_iter)

    # Create output directory structure
    fast_jit_str = fast_jit if fast_jit else "None"
    base_name = f"{block_size}_{jit}_{fast_jit_str}_{n_iter}"
    
    # Setup perf output files
    perf_data = output_dir / f"{base_name}_perf.data"
    perf_report = output_dir / f"{base_name}_report.txt"
    firefox_prof_data = output_dir / f"{base_name}_ffp.data"
    
    # Run perf record
    print(f"Running perf record for {prog}...")
    perf_record_cmd = f"perf record -F 999 -g --call-graph dwarf -o {perf_data} {etiss_cmd}"
    subprocess.run(perf_record_cmd, shell=True, check=True)

    # Generate Firefox profiler data
    print(f"Generating Firefox profiler data...")
    perf_script_cmd = f"perf script -i {perf_data} > {firefox_prof_data}"
    subprocess.run(perf_script_cmd, shell=True, check=True)

    # Generate perf report
    print(f"Generating perf report...")
    perf_report_cmd = f"perf report -i {perf_data} --stdio > {perf_report}"
    subprocess.run(perf_report_cmd, shell=True, check=True)

    print(f"\nProfiling completed!")
    print(f"Results saved to:")
    print(f"  Perf data: {perf_data}")
    print(f"  Firefox profiler data: {firefox_prof_data}")
    print(f"  Perf report: {perf_report}")
    print(f"  Time tracker log: {output_dir / f'{base_name}_time_tracker.log'}")

def main():
    parser = argparse.ArgumentParser(description="Profile ETISS execution using perf")
    parser.add_argument("--prog", default="dhry")
    parser.add_argument("--toolchain", default="gcc")
    parser.add_argument("--etiss-arch", default="RV32IMACFD")
    parser.add_argument("--arch", default="rv32gc")
    parser.add_argument("--abi", default="ilp32d")
    parser.add_argument("--build-type", default="Release")
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--jits", nargs="+", default=["GCC"], choices=["GCC", "TCC", "LLVM"])
    parser.add_argument("--fast-jit", nargs="+", default=[None], choices=["None", "TCC", "LLVM"], help="Optional fast JIT for initial compilation")
    parser.add_argument("--block-sizes", type=int, nargs="+", default=[100])
    parser.add_argument("--num-iters", type=int, nargs="+", default=[1])
    parser.add_argument("--num-slices", type=int, default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--perf-only", action="store_true", help="Only run perf profiling without MIPS measurements")
    args = parser.parse_args()

    # Process arguments
    prog = args.prog
    toolchain = args.toolchain
    arch = args.arch
    abi = args.abi
    build_type = args.build_type
    n_slices = args.num_slices
    n_iters = args.num_iters
    block_sizes = args.block_sizes
    jits = args.jits
    etiss_arch = args.etiss_arch
    fast_jit = [None if x == "None" else x for x in args.fast_jit]

    # Compile program once
    compile_prog(prog, toolchain=toolchain, arch=arch, abi=abi, build_type=build_type)

    # Run profiling for each combination
    for n_iter in n_iters:
        for block_size in block_sizes:
            for jit in jits:
                for fj in fast_jit:
                    print("====================================================")
                    print(f"Running profile: n_iter={n_iter}, block_size={block_size}, jit={jit}, fast_jit={fj}")
                    run_perf_profile(
                        prog=prog,
                        jit=jit,
                        fast_jit=fj,
                        block_size=block_size,
                        n_iter=n_iter,
                        etiss_arch=etiss_arch
                    )

if __name__ == "__main__":
    main()
