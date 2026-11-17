"""We seed massless particles in the LA at the start of cycle 2 and advect them with the
cycle-2 velocity frames, repeated periodically, to get blood washout and residence time.
A particle leaves when it is no longer inside the fluid mesh (out through the MV or a PV).
Usage: python washout.py <run_dir> <t_cycle2_start> <n_cycles> <seed_spacing_mm>
"""
import json, os, sys
import numpy as np
import pyvista as pv

RUN = sys.argv[1]
T2 = float(sys.argv[2]); NCYC = int(sys.argv[3]); DS = float(sys.argv[4]) / 1000
POST = os.path.join(RUN, "post"); os.makedirs(POST, exist_ok=True)
reader = pv.EnSightReader(os.path.join(RUN, "LA_Case001_ens.encas"))
times = np.array(reader.time_values)
idx = [i for i, t in enumerate(times) if t > T2 - 1e-9 and os.path.exists(os.path.join(RUN, f"LA_Case001_ens{i + 1:05d}.geo"))]
dt = float(np.median(np.diff(times)))
print("cycle frames:", len(idx), "dt", dt)


def frame(i):
    reader.set_active_time_value(times[i])
    mb = reader.read()
    fl = mb[[mb.get_block_name(k) for k in range(mb.n_blocks)].index("fluid")]
    return pv.UnstructuredGrid(fl)


def vel(fl, X):
    s = pv.PolyData(X).sample(fl)
    return s.point_data["velocity"], s.point_data["vtkValidPointMask"].astype(bool)


f0 = frame(idx[0])
b = np.array(f0.bounds).reshape(3, 2)
g = np.stack(np.meshgrid(*[np.arange(lo + DS / 2, hi, DS) for lo, hi in b], indexing="ij"), -1).reshape(-1, 3)
_, inside = vel(f0, g)
X0 = g[inside]; X = X0.copy()
print("seeds:", len(X0))
alive = np.ones(len(X0), bool); t_exit = np.full(len(X0), np.inf)
remain = [(0.0, 1.0)]
t = 0.0
for c in range(NCYC):
    for k in range(len(idx)):
        fl = frame(idx[k])
        # midpoint (RK2) with frozen frame velocity over two sub-steps
        for sub in range(2):
            h = dt / 2
            u1, ok1 = vel(fl, X[alive])
            Xm = X[alive] + 0.5 * h * u1
            u2, ok2 = vel(fl, Xm)
            Xn = X[alive] + h * u2
            ok = ok1 & ok2
            ids = np.where(alive)[0]
            X[ids[ok]] = Xn[ok]
            gone = ids[~ok]
            t_exit[gone] = t + (sub + 1) * h
            alive[gone] = False
        t += dt
        remain.append((t, alive.mean()))
    print(f"cycle {c + 1}: remaining {alive.mean():.3f}", flush=True)
np.savez(os.path.join(POST, "washout.npz"), X0=X0, t_exit=t_exit, X_end=X, alive=alive, remain=np.array(remain))
json.dump(dict(n_seeds=int(len(X0)), cycles=NCYC, remaining_after=[float(r[1]) for r in remain[len(idx)::len(idx)]]),
          open(os.path.join(POST, "washout_summary.json"), "w"), indent=1)
