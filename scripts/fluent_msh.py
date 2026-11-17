"""We write a tetrahedral mesh as an ASCII Fluent .msh file with named boundary zones.

Convention (we checked it on the Oct 20 Fluent 2026 R1 case, v0.cas.h5, 424k faces):
the right-hand normal of the face node list (n0, n1, n2) points TOWARD cell c0.
Boundary faces have c1 = 0, so their right-hand normal points into the fluid.
Coordinates are written in metres, so no scaling is needed in Fluent.
"""
import numpy as np

# Fluent boundary-condition type codes used in section 13 headers
BC_CODE = {"interior": 2, "wall": 3, "pressure-inlet": 4, "pressure-outlet": 5,
           "velocity-inlet": 10}


def tet_faces(tets):
    """We list the 4 faces of every tet with a consistent local node order."""
    t = tets
    f = np.concatenate([t[:, [1, 2, 3]], t[:, [0, 3, 2]], t[:, [0, 1, 3]], t[:, [0, 2, 1]]])
    owner = np.tile(np.arange(len(t)), 4)
    return f, owner


def fix_tet_orientation(X, tets):
    """We make every tet positive (det > 0) so the face order above gives outward normals."""
    a, b, c, d = (X[tets[:, i]] for i in range(4))
    vol = np.einsum("ij,ij->i", np.cross(b - a, c - a), d - a)
    tets = tets.copy()
    neg = vol < 0
    tets[neg, 2], tets[neg, 3] = tets[neg, 3].copy(), tets[neg, 2].copy()
    return tets, np.abs(vol) / 6.0


def build_faces(X, tets, tri_zone_of_boundary_face):
    """We build unique faces. Returns interior faces and boundary faces per zone.

    tri_zone_of_boundary_face: function(sorted_node_tuple_array) -> zone index per boundary face
    """
    f, owner = tet_faces(tets)
    key = np.sort(f, axis=1)
    order = np.lexsort((key[:, 2], key[:, 1], key[:, 0]))
    ks = key[order]
    same_as_next = np.all(ks[1:] == ks[:-1], axis=1)
    first = np.where(same_as_next)[0]
    # interior faces: pairs
    ia, ib = order[first], order[first + 1]
    paired = np.zeros(len(f), bool)
    paired[ia] = True
    paired[ib] = True
    bnd = np.where(~paired)[0]
    # The local order gives an OUTWARD normal of the owner tet.
    # Fluent wants the normal toward c0, so we reverse the node order and keep c0 = owner.
    int_nodes = f[ia][:, ::-1]
    int_c0 = owner[ia]
    int_c1 = owner[ib]
    bnd_nodes = f[bnd][:, ::-1]
    bnd_c0 = owner[bnd]
    bnd_zone = tri_zone_of_boundary_face(np.sort(f[bnd], axis=1))
    return int_nodes, int_c0, int_c1, bnd_nodes, bnd_c0, bnd_zone


