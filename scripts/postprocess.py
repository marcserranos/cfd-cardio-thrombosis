"""We post-process the Fluent EnSight Gold export of the Case 1 LA simulation.

Per frame: MV/PV flow rates, LA volume, volume fractions of slow flow, velocity near the device face.
Cycle 2 (t > T_CYCLE): wall shear stress vectors accumulated -> TAWSS, OSI, ECAP on the wall.
Output: results/<run>/post/*.npz, *.json used by make_figures.py
Usage: python postprocess.py <run_dir> [t_cycle2_start]
"""
import json, os, sys
import numpy as np
import pyvista as pv
from scipy import ndimage as ndi

RUN = sys.argv[1]
T2 = float(sys.argv[2]) if len(sys.argv) > 2 else 0.875  # start of cycle 2 (s); period 0.875 s
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
POST = os.path.join(RUN, "post")
os.makedirs(POST, exist_ok=True)
SP = os.environ["SP"]

# ---- device position in the simulation frame (metres) ----
T = json.load(open(os.path.join(ROOT, "data", "derived", "transform.json")))
R, mvc = np.array(T["R"]), np.array(T["mv_centre_LPS"])
meta = np.load(f"{SP}/ct_meta.npy"); sp, org = meta[:3], meta[3:]
dev = np.load(f"{SP}/device.npy")
dev_lps = org + np.argwhere(dev) * sp
dev_sim = ((dev_lps - mvc) @ R.T) / 1000.0
dev_c = dev_sim.mean(0)
print("device centre (sim frame, mm):", np.round(dev_c * 1000, 1))

reader = pv.EnSightReader(os.path.join(RUN, "LA_Case001_ens.encas"))
times = np.array(reader.time_values)
avail = [i for i, t in enumerate(times) if os.path.exists(os.path.join(RUN, f"LA_Case001_ens{i + 1:05d}.geo"))]
print("frames available:", len(avail), "of", len(times))


def parts(i):
    reader.set_active_time_value(times[i])
    mb = reader.read()
    return {mb.get_block_name(k): mb[k] for k in range(mb.n_blocks)}


def face_flux(surf, inward_ref):
    """We integrate u.n over a cap; n points INTO the LA (inward_ref = LA centroid)."""
    s = surf.extract_surface().compute_cell_sizes(length=False, volume=False)
    s = s.point_data_to_cell_data()
    n = s.compute_normals(cell_normals=True, point_normals=False, auto_orient_normals=False)["Normals"]
    c = s.cell_centers().points
    sign = np.sign(((inward_ref - c) * n).sum(1).mean())
    u = s.cell_data["velocity"]
    return float(sign * ((u * n).sum(1) * s.cell_data["Area"]).sum()), float(s.cell_data["Area"].sum())


rows = []
wss_sum = None; wssv_sum = None; nwss = 0; wall_ref = None
for k, i in enumerate(avail):
    P = parts(i)
    fl = P["fluid"]
    cen = fl.points.mean(0)
    row = dict(t=float(times[i]), ncells=int(fl.n_cells))
    for z in ["mv", "pv_rs", "pv_ri", "pv_ls", "pv_li"]:
        q, a = face_flux(P[z], cen)
        row[f"Q_{z}_mLs"] = q * 1e6
        if z == "mv":
            row["mv_area_mm2"] = a * 1e6
            row["mv_z_mm"] = float(P[z].points[:, 2].mean() * 1000)
    vol = fl.compute_cell_sizes(length=False, area=False)["Volume"]
    row["volume_mL"] = float(vol.sum() * 1e6)
    cd = fl.point_data_to_cell_data()
    umag = np.linalg.norm(cd.cell_data["velocity"], axis=1)
    row["umean_ms"] = float((umag * vol).sum() / vol.sum())
    row["f_u_lt_0p1"] = float(vol[umag < 0.1].sum() / vol.sum())
    row["f_u_lt_0p05"] = float(vol[umag < 0.05].sum() / vol.sum())
    cc = fl.cell_centers().points
    near = np.linalg.norm(cc - dev_c, axis=1) < 0.010  # 10 mm sphere around the device centre
    row["u_near_device_ms"] = float((umag[near] * vol[near]).sum() / max(vol[near].sum(), 1e-30))
    row["KE_mJ"] = float(0.5 * 1060 * (umag**2 * vol).sum() * 1e3)
    rows.append(row)
    # cycle 2 wall shear stress accumulation (node values; wall connectivity is fixed)
    w = P["wall"]
    if times[i] > T2 + 1e-9:
        tau = np.c_[w.point_data["x_wall_shear"], w.point_data["y_wall_shear"], w.point_data["z_wall_shear"]]
        if wss_sum is None:
            wss_sum = np.zeros(w.n_points); wssv_sum = np.zeros((w.n_points, 3)); wall_ref = w.copy()
        if w.n_points == wss_sum.size:
            wss_sum += np.linalg.norm(tau, axis=1); wssv_sum += tau; nwss += 1
    if k % 10 == 0:
        print(f"t={row['t']:.2f} cells={row['ncells']} Qmv={row['Q_mv_mLs']:.1f} mL/s V={row['volume_mL']:.1f} mL u<0.1:{row['f_u_lt_0p1']:.2f}", flush=True)

json.dump(rows, open(os.path.join(POST, "timeseries.json"), "w"), indent=1)
if nwss:
    tawss = wss_sum / nwss
    osi = 0.5 * (1 - np.linalg.norm(wssv_sum / nwss, axis=1) / np.maximum(tawss, 1e-12))
    ecap = osi / np.maximum(tawss, 1e-6)
    wall_ref.point_data["TAWSS_Pa"] = tawss
    wall_ref.point_data["OSI"] = osi
    wall_ref.point_data["ECAP_1_Pa"] = ecap
    d_dev = np.linalg.norm(wall_ref.points - dev_c, axis=1)
    wall_ref.point_data["dist_device_mm"] = d_dev * 1000
    wall_ref.save(os.path.join(POST, "wall_indices_cycle2.vtp" if False else "wall_indices_cycle2.vtk"))
    face = d_dev < 0.012
    summ = dict(n_frames_cycle2=nwss,
                wall_TAWSS_median=float(np.median(tawss)), wall_ECAP_median=float(np.median(ecap)),
                device_TAWSS_median=float(np.median(tawss[face])), device_ECAP_median=float(np.median(ecap[face])),
                device_OSI_median=float(np.median(osi[face])),
                frac_wall_ECAP_gt_1p4=float((ecap > 1.4).mean()), frac_device_ECAP_gt_1p4=float((ecap[face] > 1.4).mean()))
    json.dump(summ, open(os.path.join(POST, "wss_summary.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1))
np.save(os.path.join(POST, "device_sim_m.npy"), dev_sim)
print("done")
