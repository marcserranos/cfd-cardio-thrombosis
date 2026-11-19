"""We make two extra figures for the paper-style report:
1. fig_pipeline.png   : CT -> 3D model -> volume mesh -> simulated flow (one picture per step)
2. fig_keynumbers.png : device region vs whole left atrium (speed, washout, ECAP, OSI)
Usage: python make_paper_figures.py <run_dir>
"""
import json, os, sys
import numpy as np
import pyvista as pv
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ens_frames import available_frames

pv.OFF_SCREEN = True
RUN = sys.argv[1]
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FIG = os.path.join(ROOT, "figures"); POST = os.path.join(RUN, "post")
SP = os.environ["SP"]
plt.rcParams.update({"font.family": "serif", "font.size": 9})
GREY, ACCENT = "#9aa5b1", "#b23a48"

# ---------- (a) CT slice with the segmentation ----------
vol = np.load(f"{SP}/ct.npy"); meta = np.load(f"{SP}/ct_meta.npy"); sp, org = meta[:3], meta[3:]
seg = np.load(f"{SP}/seg_filled.npy"); dev = np.load(f"{SP}/device.npy")
kc = int(np.argwhere(dev)[:, 2].mean())
ij = np.argwhere(seg[:, :, kc]); i0, j0 = ij.min(0) - 25; i1, j1 = ij.max(0) + 25
ct_img = vol[i0:i1, j0:j1, kc].T; seg_img = seg[i0:i1, j0:j1, kc].T; dev_img = dev[i0:i1, j0:j1, kc].T

# ---------- (b) 3D model with zones and the device ----------
s = np.load(os.path.join(ROOT, "data", "derived_cyl", "LA_surface_Zaligned_mm_indexed.npz"))
V, F, Z = s["V"], s["F"], s["zone"]
surf = pv.PolyData(V, np.c_[np.full(len(F), 3), F].ravel())
surf.cell_data["zone"] = Z
dev_sim = np.load(os.path.join(POST, "device_sim_m.npy")) * 1000
dc = dev_sim.mean(0)
view = dc - V.mean(0); view[2] = 0; view /= np.linalg.norm(view)
cam = [tuple(V.mean(0) + view * 260 + np.array([0, 0, 60])), tuple(V.mean(0)), (0, 0, 1)]
names = ["wall", "MV", "PV", "PV", "PV", "PV", "wall", "MV tube"]
colors = ["#d9d4cc", "#2f6db5", "#e0a030", "#e0a030", "#e0a030", "#e0a030", "#d9d4cc", "#7fa7d9"]
p = pv.Plotter(off_screen=True, window_size=(800, 800)); p.set_background("white")
for z in np.unique(Z):
    p.add_mesh(surf.extract_cells(np.where(Z == z)[0]), color=colors[z], smooth_shading=True)
p.add_points(dev_sim, color="black", point_size=3)
p.camera_position = cam
img_model = p.screenshot(return_img=True); p.close()

# ---------- (c) volume mesh cut ----------
reader = pv.EnSightReader(os.path.join(RUN, "LA_Case001_ens.encas"))
times = np.array(reader.time_values); i = available_frames(RUN)[0]
reader.set_active_time_value(times[i]); mb = reader.read()
fl = mb[[mb.get_block_name(k) for k in range(mb.n_blocks)].index("fluid")]
fl = fl.scale(1000)
n = np.cross(view, [0, 0, 1.0])
cut = fl.clip(normal=n, origin=dc, crinkle=True)
p = pv.Plotter(off_screen=True, window_size=(800, 800)); p.set_background("white")
p.add_mesh(cut, color="#f2efe9", show_edges=True, edge_color="#555555", line_width=0.3)
p.camera_position = [tuple(dc + n * 260 + np.array([0, 0, 40])), tuple(V.mean(0)), (0, 0, 1)]
img_mesh = p.screenshot(return_img=True); p.close()


def crop(img):
    m = (img < 250).any(2); r = np.where(m.any(1))[0]; c = np.where(m.any(0))[0]
    return img[max(r[0] - 5, 0):r[-1] + 5, max(c[0] - 5, 0):c[-1] + 5]


img_flow = plt.imread(os.path.join(FIG, "cfd_vel_Epeak.png"))[:, :, :3]
img_flow = (img_flow * 255).astype(np.uint8)[60:560, 90:690]

fig, ax = plt.subplots(1, 4, figsize=(7.2, 2.1))
ax[0].imshow(np.clip(ct_img, -150, 800), cmap="gray", origin="lower")
ax[0].contour(seg_img, [0.5], colors=ACCENT, linewidths=0.8)
ax[0].contour(dev_img, [0.5], colors="#f4d35e", linewidths=0.8)
for a, im in zip(ax[1:], [crop(img_model), crop(img_mesh), img_flow]):
    a.imshow(im)
titles = ["(a) CT + segmentation", "(b) 3D model", "(c) volume mesh", "(d) simulated flow"]
for a, t in zip(ax, titles):
    a.set_title(t, fontsize=8.5); a.axis("off")
for k in range(3):
    fig.text(0.255 + 0.245 * k, 0.5, "→", fontsize=16, ha="center", va="center", color="#444")
plt.subplots_adjust(left=0.01, right=0.99, top=0.88, bottom=0.02, wspace=0.18)
plt.savefig(os.path.join(FIG, "fig_pipeline.png"), dpi=300)
plt.close()

