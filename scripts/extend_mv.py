"""We extrude the mitral valve (MV) outline straight along -Z (the MV motion axis).

The MV cap moves 8.9 mm along Z. Right above the annulus the LA wall flares out, so when the
MV moves back up the cells between the rim and the wall get crushed (negative volumes in Fluent).
With a straight tube the moving cap slides along a surface parallel to its motion and stays away
from the irregular annulus.
Usage: python extend_mv.py <length_mm> <ring_spacing_mm> <in_dir> <out_dir>
"""
import json, os, shutil, sys
import numpy as np
import trimesh

L = float(sys.argv[1]); H = float(sys.argv[2]); IN = sys.argv[3]; OUT = sys.argv[4]
os.makedirs(OUT, exist_ok=True)
s = np.load(f"{IN}/LA_surface_Zaligned_mm_indexed.npz")
V, F, Z = s["V"].astype(float), s["F"].copy(), s["zone"].copy()
MV = 1

# we find the MV boundary loop (edges used by only one MV triangle) and order it
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
assert len(loop) == len(b), "MV boundary is not a single loop"
print("MV rim nodes:", len(loop), "rim z range:", V[loop, 2].min(), V[loop, 2].max())

# we keep the outward orientation: the wall triangle on each rim edge tells us the edge direction
wall_dir = {}
for t in F[Z != MV]:
    for a, c in [(t[0], t[1]), (t[1], t[2]), (t[2], t[0])]:
        wall_dir[(a, c)] = True
# in the wall, the rim edge goes a->c; the new tube triangles must use it as c->a
a0, a1 = loop[0], loop[1]
if (a0, a1) in wall_dir:
    loop = loop[::-1]  # we want the wall to have (loop[k+1], loop[k]) so the tube uses (loop[k], loop[k+1])

# we build the rings at z = -H, -2H, ..., -L
nr = int(round(L / H))
rings = [loop]
newV = [V]
nV = len(V)
for k in range(1, nr + 1):
    P = V[loop].copy(); P[:, 2] = -L * k / nr
    rings.append(np.arange(nV, nV + len(loop))); nV += len(loop); newV.append(P)
V2 = np.vstack(newV)
side = []
n = len(loop)
for k in range(nr):
    r0, r1 = rings[k], rings[k + 1]
    for i in range(n):
        j = (i + 1) % n
        side += [[r0[i], r0[j], r1[j]], [r0[i], r1[j], r1[i]]]
side = np.array(side)

# we move the MV cap to the end of the tube (rim nodes -> last ring, inner nodes shifted by -L)
last = dict(zip(loop, rings[-1]))
capF = F[Z == MV].copy()
inner = np.setdiff1d(np.unique(capF), loop)
V2[inner, 2] -= L
capF = np.vectorize(lambda x: last.get(x, x))(capF)
F2 = np.r_[F[Z != MV], side, capF]
Z2 = np.r_[Z[Z != MV], np.zeros(len(side), int), np.full(len(capF), MV)]

m = trimesh.Trimesh(V2, F2, process=False)
print("watertight:", m.is_watertight, "winding consistent:", m.is_winding_consistent, "volume mL:", m.volume / 1000)
# we check the side wall orientation: tube normals must point away from the axis
c = V2[loop].mean(0)
tn = m.face_normals[len(F[Z != MV]):len(F[Z != MV]) + len(side)]
tc = m.triangles_center[len(F[Z != MV]):len(F[Z != MV]) + len(side)]
radial = tc - c; radial[:, 2] = 0
print("tube normals outward fraction:", float(((tn * radial).sum(1) > 0).mean()))
np.savez(f"{OUT}/LA_surface_Zaligned_mm_indexed.npz", V=V2, F=F2, zone=Z2)
for f in ["transform.json"]:
    shutil.copy(f"{IN}/{f}", f"{OUT}/{f}")
T = json.load(open(f"{OUT}/transform.json")); T["mv_extension_mm"] = L
json.dump(T, open(f"{OUT}/transform.json", "w"), indent=1)
m.export(f"{OUT}/LA_surface_Zaligned_mm.stl")
print("written", OUT)
