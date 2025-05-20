#!/usr/bin/python3
import os
import re
import sys
import argparse
import tempfile
import subprocess
from typing import Optional
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument("--output-dir", default=None, required=True)
    parser.add_argument("--rel", action="store_true")
    parser.add_argument("--alt", action="store_true")
    parser.add_argument("--windowed", action="store_true")
    args = parser.parse_args()
    full_df = pd.read_csv(args.csv_path)

    if not args.rel:
        assert not args.windowed
        if args.alt:
            full_df["overhead"] = full_df["overhead"] * (full_df["time"] / full_df["time"].min())
        else:
            full_df["overhead"] = full_df["overhead"] * (full_df["time"] / full_df["time"].min()) / full_df["n_iter"]

    # group_df = full_df
    for group, group_df in full_df.groupby(["prog", "etiss_arch", "block_size", "jit"], dropna=False):
        group_df = group_df.groupby(["slice","dso_new"], as_index=False, dropna=False).agg({"overhead": np.sum})
        group_df = group_df.sort_values("overhead", ascending=False)
        print("group", group)
        title = " - ".join(map(str, group))
        print(group_df)
        group_df_ = group_df.copy()
        for dso in group_df_["dso_new"].unique():
            new = pd.DataFrame([{"dso_new": dso, "slice": 0, "overhead": 0}])
            group_df_ = pd.concat([group_df_, new])
        # TODO: add mips on other axis?
        print("group_df_", group_df)
        if not args.windowed:
            assert "slice" not in group_df.columns
            assert "n_iter" in group_df.columns
            # assert len(df["n_iter"].unique()) == 1
            fig = px.area(group_df_, x="n_iter", y="overhead", color="dso_new", title=title)
            fig.add_scatter(x=group_df["n_iter"], y=group_df["mips"]/100, mode="markers", name="MIPS/100", marker=dict(size=10, color="black"))
        else:
            # assert len(group_df_["n_iter"].unique()) == 1
            assert "slice" in group_df.columns
            assert "n_iter" not in group_df.columns
            fig = px.area(group_df_, x="slice", y="overhead", color="dso_new", title=title)
        out_dir = Path(args.output_dir)
        assert out_dir.is_dir()
        title_ = title.replace(" ", "")
        out_file = out_dir / f"{title_}.html"
        fig.write_html(out_file)
        # input("CHECK HTML")


if __name__ == "__main__":
    main()