def write_msh(path, X_m, tets, zone_names, zone_types, tri_zone_fn, fluid_name="fluid"):
    """We write the .msh file. X_m in metres. zone_names/types list boundary zones in order."""
    tets, _ = fix_tet_orientation(X_m, tets)
    int_nodes, int_c0, int_c1, bnd_nodes, bnd_c0, bnd_zone = build_faces(X_m, tets, tri_zone_fn)
    nn, nc = len(X_m), len(tets)
    nf = len(int_nodes) + len(bnd_nodes)
    hx = lambda v: format(int(v), "x")
    with open(path, "w") as fh:
        fh.write('(0 "cfd-cardio-thrombosis: LA tet mesh, metres")\n(2 3)\n')
        fh.write(f"(10 (0 1 {hx(nn)} 0 3))\n")
        fh.write(f"(10 (1 1 {hx(nn)} 1 3)(\n")
        np.savetxt(fh, X_m, fmt="%.9e")
        fh.write("))\n")
        fh.write(f"(12 (0 1 {hx(nc)} 0))\n")
        fh.write(f"(12 (2 1 {hx(nc)} 1 2))\n")  # zone 2, fluid, tetra
        fh.write(f"(13 (0 1 {hx(nf)} 0))\n")
        start = 1
        # interior zone id 3
        n_int = len(int_nodes)
        fh.write(f"(13 (3 {hx(start)} {hx(start + n_int - 1)} 2 3)(\n")
        arr = np.column_stack([int_nodes + 1, int_c0 + 1, int_c1 + 1])
        np.savetxt(fh, arr, fmt="%x")
        fh.write("))\n")
        start += n_int
        zone_ids = []
        for zi, (name, typ) in enumerate(zip(zone_names, zone_types)):
            sel = np.where(bnd_zone == zi)[0]
            if len(sel) == 0:
                raise ValueError(f"zone {name} has no faces")
            zid = 4 + zi
            zone_ids.append(zid)
            fh.write(f"(13 ({hx(zid)} {hx(start)} {hx(start + len(sel) - 1)} {hx(BC_CODE[typ])} 3)(\n")
            arr = np.column_stack([bnd_nodes[sel] + 1, bnd_c0[sel] + 1, np.zeros(len(sel), int)])
            np.savetxt(fh, arr, fmt="%x")
            fh.write("))\n")
            start += len(sel)
        unassigned = np.sum((bnd_zone < 0) | (bnd_zone >= len(zone_names)))
        if unassigned:
            raise ValueError(f"{unassigned} boundary faces without zone")
        fh.write(f"(45 (2 fluid {fluid_name})())\n")
        fh.write("(45 (3 interior interior-fluid)())\n")
        for zid, name, typ in zip(zone_ids, zone_names, zone_types):
            fh.write(f"(45 ({zid} {typ} {name})())\n")
    return dict(nodes=nn, cells=nc, faces=nf, interior=n_int,
                boundary={n: int(np.sum(bnd_zone == i)) for i, n in enumerate(zone_names)})


def check_msh(path):
    """We re-read our own .msh and verify the c0 convention and closure (sum of area vectors per cell = 0)."""
    txt = open(path).read()
    import re
    blocks = re.findall(r"\(13 \(([0-9a-f]+) ([0-9a-f]+) ([0-9a-f]+) ([0-9a-f]+) 3\)\(\n(.*?)\)\)", txt, re.S)
    nodes_blk = re.search(r"\(10 \(1 1 [0-9a-f]+ 1 3\)\(\n(.*?)\)\)", txt, re.S).group(1)
    X = np.array(nodes_blk.split(), float).reshape(-1, 3)
    F = []
    for b in blocks:
        F.append(np.array([int(v, 16) for v in b[4].split()]).reshape(-1, 5))
    F = np.vstack(F)
    n = F[:, :3] - 1
    c0, c1 = F[:, 3], F[:, 4]
    A = 0.5 * np.cross(X[n[:, 1]] - X[n[:, 0]], X[n[:, 2]] - X[n[:, 0]])
    fc = X[n].mean(1)
    nc = max(c0.max(), c1.max())
    S = np.zeros((nc + 1, 3)); C = np.zeros(nc + 1)
    np.add.at(S, c0, fc); np.add.at(C, c0, 1)
    np.add.at(S, c1, fc); np.add.at(C, c1, 1)
    cc = S[1:] / C[1:, None]
    toward_c0 = np.einsum("ij,ij->i", A, cc[c0 - 1] - fc) > 0
    # closure: area vectors pointing OUT of each cell must sum to zero
    out = np.zeros((nc + 1, 3))
    np.add.at(out, c0, -A)
    np.add.at(out, c1, A)
    closure = np.abs(out[1:]).max()
    return dict(frac_toward_c0=float(toward_c0.mean()), faces_per_cell_min=float(C[1:].min()),
                faces_per_cell_max=float(C[1:].max()), max_closure_error=float(closure))
