"""We build the processed LA surface: clean segmentation -> smooth field -> planar PV/MV cuts -> remesh -> Z-align.

Inputs (scratch): seg_filled.npy, device.npy, ct_meta.npy, caps_mesh01.npy (cut planes Marc chose in Meshmixer, RAS).
Outputs: data/derived/LA_surface_LPSmm.stl, LA_surface_Zaligned_mm.stl, transform.json, face_labels.npy
"""
import json, os, sys
import numpy as np
from scipy import ndimage as ndi
from skimage import measure
import trimesh, pymeshlab

SP = os.environ["SP"]
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "derived")
os.makedirs(OUT, exist_ok=True)
TARGET_EDGE = float(sys.argv[1]) if len(sys.argv) > 1 else 1.5  # mm

meta = np.load(f"{SP}/ct_meta.npy")
sp, org = meta[:3], meta[3:]
seg = np.load(f"{SP}/seg_filled.npy")
dev = np.load(f"{SP}/device.npy")

# we keep only the largest component, remove device (+1 voxel) and fill holes
seg = seg & ~ndi.binary_dilation(dev, iterations=1)
lab, n = ndi.label(seg)
sz = np.bincount(lab.ravel()); sz[0] = 0
seg = lab == np.argmax(sz)
seg = ndi.binary_fill_holes(seg)

# we crop to the LA box (+12 voxels) to save memory
bb = ndi.find_objects(seg.astype(np.uint8))[0]
bb = tuple(slice(max(s.start - 12, 0), min(s.stop + 12, seg.shape[k])) for k, s in enumerate(bb))
seg_c = seg[bb]
o2 = org + np.array([s.start for s in bb]) * sp

# cut planes in LPS from Marc's Meshmixer caps (RAS -> LPS flips x and y)
caps = np.load(f"{SP}/caps_mesh01.npy")
F = np.array([-1, -1, 1])
# we move two planes slightly toward the LA (mm) so each cut is one smooth convex lumen
OFFSETS = {"mv": -1.5, "pv_li": -4.0}
names = {1: "mv", 3: "pv_rs", 5: "pv_ri", 6: "pv_ls", 4: "pv_li"}
planes = {}
for k, name in names.items():
    A = caps[k, 0]
    nn = caps[k, 4:7] * F / np.linalg.norm(caps[k, 4:7])
    planes[name] = dict(c=caps[k, 1:4] * F + OFFSETS.get(name, 0.0) * nn, n=nn, r=np.sqrt(A / np.pi))

def cut_field(mask):
    """We smooth the mask (sigma 0.6 mm) and apply the planar cuts as a min() with a plane ramp."""
    f = ndi.gaussian_filter(mask.astype(np.float32), sigma=0.6 / sp)
    gi = [np.arange(s.stop - s.start) * sp[k] + o2[k] for k, s in enumerate(bb)]
    X, Y, Z = np.meshgrid(*gi, indexing="ij")
    w = 0.5  # mm, ramp width of the plane field
    for name, p in planes.items():
        d = (X - p["c"][0]) * p["n"][0] + (Y - p["c"][1]) * p["n"][1] + (Z - p["c"][2]) * p["n"][2]
        beyond = d > 0
        # distance from the cap axis, to pick only the vessel part right behind the cap
        vx, vy, vz = X - p["c"][0], Y - p["c"][1], Z - p["c"][2]
        rad = np.sqrt(np.maximum(vx**2 + vy**2 + vz**2 - d**2, 0))
        seed = beyond & (mask) & (rad < 1.3 * p["r"]) & (d < 2.0)
        comp_lab, _ = ndi.label(beyond & mask)
        ids = np.unique(comp_lab[seed]); ids = ids[ids > 0]
        region = np.isin(comp_lab, ids)
        region = ndi.binary_dilation(region, iterations=4) & (d > -1.5)
        q = 0.5 - d / (2 * w)
        f = np.where(region, np.minimum(f, q), f)
        print(name, "removed voxels", int((region & mask).sum()), "cap radius mm", round(p["r"], 1))

    return f


f = cut_field(seg_c)

