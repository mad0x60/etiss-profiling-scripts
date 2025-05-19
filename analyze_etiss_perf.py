#!/usr/bin/python3
import os
import re
import tempfile
import subprocess
from typing import Optional
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px


DIR = os.path.dirname(os.path.realpath(__file__))

# TODO
DIR = Path(DIR).parent

ETISS_INSTALL_DIR = Path("/work/git/hm/etiss_48bit/48bit-riscv-flow/install/etiss/")
ETISS_EXE = ETISS_INSTALL_DIR / "bin" / "bare_etiss_processor"
ETISS_EXAMPLES_DIR = Path("/work/git/hm/etiss_48bit/48bit-riscv-flow/etiss_riscv_examples")

ETISS_ARCH = "RV32IMACFD"

# JITS = ["TCC", "GCC", "LLVM"]
JITS = ["TCC"]
# BLOCK_SIZES = [100, 1000]
BLOCK_SIZES = [100]

# PROG = "hello_world"
PROG = "dhry"

# ITERS = [1, 2, 10]
# ITERS = [1, 2, 5, 10]
ITERS = [1, 2, 5, 10, 20, 40, 80]
REPEAT = 2

TOOLCHAIN = "llvm"

ARCH = "rv32gc"
ABI = "ilp32d"

BUILD_TYPE = "Release"

OUTFILE = "etiss_perf.csv"


def populate_extra_ini(ini_path: Path, jit: str, block_size: Optional[int]):
    content = f"""
[StringConfigurations]
jit.type={jit}JIT

[IntConfigurations]
etiss.max_block_size={block_size}
"""
    with open(ini_path, "w") as f:
        f.write(content)

def get_etiss_cmd(extra_ini):
    etiss_cmd = f"{ETISS_EXE} -i{ETISS_EXAMPLES_DIR}/build/install/ini/{PROG}.ini -i{extra_ini} --arch.cpu={ETISS_ARCH}"
    return etiss_cmd

def get_mips(workdir: Path, repeat: int = 1):
    extra_ini = workdir / "extra.ini"
    etiss_cmd = get_etiss_cmd(extra_ini)
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

def compile_prog(workdir: Path, n_iter):
    command = f"{DIR}/scripts/compile_example.sh {PROG} {TOOLCHAIN} {ARCH} {ABI} {BUILD_TYPE} {n_iter}"
    # _ = subprocess.run(command, check=True, text=True, shell=True, cwd=workdir, capture_output=True)
    _ = subprocess.run(command, check=True, text=True, shell=True, capture_output=True)

def run_perf_record(workdir: Path):
    extra_ini = workdir / "extra.ini"
    etiss_cmd = get_etiss_cmd(extra_ini)

    command = f"perf record -o {workdir}/perf.data {etiss_cmd}"
    # print("command", command)
    # print("cwd", workdir)
    # _ = subprocess.run(command, check=True, text=True, shell=True, cwd=workdir, capture_output=True)
    proc = subprocess.run(command, check=True, shell=True, cwd=workdir, capture_output=True)
    # out = proc.stdout.decode()
    # print("out", out)
    # input("???")

def get_perf_report(workdir: Path):
    run_perf_record(workdir)
    command = "perf report -F dso,overhead --stdio | grep '%' | tr -s ' ' | sed -e \"s/tid\\s[0-9]*//g\" | awk '{print $1 \",\" $2/100}'"
    # print("command", command)

    outfile = workdir / "out.csv"
    with open(outfile, "w") as f:
        _ = subprocess.run(command, check=True, text=True, shell=True, cwd=workdir, stdout=f)
    # print("workdir", workdir)
    # input("1")
    report_df = pd.read_csv(outfile, names=["dso", "overhead"])
    report_df = report_df.sort_values("overhead", ascending=False)
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
    report_df["dso_new"] = report_df["dso"].apply(replace_dso_names)
    # print("report_df")
    return report_df


def main():
    reports = []
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        extra_ini = workdir / "extra.ini"
        etiss_cmd = get_etiss_cmd(extra_ini)
        dfs = []
        for n_iter in ITERS:
            assert n_iter != 0
            compile_prog(workdir, n_iter)
            for block_size in BLOCK_SIZES:
                assert block_size > 0
                for jit in JITS:
                    populate_extra_ini(extra_ini, jit, block_size=block_size)
                    sim_mips, sim_time, sim_instrs = get_mips(workdir, repeat=REPEAT)
                    report_df = get_perf_report(workdir)
                    report_df["n_iter"] = n_iter
                    report_df["mips"] = sim_mips
                    report_df["time"] = sim_time
                    report_df["instrs"] = sim_instrs
                    report_df["prog"] = PROG
                    report_df["etiss_arch"] = ETISS_ARCH
                    report_df["block_size"] = block_size
                    report_df["jit"] = jit
                    dfs.append(report_df)
        full_df = pd.concat(dfs)
        full_df.reset_index(inplace=True)
        with pd.option_context("display.max_rows", None, "display.max_columns", None):
            print(full_df)
        full_df.to_csv(OUTFILE, index=False)

        # for group, group_df in full_df.groupby(["prog", "etiss_arch", "block_size", "jit"]):
        #     group_df = group_df.groupby(["n_iter","dso_new"], as_index=False).agg({"overhead": np.sum})
        #     group_df = group_df.sort_values("overhead", ascending=False)
        #     print("group", group)
        #     title = " - ".join(map(str, group))
        #     print(group_df)
        #     group_df_ = group_df.copy()
        #     for dso in group_df_["dso_new"].unique():
        #         new = pd.DataFrame([{"dso_new": dso, "n_iter": 0, "overhead": 0}])
        #         group_df_ = pd.concat([group_df_, new])
        #     # TODO: add mips on other axis?
        #     # fig = px.area(group_df, x="n_iter", y="overhead", color="dso_new", line_group="country")
        #     fig = px.area(group_df_, x="n_iter", y="overhead", color="dso_new", title=title)
        #     fig.write_html("plot.html")
        #     input("CHECK HTML")


if __name__ == "__main__":
    main()
