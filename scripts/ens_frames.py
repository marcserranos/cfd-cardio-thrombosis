"""We read the file numbers of an EnSight .encas so we know which frame files exist on disk."""
import os
import re


def available_frames(run, case="LA_Case001_ens"):
    """We return the time indices whose .geo file was downloaded (the export may skip steps)."""
    txt = open(os.path.join(run, case + ".encas")).read()
    ts = txt.split("time set:")[1]
    n = int(re.search(r"number of steps:\s*(\d+)", ts).group(1))
    m = re.search(r"filename numbers:\s*([\d\s]+?)\s*time values", ts)
    if m:
        nums = [int(x) for x in m.group(1).split()]
    else:
        s = int(re.search(r"filename start number:\s*(\d+)", ts).group(1))
        inc = int(re.search(r"filename increment:\s*(\d+)", ts).group(1))
        nums = [s + inc * k for k in range(n)]
    return [i for i, k in enumerate(nums) if os.path.exists(os.path.join(run, f"{case}{k:05d}.geo"))]
