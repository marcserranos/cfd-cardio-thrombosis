"""We make the report figures from the post-processed simulation.
Usage: python make_figures.py <run_dir> <t_epeak> <t_diastasis>
"""
import json, os, sys
import numpy as np
import pyvista as pv
from ens_frames import available_frames
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

pv.OFF_SCREEN = True
RUN = sys.argv[1]; T_E = float(sys.argv[2]); T_D = float(sys.argv[3])
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FIG = os.path.join(ROOT, "figures"); POST = os.path.join(RUN, "post")
dev = np.load(os.path.join(POST, "device_sim_m.npy"))
dc = dev.mean(0)
reader = pv.EnSightReader(os.path.join(RUN, "LA_Case001_ens.encas"))
times = np.array(reader.time_values)
have = available_frames(RUN)


def load(t):
    i = min(have, key=lambda j: abs(times[j] - t))
    reader.set_active_time_value(times[i])
    mb = reader.read()
    return {mb.get_block_name(k): mb[k] for k in range(mb.n_blocks)}, times[i]


# slice plane through the device centre containing the Z (MV motion) axis and the device direction
d = dc.copy(); d[2] = 0; d /= np.linalg.norm(d)
normal = np.cross(d, [0, 0, 1.0]); normal /= np.linalg.norm(normal)
cam = dict(position=tuple(dc + normal * 0.25), focal_point=tuple(dc * np.array([0.5, 0.5, 1]) + np.array([0, 0, 0.0])), viewup=(0, 0, 1))


def velocity_panel(t, fname, title):
    P, tt = load(t)
    fl = P["fluid"]
    sl = fl.slice(normal=normal, origin=dc)
    p = pv.Plotter(off_screen=True, window_size=(700, 700))
    p.add_mesh(P["wall"], color="lightgray", opacity=0.12)
    p.add_mesh(sl, scalars="velocity_magnitude", cmap="turbo", clim=[0, 0.6],
               scalar_bar_args=dict(title="|u| (m/s)", vertical=True, height=0.5, position_x=0.85, position_y=0.25))
    seeds = pv.PolyData(sl.points[::40])
    try:
        st = fl.streamlines_from_source(seeds, vectors="velocity", max_time=0.05, integration_direction="both")
        p.add_mesh(st.tube(radius=0.00012), color="white", opacity=0.6)
    except Exception as e:
        print("streamlines skipped:", e)
    p.add_points(dev, color="black", point_size=2, render_points_as_spheres=False)
    p.camera_position = [cam["position"], cam["focal_point"], cam["viewup"]]
    p.add_text(f"{title}  t = {tt:.2f} s", font_size=11)
    p.screenshot(os.path.join(FIG, fname))


velocity_panel(T_E, "cfd_vel_Epeak.png", "E-wave peak")
velocity_panel(T_D, "cfd_vel_diastasis.png", "Late diastole / systole")

w = pv.read(os.path.join(POST, "wall_indices_cycle2.vtk"))
for arr, clim, cmap, fname in [("TAWSS_Pa", [0, 0.6], "viridis", "cfd_tawss.png"), ("ECAP_1_Pa", [0, 10], "inferno", "cfd_ecap.png")]:
    p = pv.Plotter(off_screen=True, window_size=(700, 700))
    p.add_mesh(w, scalars=arr, cmap=cmap, clim=clim, smooth_shading=True,
               scalar_bar_args=dict(title=arr.replace("_1_Pa", " (1/Pa)").replace("_Pa", " (Pa)"), vertical=True, height=0.5, position_x=0.85, position_y=0.25))
    ring = w.extract_points(w.point_data["dist_device_mm"] < 12.0, adjacent_cells=False)
    p.add_mesh(ring.extract_feature_edges(boundary_edges=True, feature_edges=False, manifold_edges=False, non_manifold_edges=False), color="cyan", line_width=3)
    p.camera_position = [tuple(dc + d * 0.15 + np.array([0, 0, 0.03])), tuple(dc), (0, 0, 1)]
    p.add_text("cycle 2 - device face outlined (cyan)", font_size=10)
    p.screenshot(os.path.join(FIG, fname))

# time series + washout
ts = json.load(open(os.path.join(POST, "timeseries.json")))
t = np.array([r["t"] for r in ts])
fig, ax = plt.subplots(1, 3, figsize=(12, 3.0))
ax[0].plot(t, [-r["Q_mv_mLs"] for r in ts], label="MV outflow")
ax[0].plot(t, [sum(r[f"Q_{z}_mLs"] for z in ["pv_rs", "pv_ri", "pv_ls", "pv_li"]) for r in ts], label="PV inflow (sum)")
ax[0].set_xlabel("t (s)"); ax[0].set_ylabel("flow (mL/s)"); ax[0].legend(fontsize=7); ax[0].grid(alpha=0.3)
ax[1].plot(t, [r["u_near_device_ms"] * 100 for r in ts], label="10 mm around device")
ax[1].plot(t, [r["umean_ms"] * 100 for r in ts], label="whole LA")
ax[1].set_xlabel("t (s)"); ax[1].set_ylabel("mean |u| (cm/s)"); ax[1].legend(fontsize=7); ax[1].grid(alpha=0.3)
wo_f = os.path.join(POST, "washout.npz")
if os.path.exists(wo_f):
    wo = np.load(wo_f)
    rem = wo["remain"]
    ax[2].plot(rem[:, 0] / 0.875, rem[:, 1] * 100, label="all seeds")
    X0, te = wo["X0"], wo["t_exit"]
    near = np.linalg.norm(X0 - dc, axis=1) < 0.012
    tt = rem[:, 0]
    ax[2].plot(tt / 0.875, [(te[near] > x).mean() * 100 for x in tt], label="seeds < 12 mm from device")
    ax[2].set_xlabel("cardiac cycles"); ax[2].set_ylabel("blood remaining in LA (%)"); ax[2].legend(fontsize=7); ax[2].grid(alpha=0.3)
plt.tight_layout(); plt.savefig(os.path.join(FIG, "cfd_timeseries.png"), dpi=200)
print("figures written")
