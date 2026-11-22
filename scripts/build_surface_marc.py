"""We take Marc's Meshmixer surface (mesh01_clean_remeshed.stl, RAS mm), clean the degenerate triangles,
keep his cylinders and sharp cap edges, label the 5 caps, and align the MV normal with -Z.

Outputs in data/derived/: LA_surface_LPSmm.stl, LA_surface_Zaligned_mm.stl, *_indexed.npz, transform.json
"""
import json, os, sys
import numpy as np
import trimesh, pymeshlab

SP = os.environ["SP"]
SRC = os.environ.get("MESHMIXER_STL", "data/meshmixer/mesh01_clean_remeshed.stl")  # our hand-made Meshmixer surface (not in the repo)
OUT = os.environ.get("OUTDIR", os.path.join(os.path.dirname(__file__), "..", "data", "derived"))
os.makedirs(OUT, exist_ok=True)
TARGET_EDGE = float(sys.argv[1]) if len(sys.argv) > 1 else 1.3  # mm

# Marc's caps (we found them as exactly planar regions, RAS); index -> zone name
caps = np.load(f"{SP}/caps_mesh01.npy")
names = {1: "mv", 3: "pv_rs", 5: "pv_ri", 6: "pv_ls", 4: "pv_li"}
F = np.array([-1.0, -1.0, 1.0])  # RAS -> LPS (rotation by 180 deg about z, keeps orientation)
planes = {}
for k, name in names.items():
    nn = caps[k, 4:7] * F
    planes[name] = dict(c=caps[k, 1:4] * F, n=nn / np.linalg.norm(nn), r=np.sqrt(caps[k, 0] / np.pi))


def snap(V, tol=0.3):
    """We put vertices that are almost on a cap plane exactly on it."""
    V = V.copy()
    for p in planes.values():
        d = (V - p["c"]) @ p["n"]
        rad = np.linalg.norm((V - p["c"]) - np.outer(d, p["n"]), axis=1)
        sel = (np.abs(d) < tol) & (rad < 1.6 * p["r"])
        V[sel] -= np.outer(d[sel], p["n"])
    return V


def min_angle(t):
    out = []
    for i in range(3):
        u = t[:, (i + 1) % 3] - t[:, i]
        v = t[:, (i + 2) % 3] - t[:, i]
        c = np.einsum("ij,ij->i", u, v) / (np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1) + 1e-30)
        out.append(np.degrees(np.arccos(np.clip(c, -1, 1))))
    return np.min(out, axis=0)


ms = pymeshlab.MeshSet()
ms.load_new_mesh(SRC)
V = ms.current_mesh().vertex_matrix().copy() * F
Fc = ms.current_mesh().face_matrix().copy()
ms = pymeshlab.MeshSet()
ms.add_mesh(pymeshlab.Mesh(V, Fc))
ms.meshing_remove_duplicate_vertices()
ms.meshing_merge_close_vertices(threshold=pymeshlab.PureValue(0.15))
ms.meshing_remove_null_faces()
ms.meshing_remove_duplicate_faces()
ms.meshing_remove_unreferenced_vertices()
# feature-preserving isotropic remesh: the cap rims (about 90 deg) stay sharp
ms.meshing_isotropic_explicit_remeshing(targetlen=pymeshlab.PureValue(TARGET_EDGE), iterations=6,
                                        featuredeg=40, checksurfdist=True,
                                        maxsurfdist=pymeshlab.PureValue(0.1))
# we collapse the few very short edges (< 0.55 mm) that would give tiny tetrahedra
ms.meshing_merge_close_vertices(threshold=pymeshlab.PureValue(0.55))
ms.meshing_remove_null_faces()
ms.meshing_remove_duplicate_faces()
ms.meshing_remove_unreferenced_vertices()
ms.meshing_repair_non_manifold_edges()
ms.meshing_re_orient_faces_coherently()
mm = ms.current_mesh()
m = trimesh.Trimesh(snap(mm.vertex_matrix()), mm.face_matrix(), process=False)
if m.volume < 0:
    m.invert()
topo = ms.get_topological_measures()
ms.compute_selection_by_self_intersections_per_face()
n_self = ms.current_mesh().selected_face_number()
a = min_angle(m.triangles)
print("faces", len(m.faces), "watertight", m.is_watertight, "winding", m.is_winding_consistent,
      "genus", topo["genus"], "non-manifold edges", topo["non_two_manifold_edges"], "self-intersections", n_self)
print("surface edge min %.2f mm" % m.edges_unique_length.min())
print("vol mL %.1f, min angle %.1f deg, faces < 15 deg: %d, edge median %.2f mm" %
      (m.volume / 1000, a.min(), (a < 15).sum(), np.median(m.edges_unique_length)))

# labels: all 3 vertices exactly on the plane and normal along the outward plane normal
lab = np.zeros(len(m.faces), int)
zone_names = ["wall"] + list(planes.keys())
tc, tn = m.triangles_center, m.face_normals
for zi, (name, p) in enumerate(planes.items(), start=1):
    dv = np.abs((m.vertices - p["c"]) @ p["n"])
    on = (dv[m.faces] < 1e-6).all(axis=1) & ((tn @ p["n"]) > 0.9)
    lab[on] = zi
for zi, name in enumerate(zone_names):
    sel = lab == zi
    print(f"zone {name:6s} faces {sel.sum():6d} area {m.area_faces[sel].sum():8.1f} mm2")
adj, ang = m.face_adjacency, np.degrees(m.face_adjacency_angles)
bd = lab[adj[:, 0]] != lab[adj[:, 1]]
print("cap rim dihedral angles: min %.0f, median %.0f deg; max wall-wall angle %.0f deg" %
      (ang[bd].min(), np.median(ang[bd]), ang[~bd].max()))

# Z alignment: MV outward normal -> -Z, MV centroid -> origin
mvn = planes["mv"]["n"]
sel = lab == 1
mvc = (tc[sel] * m.area_faces[sel, None]).sum(0) / m.area_faces[sel].sum()
target = np.array([0, 0, -1.0])
v = np.cross(mvn, target); s = np.linalg.norm(v); c = mvn @ target
vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
R = np.eye(3) + vx + vx @ vx * ((1 - c) / s**2)
Xa = (m.vertices - mvc) @ R.T
ma = trimesh.Trimesh(Xa, m.faces, process=False)
print("aligned bbox mm", np.round(ma.bounds, 1).tolist())

m.export(f"{OUT}/LA_surface_LPSmm.stl")
ma.export(f"{OUT}/LA_surface_Zaligned_mm.stl")
np.savez(f"{OUT}/LA_surface_LPSmm_indexed.npz", V=m.vertices, F=m.faces, zone=lab)
np.savez(f"{OUT}/LA_surface_Zaligned_mm_indexed.npz", V=Xa, F=m.faces, zone=lab)
json.dump(dict(source=SRC, zone_names=zone_names, R=R.tolist(), mv_centre_LPS=mvc.tolist(),
               planes={k: dict(c=p["c"].tolist(), n=p["n"].tolist(), r=float(p["r"])) for k, p in planes.items()},
               note="aligned_mm = R @ (x_LPS_mm - mv_centre_LPS); MV outward normal -> -Z; Fluent mesh = aligned_mm/1000"),
          open(f"{OUT}/transform.json", "w"), indent=1)
