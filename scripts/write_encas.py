"""We write an EnSight .encas for the frames we downloaded (frames 1..N, dt 0.01 s), listing only the variables we kept."""
import sys
run, n = sys.argv[1], int(sys.argv[2])
keep = [("scalar per node", "z_wall_shear", "scl5"), ("scalar per node", "y_wall_shear", "scl6"), ("scalar per node", "x_wall_shear", "scl7"),
        ("scalar per node", "wall_shear", "scl8"), ("scalar per node", "velocity_magnitude", "scl12"), ("scalar per node", "pressure", "scl13"),
        ("vector per node", "velocity", "vel")]
vals = [f"{0.01 * (k + 1):.5e}" for k in range(n)]
txt = "FORMAT\ntype:  ensight gold\nGEOMETRY\nmodel:  1   \"LA_Case001_ens*****.geo\"\nVARIABLE\n"
txt += "".join(f"{t}:  1  {name}  \"LA_Case001_ens*****.{ext}\"\n" for t, name, ext in keep)
txt += f"TIME\ntime set: 1 Model\nnumber of steps: {n}\nfilename start number: 1\nfilename increment: 1\ntime values:\n"
txt += "\n".join(" ".join(vals[i:i + 6]) for i in range(0, n, 6)) + "\n"
open(f"{run}/LA_Case001_ens.encas", "w").write(txt)
print("encas with", n, "frames")
