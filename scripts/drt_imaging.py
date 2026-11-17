"""We look for device-related thrombus (DRT) on the CT: hypoattenuated tissue on the atrial face of the occluder.

For lines parallel to the device axis (spacing 0.5 mm over the device disc) we walk from the LA blood pool
toward the device and measure the thickness of tissue with HU < 250 right before the first metal voxel (HU > 700).
Contrast blood in this scan is ~490 HU (5-95 %: 400-585), so a thrombus would appear as a low-HU layer.
Output: figures/drt_imaging.png, results/drt_imaging.json
"""
import json, os
import numpy as np
from scipy import ndimage as ndi
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

SP = os.environ["SP"]
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
vol = np.load(f"{SP}/ct.npy"); meta = np.load(f"{SP}/ct_meta.npy"); sp, org = meta[:3], meta[3:]
seg = np.load(f"{SP}/seg_filled.npy"); dev = np.load(f"{SP}/device.npy")
P = org + np.argwhere(dev) * sp
c = P.mean(0)
# device axis: normal of the flat device face (Marc's Meshmixer cap, RAS -> LPS), pointing from LA into LAA
n = np.array([0.674, -0.18, 0.716]) * np.array([1, 1, 1]); n /= np.linalg.norm(n)
e1 = np.cross(n, [0, 0, 1.0]); e1 /= np.linalg.norm(e1); e2 = np.cross(n, e1)


def sample(points, arr=vol, order=1):
    return ndi.map_coordinates(arr, ((points - org) / sp).T, order=order, mode="nearest")


s_line = np.arange(-15, 10, 0.25)
rad = 11.0
grid = np.arange(-rad, rad + 0.01, 0.5)
thick = np.full((len(grid), len(grid)), np.nan)
blood_gap = np.full_like(thick, np.nan)
for a, u in enumerate(grid):
    for b, v in enumerate(grid):
        if u * u + v * v > rad * rad:
            continue
        L = c + u * e1[None] * 0 + 0  # placeholder to keep shapes clear
        pts = c[None] + u * e1[None] + v * e2[None] + s_line[:, None] * n[None]
        hu = sample(pts)
        metal = np.where(hu > 700)[0]
        if len(metal) == 0:
            continue
        m0 = metal[0]
        blood = np.where(hu[:m0] > 350)[0]
        if len(blood) == 0:
            continue
        b_last = blood[-1]
        # tissue between last contrast-blood sample and the metal
        seg_hu = hu[b_last + 1:m0]
        thick[a, b] = np.sum(seg_hu < 250) * 0.25
        blood_gap[a, b] = (m0 - b_last - 1) * 0.25
valid = ~np.isnan(thick)
res = dict(lines_with_metal=int(valid.sum()),
           hypo_thickness_mm_median=float(np.nanmedian(thick)), hypo_thickness_mm_p95=float(np.nanpercentile(thick, 95)),
           hypo_thickness_mm_max=float(np.nanmax(thick)),
           frac_lines_hypo_ge_3mm=float((thick[valid] >= 3).mean()),
           blood_to_metal_gap_mm_median=float(np.nanmedian(blood_gap)))
print(json.dumps(res, indent=1))
os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
json.dump(res, open(os.path.join(ROOT, "results", "drt_imaging.json"), "w"), indent=1)


def plane(center, a, b, half=28, step=0.2):
    s = np.arange(-half, half, step)
    S1, S2 = np.meshgrid(s, s, indexing="ij")
    Q = center[None, None] + a[None, None] * S1[..., None] + b[None, None] * S2[..., None]
    I = sample(Q.reshape(-1, 3)).reshape(S1.shape)
    G = sample(Q.reshape(-1, 3), seg.astype(np.float32)).reshape(S1.shape)
    return s, I, G


fig, ax = plt.subplots(1, 4, figsize=(13.5, 3.6))
for k, (A, B, title) in enumerate([(n, e1, "Long axis (device plane 1)"), (n, e2, "Long axis (device plane 2)"),
                                    (e1, e2, "En face, at the hub")]):
    s, I, G = plane(c, A, B)
    ax[k].imshow(np.clip(I, -150, 800).T, cmap="gray", origin="lower", extent=[s[0], s[-1], s[0], s[-1]])
    ax[k].contour(s, s, G.T, [0.5], colors="#e74c3c", linewidths=0.9)
    ax[k].set_title(title, fontsize=9)
    ax[k].set_xticks([]); ax[k].set_yticks([])
    if k < 2:
        ax[k].annotate("LA", (-20, 15), color="w", fontsize=9)
        ax[k].annotate("LAA (no contrast)", (4, -22), color="w", fontsize=8)
ax[0].plot([-20, -10], [-25, -25], "w-", lw=2); ax[0].annotate("10 mm", (-20, -23.5), color="w", fontsize=7)
im = ax[3].imshow(thick.T, origin="lower", extent=[-rad, rad, -rad, rad], cmap="magma", vmin=0, vmax=4)
ax[3].set_title("Low-HU tissue on atrial face (mm)", fontsize=9)
ax[3].set_xlabel("mm"); plt.colorbar(im, ax=ax[3], fraction=0.046)
plt.tight_layout()
plt.savefig(os.path.join(ROOT, "figures", "drt_imaging.png"), dpi=200)
