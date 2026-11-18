"""We fill the labelled, Z-aligned LA surface with tetrahedra (Gmsh + Netgen optimisation),
check Fluent-style quality, and write:
  - LA volume mesh .bdf (mm, Z-aligned)       -> deliverable / teacher import route
  - LA volume mesh .msh (Fluent ASCII, metres, named zones) -> our automated Fluent run
Usage: python build_volume.py <max interior size mm> <tag>
"""
import json, os, sys
import numpy as np
import gmsh

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fluent_msh as fm

D = os.environ.get("OUTDIR", os.path.join(HERE, "..", "data", "derived"))
HMAX = float(sys.argv[1]) if len(sys.argv) > 1 else 1.8
TAG = sys.argv[2] if len(sys.argv) > 2 else "v1"

s = np.load(f"{D}/LA_surface_Zaligned_mm_indexed.npz")
V, Fc, zone = s["V"], s["F"], s["zone"]
zone_names = json.load(open(f"{D}/transform.json"))["zone_names"]

gmsh.initialize()
gmsh.option.setNumber("General.Verbosity", 2)
gmsh.model.add("LA")
node_tags = np.arange(1, len(V) + 1)
surf_tags = []
for zi, name in enumerate(zone_names):
    tag = zi + 1
    gmsh.model.addDiscreteEntity(2, tag)
    surf_tags.append(tag)
# all nodes go on surface 1, triangles go on their own zone surface
gmsh.model.mesh.addNodes(2, 1, node_tags.tolist(), V.ravel().tolist())
etag = 1
for zi in range(len(zone_names)):
    tris = Fc[zone == zi]
    gmsh.model.mesh.addElementsByType(zi + 1, 2, list(range(etag, etag + len(tris))), (tris + 1).ravel().tolist())
    etag += len(tris)
gmsh.model.mesh.createTopology()
sl = gmsh.model.geo.addSurfaceLoop(surf_tags)
vtag = gmsh.model.geo.addVolume([sl])
gmsh.model.geo.synchronize()
gmsh.model.addPhysicalGroup(3, [vtag], 1, name="fluid")
gmsh.option.setNumber("Mesh.Algorithm3D", 1)          # Delaunay
gmsh.option.setNumber("Mesh.MeshSizeMax", HMAX)
gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 1)
gmsh.option.setNumber("Mesh.Optimize", 1)
gmsh.option.setNumber("Mesh.OptimizeNetgen", 1)       # as in the Lab 2 slides
gmsh.option.setNumber("Mesh.OptimizeThreshold", 0.4)
gmsh.model.mesh.generate(3)
gmsh.model.mesh.optimize("Netgen")
gmsh.model.mesh.optimize("", force=True)
gmsh.model.mesh.optimize("Netgen")

ntag, xyz, _ = gmsh.model.mesh.getNodes()
X = xyz.reshape(-1, 3)
idx = np.zeros(int(ntag.max()) + 1, int); idx[ntag.astype(int)] = np.arange(len(ntag))
_, etags, enodes = gmsh.model.mesh.getElements(3, vtag)
T = idx[np.array(enodes[0], int)].reshape(-1, 4)
print(f"tets {len(T)}, nodes {len(X)} (limit 500k elements)")

# BDF export (mm), volume only, exactly like the Lab 2 .geo (Physical Volume)
gmsh.option.setNumber("Mesh.SaveAll", 0)
gmsh.option.setNumber("Mesh.BdfFieldFormat", 1)  # small fields with more digits than default
bdf = f"{D}/LA_Case001_volume_{TAG}.bdf"
gmsh.write(bdf)
gmsh.finalize()

