#!/usr/bin/python3
import os
import re
import argparse
import tempfile
import subprocess
from typing import Optional
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px

from contextlib import nullcontext

DIR = os.path.dirname(os.path.realpath(__file__))

# TODO
DIR = Path(DIR)

ETISS_INSTALL_DIR = Path(os.getenv("ETISS_INSTALL_DIR", "/home/mohamed/thesis/etiss/build_dir/"))
ETISS_EXE = ETISS_INSTALL_DIR / "bin" / "bare_etiss_processor"
ETISS_EXAMPLES_DIR = Path(os.getenv("ETISS_EXAMPLES_DIR", "/home/mohamed/thesis/etiss_riscv_examples"))

def populate_extra_ini(ini_path: Path, jit: str, fast_jit: Optional[str], block_size: Optional[int]):
    content = f"""
[StringConfigurations]
jit.type={jit}JIT
"""
    if fast_jit:
        content += f"jit.fast_type={fast_jit}JIT\n"

    content += f"""
[IntConfigurations]
etiss.max_block_size={block_size}
"""
    with open(ini_path, "w") as f:
        f.write(content)

def get_etiss_cmd(extra_ini: Path, prog: str, etiss_arch: str = "RV32IMACFD"):
    etiss_cmd = f"{ETISS_EXE} -i{ETISS_EXAMPLES_DIR}/build/install/ini/{prog}.ini -i{extra_ini} --arch.cpu={etiss_arch}"
    return etiss_cmd

def get_mips(workdir: Path, prog: str, etiss_arch: str = "RV32IMACFD", repeat: int = 1):
    extra_ini = workdir / "extra.ini"
    etiss_cmd = get_etiss_cmd(extra_ini, prog, etiss_arch=etiss_arch)
    # TODO: run multiple times for avg?
    all_mips = []
    all_times = []
    assert repeat > 0
    for _ in range(repeat):
        proc = subprocess.run(etiss_cmd, check=True, text=True, shell=True, cwd=workdir, capture_output=True)
        out = proc.stdout
        print("out", out)
        mips_match = re.search(r"MIPS \(estimated\): (.*)", out)
        assert mips_match is not None
        mips_str = mips_match.group(1)
        mips = float(mips_str)
        all_mips.append(mips)
        time_match = re.search(r"Simulation Time: (.*)s", out)
        assert time_match is not None
        time_str = time_match.group(1)
        time = float(time_str)
        all_times.append(time)
    sim_insns = re.search(r"CPU Cycles \(estimated\): (.*)", out)
    sim_insns = int(float(sim_insns.group(1)))
    avg_mips = sum(all_mips) / repeat
    avg_time = sum(all_times) / repeat
    return avg_mips, avg_time, sim_insns

def compile_prog(workdir: Path, prog: str, toolchain: str = "gcc", arch: str = "rv32gc", abi: str = "ilp32d", build_type: str = "Release", n_iter: int = 1):
    command = f"{DIR}/scripts/compile_example.sh {prog} {toolchain} {arch} {abi} {build_type} {n_iter}"
    # _ = subprocess.run(command, check=True, text=True, shell=True, cwd=workdir, capture_output=True)
    print("Running:", command)
    proc = subprocess.run(command, text=True, shell=True, capture_output=True)
    print("STDOUT:\n", proc.stdout)
    print("STDERR:\n", proc.stderr)
    proc.check_returncode()

def run_perf_record(workdir: Path, prog: str, etiss_arch: str = "RV32IMACFD"):
    extra_ini = workdir / "extra.ini"
    etiss_cmd = get_etiss_cmd(extra_ini, prog, etiss_arch=etiss_arch)

    command = f"perf record -o {workdir}/perf.data {etiss_cmd}"
    print("Running:", command)
    # print("cwd", workdir)
    # _ = subprocess.run(command, check=True, text=True, shell=True, cwd=workdir, capture_output=True)
    proc = subprocess.run(command, check=True, shell=True, cwd=workdir, capture_output=True)
    # out = proc.stdout.decode()
    # print("out", out)
    # input("???")


