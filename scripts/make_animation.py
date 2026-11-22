"""We make the animated GIF of the README: blood speed on a plane through the occluder over the second heartbeat,
with the mitral valve (MV) velocity profile underneath and a dot that follows the time.

Usage: python make_animation.py <reduced.encas> <device.stl (RAS mm)> <transform.json> <MV velocity .prof> <out.gif>
The .encas lists only velocity_magnitude and velocity for the frames we want (see README, "Reproduce").
"""
import json, sys
import numpy as np
import pyvista as pv
import trimesh
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.colorbar import ColorbarBase
from PIL import Image

pv.OFF_SCREEN = True
encas, dev_stl, tr_json, prof, out = sys.argv[1:6]
plt.rcParams.update({"font.family": "serif", "font.size": 8})

# we put the device in the simulation frame: RAS -> LPS (flip x, y), then the same rotation and shift as the model
T = json.load(open(tr_json))
R, mvc = np.array(T["R"]), np.array(T["mv_centre_LPS"])
v = trimesh.load(dev_stl).vertices * np.array([-1.0, -1.0, 1.0])
dev = ((v - mvc) @ R.T) / 1000.0
dc = dev.mean(0)

# we cut the blood with a plane that contains the device and the Z axis (the valve motion axis)
d = dc.copy(); d[2] = 0; d /= np.linalg.norm(d)
normal = np.cross(d, [0, 0, 1.0]); normal /= np.linalg.norm(normal)
cam = [tuple(dc + normal * 0.25), tuple(dc * np.array([0.5, 0.5, 1])), (0, 0, 1)]

reader = pv.EnSightReader(encas)
times = np.array(reader.time_values)
renders = []
for t in times:
    reader.set_active_time_value(t)
    mb = reader.read()
    names = [mb.get_block_name(i) for i in range(mb.n_blocks)]
    sl = mb[names.index("fluid")].slice(normal=normal, origin=dc)
    p = pv.Plotter(off_screen=True, window_size=(900, 900)); p.set_background("white")
    p.add_mesh(mb[names.index("wall")], color="lightgray", opacity=0.12)
    p.add_mesh(sl, scalars="velocity_magnitude", cmap="turbo", clim=[0, 0.6], show_scalar_bar=False)
    p.add_points(dev, color="black", point_size=2)
    p.camera_position = cam
    renders.append(p.screenshot(return_img=True)); p.close()

# we crop all frames with the same box, so that nothing jumps
mask = np.zeros(renders[0].shape[:2], bool)
for im in renders:
    mask |= (im < 245).any(2)
r_, c_ = np.where(mask.any(1))[0], np.where(mask.any(0))[0]
H, W = mask.shape
box = (max(r_[0] - 6, 0), min(r_[-1] + 6, H), max(c_[0] - 6, 0), min(c_[-1] + 6, W))  # we keep the box inside the picture

# MV velocity profile of the course (negative = outflow through the valve), we plot its size
rows = [l.split() for l in open(prof) if l.strip() and l.split()[0].replace(".", "", 1).replace("e-", "", 1).replace("-", "", 1).isdigit()]
tp, up = np.array([[float(a), abs(float(b))] for a, b in rows]).T

frames = []
for t, im in zip(times, renders):
    im = im[box[0]:box[1], box[2]:box[3]]
    fig = plt.figure(figsize=(4.4, 5.3), dpi=110)
    ax = fig.add_axes([0.0, 0.30, 1.0, 0.66]); ax.imshow(im); ax.axis("off")
    fig.text(0.5, 0.965, f"Blood speed on a plane through the device, t = {t:.2f} s", ha="center", fontsize=8.5)
    cax = fig.add_axes([0.2, 0.245, 0.6, 0.018])
    ColorbarBase(cax, cmap=plt.get_cmap("turbo"), norm=Normalize(0, 0.6), orientation="horizontal")
    cax.set_xlabel("m/s", fontsize=7.5); cax.tick_params(labelsize=7)
    bx = fig.add_axes([0.14, 0.07, 0.80, 0.11])
    sel = tp >= 0.875
    bx.plot(tp[sel], up[sel], color="#9aa5b1", lw=1.4)
    bx.plot(tp[(tp >= 0.875) & (tp <= t)], up[(tp >= 0.875) & (tp <= t)], color="#b23a48", lw=1.8)
    bx.plot([t], [np.interp(t, tp, up)], "o", color="#b23a48", ms=4)
    bx.set_xlim(0.875, 1.75); bx.set_ylim(0, 1.05); bx.set_yticks([0, 0.5, 1]); bx.tick_params(labelsize=7)
    bx.set_xlabel("time (s)", fontsize=7.5); bx.set_ylabel("MV inflow (m/s)", fontsize=7.5)
    for side in ["top", "right"]:
        bx.spines[side].set_visible(False)
    fig.canvas.draw()
    frames.append(Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[:, :, :3]))
    plt.close(fig)

pal = [f.convert("P", palette=Image.ADAPTIVE, colors=256) for f in frames]
pal[0].save(out, save_all=True, append_images=pal[1:], duration=70, loop=0, optimize=True, disposal=2)
print("written", out, len(frames), "frames")