# ---- quality (Fluent definitions) ----
T, vol = fm.fix_tet_orientation(X, T)
a, b, c, d = (X[T[:, i]] for i in range(4))
# equilateral-volume skewness: 1 - V / V_equilateral(same circumradius)
A = np.stack([b - a, c - a, d - a], 1)
rhs = 0.5 * np.stack([(b - a) ** 2, (c - a) ** 2, (d - a) ** 2], 1).sum(-1)
cc = np.linalg.solve(A, rhs[..., None])[..., 0]
Rc = np.linalg.norm(cc, axis=1)
Veq = 8 * np.sqrt(3) / 27 * Rc**3
skew = 1 - vol / Veq
# orthogonal quality: min over faces of cos(face normal, centroid->face centroid) (and neighbour vectors)
cen = (a + b + c + d) / 4
fl, owner = fm.tet_faces(T)
fc = X[fl].mean(1)
nrm = np.cross(X[fl[:, 1]] - X[fl[:, 0]], X[fl[:, 2]] - X[fl[:, 0]])
cvec = fc - cen[owner]
oq_cell = np.einsum("ij,ij->i", nrm, cvec) / (np.linalg.norm(nrm, axis=1) * np.linalg.norm(cvec, axis=1))
oq = np.full(len(T), 1.0)
np.minimum.at(oq, owner, oq_cell)
# neighbour term
key = np.sort(fl, 1)
order = np.lexsort((key[:, 2], key[:, 1], key[:, 0]))
ks = key[order]
same = np.all(ks[1:] == ks[:-1], 1)
i0, i1 = order[:-1][same], order[1:][same]
dv = cen[owner[i1]] - cen[owner[i0]]
oq_n = np.abs(np.einsum("ij,ij->i", nrm[i0], dv)) / (np.linalg.norm(nrm[i0], axis=1) * np.linalg.norm(dv, axis=1))
np.minimum.at(oq, owner[i0], oq_n)
np.minimum.at(oq, owner[i1], oq_n)
edges = np.concatenate([np.linalg.norm(X[T[:, i]] - X[T[:, j]], axis=1) for i, j in [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]])
L = vol ** (1 / 3)
q = dict(tets=int(len(T)), nodes=int(len(X)), volume_mL=float(vol.sum() / 1000),
         skew_max=float(skew.max()), skew_p99=float(np.percentile(skew, 99)), n_skew_gt_0p9=int((skew > 0.9).sum()),
         n_skew_gt_0p8=int((skew > 0.8).sum()),
         orthoq_min=float(oq.min()), orthoq_p1=float(np.percentile(oq, 1)), n_orthoq_lt_0p1=int((oq < 0.1).sum()),
         edge_min_mm=float(edges.min()), edge_max_mm=float(edges.max()), edge_median_mm=float(np.median(edges)),
         cell_lengthscale_min_mm=float(L.min()), cell_lengthscale_max_mm=float(L.max()),
         min_volume_mm3=float(vol.min()))
print(json.dumps(q, indent=1))
json.dump(q, open(f"{D}/volume_quality_{TAG}.json", "w"), indent=1)

# ---- Fluent mesh (metres) with named zones ----
tri_zone = {tuple(t): z for t, z in zip(np.sort(Fc, 1).tolist(), zone.tolist())}
# gmsh node ids == our surface vertex ids for the first len(V) nodes? we map by coordinates to be safe
from scipy.spatial import cKDTree
tree = cKDTree(X)
used = np.unique(Fc)
dist_all, surf2vol_all = tree.query(V)
dist, surf2vol = dist_all[used], surf2vol_all[used]
print("surface node match max dist mm", dist.max(), "n>1e-6", int((dist > 1e-6).sum()))
assert dist.max() < 1e-6, "surface nodes moved"
vol2surf = -np.ones(len(X), int); vol2surf[surf2vol] = used


def zfn(sorted_tris):
    s_ = np.sort(vol2surf[sorted_tris], 1)
    return np.array([tri_zone.get(tuple(t), -1) for t in s_.tolist()])


types = ["velocity-inlet" if z == "mv" else "pressure-inlet" if z.startswith("pv") else "wall" for z in zone_names]
msh = f"{D}/LA_Case001_{TAG}.msh"
info = fm.write_msh(msh, X / 1000.0, T, zone_names, types, zfn)
print(info)
print(fm.check_msh(msh))