# we remove blind-ended thin side branches (stubs) that are not cut: they would trap stagnant flow
inside = f > 0.5
rv = np.ceil(2.3 / sp).astype(int)  # we use a 2.3 mm radius ball in physical units
gg = np.meshgrid(*[np.arange(-q, q + 1) * sp[k] for k, q in enumerate(rv)], indexing="ij")
ball = (gg[0] ** 2 + gg[1] ** 2 + gg[2] ** 2) <= 2.3 ** 2
opened = ndi.binary_opening(inside, structure=ball)
thin = inside & ~opened
tl, tn_ = ndi.label(thin)
cap_c = np.array([p["c"] for p in planes.values()])
stub = np.zeros_like(inside)
for i in range(1, tn_ + 1):
    idx = np.argwhere(tl == i)
    if len(idx) * sp.prod() < 20:
        continue
    cen = o2 + idx.mean(0) * sp
    if np.min(np.linalg.norm(cap_c - cen, axis=1)) > 12:
        stub |= tl == i
        print("stub removed at LPS", np.round(cen, 1), "volume mm3", round(len(idx) * sp.prod(), 1))
stub = ndi.binary_dilation(stub, iterations=2) & ~ndi.binary_erosion(opened, iterations=1)
seg_c = seg_c & ~stub
lab2, _ = ndi.label(seg_c)
sz2 = np.bincount(lab2.ravel()); sz2[0] = 0
seg_c = lab2 == np.argmax(sz2)
f = cut_field(seg_c)
np.save(f"{SP}/seg_final_crop.npy", seg_c)
json.dump(dict(start=[s.start for s in bb], stop=[s.stop for s in bb]), open(f"{SP}/seg_final_bb.json", "w"))

verts, faces, _, _ = measure.marching_cubes(f, 0.5, spacing=tuple(sp))
verts = verts + o2
m = trimesh.Trimesh(verts, faces, process=True)
parts = m.split(only_watertight=False)
m = max(parts, key=lambda t: len(t.faces))
print("marching cubes:", len(m.faces), "tris, watertight", m.is_watertight, "vol mL", m.volume / 1000)

# we remesh isotropically and keep the sharp cap edges (feature angle 45 deg)
ms = pymeshlab.MeshSet()
ms.add_mesh(pymeshlab.Mesh(m.vertices, m.faces))
ms.meshing_isotropic_explicit_remeshing(targetlen=pymeshlab.PureValue(TARGET_EDGE), iterations=8,
                                        featuredeg=45, checksurfdist=True,
                                        maxsurfdist=pymeshlab.PureValue(0.2))
ms.meshing_remove_duplicate_vertices()
ms.meshing_repair_non_manifold_edges()
ms.meshing_close_holes(maxholesize=50)
ms.meshing_re_orient_faces_coherently()
mm = ms.current_mesh()
m = trimesh.Trimesh(mm.vertex_matrix(), mm.face_matrix(), process=True)
m = max(m.split(only_watertight=False), key=lambda t: len(t.faces))
trimesh.repair.fix_normals(m)
print("remeshed:", len(m.faces), "tris, watertight", m.is_watertight, "winding ok", m.is_winding_consistent,
      "vol mL", round(m.volume / 1000, 1), "euler", m.euler_number)

# we snap vertices close to each cut plane onto it, so caps are exactly flat with a crisp edge
def snap(V):
    V = V.copy()
    for name, p in planes.items():
        d = (V - p["c"]) @ p["n"]
        rad = np.linalg.norm((V - p["c"]) - np.outer(d, p["n"]), axis=1)
        sel = (np.abs(d) < 0.6) & (rad < 1.8 * p["r"])
        V[sel] -= np.outer(d[sel], p["n"])
    return V


