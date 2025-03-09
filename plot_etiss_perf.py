#!/usr/bin/python3
import os
import re
import sys
import tempfile
import subprocess
from typing import Optional
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px


assert len(sys.argv) == 2
csv_path = sys.argv[1]


REL = True
# REL = False


def main():
    reports = []
    full_df = pd.read_csv(csv_path)

    if not REL:
        full_df["overhead"] = full_df["overhead"] * (full_df["time"] / full_df["time"].min()) / full_df["n_iter"]

    for group, group_df in full_df.groupby(["prog", "etiss_arch", "block_size", "jit"], dropna=False):
        group_df = group_df.groupby(["n_iter","dso_new"], as_index=False, dropna=False).agg({"overhead": np.sum, "mips": np.mean})
        group_df = group_df.sort_values("overhead", ascending=False)
        print("group", group)
        title = " - ".join(map(str, group))
        print(group_df)
        group_df_ = group_df.copy()
        for dso in group_df_["dso_new"].unique():
            new = pd.DataFrame([{"dso_new": dso, "n_iter": 0, "overhead": 0}])
            group_df_ = pd.concat([group_df_, new])
        # TODO: add mips on other axis?
        # fig = px.area(group_df, x="n_iter", y="overhead", color="dso_new", line_group="country")
        fig = px.area(group_df_, x="n_iter", y="overhead", color="dso_new", title=title)
        fig.add_scatter(x=group_df["n_iter"], y=group_df["mips"]/100, mode="markers", name="MIPS/100", marker=dict(size=10, color="darkgray"))
        fig.write_html("plot.html")
        input("CHECK HTML")


if __name__ == "__main__":
    main()