def get_perf_report(workdir: Path, prog: str, etiss_arch: str = "RV32IMACFD", n_slices: Optional[int] = None):
    def replace_dso_names(dso):
        temp = re.sub(r"-.*", r"", re.sub(r"\.so(\..*)?", r"", dso)).replace("[", "").replace("]", "").lower()
        if temp.startswith("librv"):
            return "etiss_arch"
        if temp.startswith("libboost"):
            return "boost"
        if temp.startswith("libsemihost"):
            return "etiss"
        if temp.startswith("x86_64"):
            return "gcc"
        if temp.startswith("libcode_"):
            return "etiss_jitcode"
        if "llvm" in temp:
            return "llvm"
        if "tcc" in temp:
            return "tcc"
        if "gcc" in temp:
            return "gcc"
        if "etiss" in temp:
            return "etiss"
        if "dso" in temp:
            return "dso"
        if temp in ["cc1", "collect2", "ld"]:
            return "gcc"
        if temp in ["bash", "rm"]:
            return "sh"
        if temp.startswith("lib"):
            return "libs"
        return temp

    run_perf_record(workdir, prog, etiss_arch=etiss_arch)
    if n_slices is not None and n_slices > 1:
        slice_per = 100 / n_slices
        dfs = []
        for i in range(n_slices):
            command = f"perf report -F dso,overhead --stdio --time {slice_per}%/{i+1} | grep -v 'Samples' | grep '%' | tr -s ' ' | sed -e \"s/tid\\s[0-9]*//g\" |" + " awk '{print $1 \",\" $2/100}'"
            outfile = workdir / "out.csv"
            with open(outfile, "w") as f:
                _ = subprocess.run(command, check=True, text=True, shell=True, cwd=workdir, stdout=f)
            # print("workdir", workdir)
            # input("1")
            report_df = pd.read_csv(outfile, names=["dso", "overhead"])
            report_df = report_df.sort_values("overhead", ascending=False)
            report_df["dso_new"] = report_df["dso"].apply(replace_dso_names)
            report_df["slice"] = i
            dfs.append(report_df)
        df = pd.concat(dfs)
    else:
        command = "perf report -F dso,overhead --stdio | grep '%' | tr -s ' ' | sed -e \"s/tid\\s[0-9]*//g\" | awk '{print $1 \",\" $2/100}'"
        # print("command", command)

        outfile = workdir / "out.csv"
        with open(outfile, "w") as f:
            _ = subprocess.run(command, check=True, text=True, shell=True, cwd=workdir, stdout=f)
        # print("workdir", workdir)
        # input("1")
        report_df = pd.read_csv(outfile, names=["dso", "overhead"])
        report_df = report_df.sort_values("overhead", ascending=False)
        report_df["dso_new"] = report_df["dso"].apply(replace_dso_names)
        df = report_df
    # print("report_df")
    return df



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prog", default="dhry")
    parser.add_argument("--toolchain", default="gcc")
    parser.add_argument("--etiss-arch", default="RV32IMACFD")
    parser.add_argument("--arch", default="rv32gc")
    parser.add_argument("--abi", default="ilp32d")
    parser.add_argument("--build-type", default="Release")
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--jits", nargs="+", default=["GCC"], choices=["GCC", "TCC", "LLVM"])
    parser.add_argument("--fast-jit", default=None, choices=[None, "TCC", "LLVM"], help="Optional fast JIT for initial compilation")
    parser.add_argument("--block-sizes", type=int, nargs="+", default=[100])
    # parser.add_argument("--num-iters", type=int, nargs="+", default=[1, 2, 5, 10, 20, 40, 80])
    parser.add_argument("--num-iters", type=int, nargs="+", default=[1])
    parser.add_argument("--num-slices", type=int, default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    prog = args.prog
    toolchain = args.toolchain
    arch = args.arch
    abi = args.abi
    build_type = args.build_type
    n_slices = args.num_slices
    n_iters = args.num_iters
    block_sizes = args.block_sizes
    jits = args.jits
    repeat = args.repeat
    etiss_arch = args.etiss_arch
    fast_jit = args.fast_jit

    TMP_PATH = Path("/home/mohamed/thesis/etiss-profiling-scripts/tmp")

    if n_slices is not None and n_slices > 1:
        assert len(n_iters) == 1

    reports = []
    # with tempfile.TemporaryDirectory(dir=str(TMP_PATH)) as tmpdir:
    with nullcontext(str(TMP_PATH)) as tmpdir:
        workdir = Path(tmpdir)
        extra_ini = workdir / "extra.ini"
        # etiss_cmd = get_etiss_cmd(extra_ini, prog)
        dfs = []
        for n_iter in n_iters:
            assert n_iter != 0
            compile_prog(workdir, prog, toolchain=toolchain, arch=arch, abi=abi, build_type=build_type, n_iter=n_iter)
            for block_size in block_sizes:
                assert block_size > 0
                for jit in jits:
                    populate_extra_ini(extra_ini, jit, fast_jit, block_size=block_size)
                    sim_mips, sim_time, sim_instrs = get_mips(workdir, prog, etiss_arch=etiss_arch, repeat=repeat)
                    report_df = get_perf_report(workdir, prog, etiss_arch=etiss_arch, n_slices=n_slices)
                    report_df["n_iter"] = n_iter
                    report_df["mips"] = sim_mips
                    report_df["time"] = sim_time
                    report_df["instrs"] = sim_instrs
                    report_df["prog"] = prog
                    report_df["etiss_arch"] = etiss_arch
                    report_df["block_size"] = block_size
                    report_df["jit"] = jit
                    dfs.append(report_df)
        full_df = pd.concat(dfs)
        full_df.reset_index(inplace=True)
        with pd.option_context("display.max_rows", None, "display.max_columns", None):
            print(full_df)
        full_df.to_csv(args.output, index=False)




if __name__ == "__main__":
    main()