V = snap(m.vertices)
# snapping can create slivers: we merge vertices closer than 0.25 mm, drop null faces, snap again
ms = pymeshlab.MeshSet()
ms.add_mesh(pymeshlab.Mesh(V, m.faces))
ms.meshing_merge_close_vertices(threshold=pymeshlab.PureValue(0.25))
ms.meshing_remove_null_faces()
ms.meshing_remove_duplicate_faces()
ms.meshing_remove_unreferenced_vertices()
ms.meshing_repair_non_manifold_edges()
# a short feature-preserving remesh removes the slivers; the 90 deg cap edges are kept
ms.meshing_isotropic_explicit_remeshing(targetlen=pymeshlab.PureValue(TARGET_EDGE), iterations=3,
                                        featuredeg=40, checksurfdist=True,
                                        maxsurfdist=pymeshlab.PureValue(0.1))
mm = ms.current_mesh()
V = snap(mm.vertex_matrix())
F_ = mm.face_matrix()
m = trimesh.Trimesh(V, F_, process=False)
print("after snap+clean:", len(m.faces), "tris, watertight", m.is_watertight, "winding", m.is_winding_consistent,
      "vol mL", round(m.volume / 1000, 1))

# triangle quality: minimum angle
tri = m.triangles
def min_angle(t):
    e = [t[:, 1] - t[:, 0], t[:, 2] - t[:, 1], t[:, 0] - t[:, 2]]
    angs = []
    for i in range(3):
        u, v = -e[i - 1], e[i]
        angs.append(np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", u, v) / (np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1)), -1, 1))))
    return np.min(angs, axis=0)
ma_ = min_angle(tri)
print("triangle min angle: min %.1f deg, 1st pct %.1f, faces < 15 deg: %d" % (ma_.min(), np.percentile(ma_, 1), (ma_ < 15).sum()))

# we label faces geometrically: all 3 vertices on the plane and normal along the plane normal
lab_f = np.zeros(len(m.faces), int)  # 0 = wall
zone_names = ["wall"] + list(planes.keys())
tc, tn = m.triangles_center, m.face_normals
for zi, (name, p) in enumerate(planes.items(), start=1):
    dv = np.abs((m.vertices - p["c"]) @ p["n"])
    rad = np.linalg.norm((tc - p["c"]) - np.outer((tc - p["c"]) @ p["n"], p["n"]), axis=1)
    on = (dv[m.faces] < 1e-6).all(axis=1) & ((tn @ p["n"]) > 0.9) & (rad < 1.8 * p["r"])
    lab_f[on] = zi
m.export(f"{OUT}/LA_surface_LPSmm.stl")
np.savez(f"{OUT}/LA_surface_LPSmm_indexed.npz", V=m.vertices, F=m.faces, zone=lab_f)
for zi, name in enumerate(zone_names):
    sel = lab_f == zi
    print(f"zone {name:6s} faces {sel.sum():6d} area {m.area_faces[sel].sum():8.1f} mm2")

# Z alignment: MV outward normal -> -Z, MV centroid -> origin
mvn = planes["mv"]["n"]
mvc = (tc[lab_f == 1] * m.area_faces[lab_f == 1, None]).sum(0) / m.area_faces[lab_f == 1].sum()
target = np.array([0, 0, -1.0])
v = np.cross(mvn, target); s = np.linalg.norm(v); c = mvn @ target
vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
R = np.eye(3) + vx + vx @ vx * ((1 - c) / s**2)
Xa = (m.vertices - mvc) @ R.T
ma = trimesh.Trimesh(Xa, m.faces, process=False)
print("aligned bbox mm", np.round(ma.bounds, 1).tolist())
print("MV normal after", np.round(R @ mvn, 4))

ma.export(f"{OUT}/LA_surface_Zaligned_mm.stl")
np.save(f"{OUT}/face_labels.npy", lab_f)
np.savez(f"{OUT}/LA_surface_Zaligned_mm_indexed.npz", V=Xa, F=m.faces, zone=lab_f)
json.dump(dict(zone_names=zone_names, R=R.tolist(), mv_centre_LPS=mvc.tolist(),
               planes={k: dict(c=v_["c"].tolist(), n=v_["n"].tolist(), r=float(v_["r"])) for k, v_ in planes.items()},
               note="aligned = R @ (x_LPS - mv_centre_LPS); MV outward normal -> -Z"),
          open(f"{OUT}/transform.json", "w"), indent=1)
