"""We extend the mitral valve (MV) with a circular tube along -Z (the MV motion axis).

Why: with a 'faceted' deforming wall Fluent projects the moving nodes back onto the original surface.
The MV travels 8.9 mm beyond the end of that surface, so the wall nodes next to the rim get clamped,
pile up and invert when the MV comes back (negative volumes at t = 0.45-0.51 s in our first runs).
A circular tube can be declared as an infinite 'cylinder' in the dynamic mesh, so nodes are always
projected correctly, like a piston in a cylinder.

Geometry: MV outline (z = 0) -> loft to a circle of equal area (z = -T) -> straight cylinder to z = -L.
Zones: wall (LA), mv_loft (part of the LA wall, stationary), mv_tube (deforming cylinder), mv cap, PVs.
Usage: python extend_mv_cyl.py <loft_mm> <length_mm> <ring_spacing_mm> <in_dir> <out_dir>
"""
import json, os, sys
import numpy as np
import trimesh

T = float(sys.argv[1]); L = float(sys.argv[2]); H = float(sys.argv[3]); IN = sys.argv[4]; OUT = sys.argv[5]
os.makedirs(OUT, exist_ok=True)
s = np.load(f"{IN}/LA_surface_Zaligned_mm_indexed.npz")
V, F, Z = s["V"].astype(float), s["F"].copy(), s["zone"].copy()
meta = json.load(open(f"{IN}/transform.json"))
names = list(meta["zone_names"])  # [wall, mv, pv_rs, pv_ri, pv_ls, pv_li]
MV = names.index("mv")

# we find and order the MV boundary loop
cap = F[Z == MV]
E = np.sort(np.r_[cap[:, [0, 1]], cap[:, [1, 2]], cap[:, [2, 0]]], axis=1)
e, cnt = np.unique(E, axis=0, return_counts=True)
b = e[cnt == 1]
nb = {}
for i, j in b:
    nb.setdefault(i, []).append(j); nb.setdefault(j, []).append(i)
loop = [b[0][0]]; prev = None
while True:
    nxt = [k for k in nb[loop[-1]] if k != prev][0]
    if nxt == loop[0]:
        break
    prev = loop[-1]; loop.append(nxt)
loop = np.array(loop)
assert len(loop) == len(b)
wall_edges = set()
for t in F[Z != MV]:
    wall_edges |= {(t[0], t[1]), (t[1], t[2]), (t[2], t[0])}
if (loop[0], loop[1]) in wall_edges:
    loop = loop[::-1]

# we use the MV centroid as the tube axis and a circle with the same area as the MV cap
c = V[np.unique(cap)].mean(0); c[2] = 0.0
area = trimesh.Trimesh(V, cap, process=False).area
R = np.sqrt(area / np.pi)
P0 = V[loop] - c
th = np.arctan2(P0[:, 1], P0[:, 0]); r0 = np.hypot(P0[:, 0], P0[:, 1])
circle = np.c_[R * np.cos(th), R * np.sin(th)]
print(f"MV area {area:.1f} mm2 -> R {R:.2f} mm; outline r {r0.min():.1f}-{r0.max():.1f} mm; rim nodes {len(loop)}")

# rings: loft (smooth blend outline -> circle), then straight cylinder
n_loft = max(2, int(round(T / H))); n_tube = int(round((L - T) / H))
zs, ws = [], []
for k in range(1, n_loft + 1):
    s_ = k / n_loft
    zs.append(-T * s_); ws.append(0.5 - 0.5 * np.cos(np.pi * s_))
for k in range(1, n_tube + 1):
    zs.append(-T - (L - T) * k / n_tube); ws.append(1.0)
rings = [loop]; newV = [V]; nV = len(V)
for zk, wk in zip(zs, ws):
    xy = (1 - wk) * P0[:, :2] + wk * circle
    rings.append(np.arange(nV, nV + len(loop))); nV += len(loop)
    newV.append(np.c_[xy + c[:2], np.full(len(loop), zk)])
V2 = np.vstack(newV)
n = len(loop)


def band(r0_, r1_):
    out = []
    for i in range(n):
        j = (i + 1) % n
        out += [[r0_[i], r0_[j], r1_[j]], [r0_[i], r1_[j], r1_[i]]]
    return out


loftF = np.array(sum([band(rings[k], rings[k + 1]) for k in range(n_loft)], []))
tubeF = np.array(sum([band(rings[k], rings[k + 1]) for k in range(n_loft, n_loft + n_tube)], []))

# we map the old MV cap onto the circular end disk (radial stretch outline -> circle), z = -L
capV = np.unique(cap); inner = np.setdiff1d(capV, loop)
last = dict(zip(loop, rings[-1]))
Q = V[inner] - c
qa = np.arctan2(Q[:, 1], Q[:, 0])
# outline radius at the angle of each inner node (periodic interpolation)
o = np.argsort(th)
r_out = np.interp(qa, th[o], r0[o], period=2 * np.pi)
scale = R / r_out
V2[inner, 0] = c[0] + Q[:, 0] * scale
V2[inner, 1] = c[1] + Q[:, 1] * scale
V2[inner, 2] = -L
capF = np.vectorize(lambda x: last.get(x, x))(cap)

names2 = names + ["mv_loft", "mv_tube"]
F2 = np.r_[F[Z != MV], loftF, tubeF, capF]
Z2 = np.r_[Z[Z != MV], np.full(len(loftF), len(names)), np.full(len(tubeF), len(names) + 1), np.full(len(capF), MV)]
m = trimesh.Trimesh(V2, F2, process=False)
q = m.triangles
ed = np.linalg.norm(q[:, [1, 2, 0]] - q, axis=2)
ang = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', *(lambda a, b: (a / np.linalg.norm(a, axis=1)[:, None], b / np.linalg.norm(b, axis=1)[:, None]))(q[:, 1] - q[:, 0], q[:, 2] - q[:, 0])), -1, 1)))
print("watertight:", m.is_watertight, "winding:", m.is_winding_consistent, "volume mL:", round(m.volume / 1000, 2))
print("new triangles min edge mm:", ed[len(F[Z != MV]):].min().round(2), "max:", ed[len(F[Z != MV]):].max().round(2),
      "min angle (vertex 0) deg:", ang[len(F[Z != MV]):].min().round(1))
np.savez(f"{OUT}/LA_surface_Zaligned_mm_indexed.npz", V=V2, F=F2, zone=Z2)
meta["zone_names"] = names2
meta["mv_tube"] = dict(axis_point_mm=c.tolist(), radius_mm=float(R), loft_mm=T, length_mm=L)
json.dump(meta, open(f"{OUT}/transform.json", "w"), indent=1)
m.export(f"{OUT}/LA_surface_Zaligned_mm.stl")
print("tube axis point (m):", (c / 1000).round(6).tolist(), "radius (m):", round(R / 1000, 6))