# ---------- key numbers: device region vs whole LA ----------
ts = json.load(open(os.path.join(POST, "timeseries.json")))
c2 = [r for r in ts if r["t"] > 0.875]
u_la = np.mean([r["umean_ms"] for r in c2]) * 100
u_dev = np.mean([r["u_near_device_ms"] for r in c2]) * 100
wss = json.load(open(os.path.join(POST, "wss_summary.json")))
wo = np.load(os.path.join(POST, "washout.npz"))
X0, te = wo["X0"], wo["t_exit"]
near = np.linalg.norm(X0 - dev_sim.mean(0) / 1000, axis=1) < 0.012
rem_la, rem_dev = np.mean(te > 3 * 0.875) * 100, np.mean(te[near] > 3 * 0.875) * 100
w = pv.read(os.path.join(POST, "wall_indices_cycle2.vtk"))
osi_la = float(np.median(w.point_data["OSI"]))
panels = [("Mean blood speed\n(cm/s)", u_la, u_dev, "{:.1f}"),
          ("Blood still inside\nafter 3 beats (%)", rem_la, rem_dev, "{:.0f}"),
          ("ECAP, wall\n(1/Pa)", wss["wall_ECAP_median"], wss["device_ECAP_median"], "{:.2f}"),
          ("OSI, wall\n(-)", osi_la, wss["device_OSI_median"], "{:.2f}")]
fig, ax = plt.subplots(1, 4, figsize=(7.2, 1.9))
for a, (t, v_la, v_dev, fmt) in zip(ax, panels):
    b = a.bar([0, 1], [v_la, v_dev], color=[GREY, ACCENT], width=0.62)
    for x, v in zip([0, 1], [v_la, v_dev]):
        a.text(x, v * 1.02, fmt.format(v), ha="center", va="bottom", fontsize=8.5)
    a.set_xticks([0, 1]); a.set_xticklabels(["whole LA", "near device"], fontsize=8)
    a.set_title(t, fontsize=8.5); a.set_yticks([])
    for side in ["top", "right", "left"]:
        a.spines[side].set_visible(False)
    a.set_ylim(0, max(v_la, v_dev) * 1.25)
plt.subplots_adjust(left=0.01, right=0.99, top=0.78, bottom=0.14, wspace=0.25)
plt.savefig(os.path.join(FIG, "fig_keynumbers.png"), dpi=300)
print(dict(u_la=u_la, u_dev=u_dev, rem_la=rem_la, rem_dev=rem_dev, osi_la=osi_la))

# ---------- column-width 2x2 version of the key numbers ----------
fig, ax = plt.subplots(1, 4, figsize=(3.4, 1.55))
short = ["Speed\n(cm/s)", "Left after\n3 beats (%)", "ECAP\n(1/Pa)", "OSI\n(-)"]
for a, (t, v_la, v_dev, fmt), st in zip(ax.ravel(), panels, short):
    a.bar([0, 1], [v_la, v_dev], color=[GREY, ACCENT], width=0.7)
    for x, v in zip([0, 1], [v_la, v_dev]):
        a.text(x, v * 1.02, fmt.format(v), ha="center", va="bottom", fontsize=6.8)
    a.set_xticks([0, 1]); a.set_xticklabels(["LA", "dev."], fontsize=7)
    a.set_title(st, fontsize=7.2); a.set_yticks([])
    for side in ["top", "right", "left"]:
        a.spines[side].set_visible(False)
    a.set_ylim(0, max(v_la, v_dev) * 1.3)
plt.subplots_adjust(left=0.02, right=0.98, top=0.76, bottom=0.12, wspace=0.25)
plt.savefig(os.path.join(FIG, "fig_keynumbers_col.png"), dpi=300)

# ---------- we crop the white margins of the 3D renders for the paper ----------
from PIL import Image
for name in ["cfd_vel_Epeak", "cfd_vel_diastasis", "cfd_ecap"]:
    im = np.asarray(Image.open(os.path.join(FIG, name + ".png")).convert("RGB"))
    m = (im < 245).any(2); r = np.where(m.any(1))[0]; c = np.where(m.any(0))[0]
    Image.fromarray(im[r[0]:r[-1] + 1, c[0]:c[-1] + 1]).save(os.path.join(FIG, name + "_crop.png"))
print("paper figures written")

# ---------- column-width figure: speed over time and washout ----------
t = np.array([r["t"] for r in ts])
fig, ax = plt.subplots(2, 1, figsize=(3.4, 2.3))
ax[0].plot(t, [r["umean_ms"] * 100 for r in ts], color=GREY, lw=1.6, label="whole LA")
ax[0].plot(t, [r["u_near_device_ms"] * 100 for r in ts], color=ACCENT, lw=1.6, label="near device")
ax[0].axvspan(0.875, 1.75, color="#f3f1ec", zorder=0); ax[0].text(1.31, 33, "analysed beat", ha="center", fontsize=7, color="#666")
ax[0].set_xlabel("time (s)", fontsize=8); ax[0].set_ylabel("speed (cm/s)", fontsize=8); ax[0].set_ylim(0, 37)
rem = wo["remain"]; tt = rem[:, 0]
ax[1].plot(tt / 0.875, rem[:, 1] * 100, color=GREY, lw=1.6, label="whole LA")
ax[1].plot(tt / 0.875, [(te[near] > x).mean() * 100 for x in tt], color=ACCENT, lw=1.6, label="near device")
ax[1].set_xlabel("heartbeats after release", fontsize=8); ax[1].set_ylabel("left inside (%)", fontsize=8); ax[1].set_ylim(0, 105)
ax[1].legend(fontsize=7, frameon=False)
for a in ax:
    a.tick_params(labelsize=7.5)
    for side in ["top", "right"]:
        a.spines[side].set_visible(False)
plt.tight_layout(h_pad=0.8)
plt.savefig(os.path.join(FIG, "fig_flow_col.png"), dpi=300)
print("flow column figure written")
