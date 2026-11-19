"""We build the two-column, paper-style report in three visual styles from one text.
Citations are written as [[key]] in the text and formatted per style (Nature superscript, IEEE brackets, APA author-year).
Usage: python build_paper.py   -> report/paper_A_nature.html, paper_B_ieee.html, paper_C_apa.html
"""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))

REFS = {
    "mill2020": dict(au="Mill J, Olivares AL, Arzamendi D, et al.", au_apa="Mill, J., Olivares, A. L., Arzamendi, D., et al.", short="Mill et al.",
                     year="2020", title="Impact of flow dynamics on device-related thrombosis after left atrial appendage occlusion",
                     journal="Canadian Journal of Cardiology", vol="36", issue="6", pages="968.e13–968.e14"),
    "aguado2019": dict(au="Aguado AM, Olivares AL, Yagüe C, et al.", au_apa="Aguado, A. M., Olivares, A. L., Yagüe, C., et al.", short="Aguado et al.",
                       year="2019", title="In silico optimization of left atrial appendage occluder implantation using interactive and modeling tools",
                       journal="Frontiers in Physiology", vol="10", issue="", pages="237"),
    "diachille2014": dict(au="Di Achille P, Tellides G, Figueroa CA, Humphrey JD.", au_apa="Di Achille, P., Tellides, G., Figueroa, C. A., & Humphrey, J. D.",
                          short="Di Achille et al.", year="2014",
                          title="A haemodynamic predictor of intraluminal thrombus formation in abdominal aortic aneurysms",
                          journal="Proceedings of the Royal Society A", vol="470", issue="2172", pages="20140163"),
    "dukkipati2018": dict(au="Dukkipati SR, Kar S, Holmes DR, et al.", au_apa="Dukkipati, S. R., Kar, S., Holmes, D. R., et al.", short="Dukkipati et al.",
                          year="2018", title="Device-related thrombus after left atrial appendage closure: incidence, predictors, and outcomes",
                          journal="Circulation", vol="138", issue="9", pages="874–885"),
    "korsholm2020": dict(au="Korsholm K, Berti S, Iriart X, et al.", au_apa="Korsholm, K., Berti, S., Iriart, X., et al.", short="Korsholm et al.",
                         year="2020", title="Expert recommendations on cardiac computed tomography for planning transcatheter left atrial appendage occlusion",
                         journal="JACC: Cardiovascular Interventions", vol="13", issue="3", pages="277–292"),
    "mill2021": dict(au="Mill J, Agudelo V, Olivares AL, et al.", au_apa="Mill, J., Agudelo, V., Olivares, A. L., et al.", short="Mill et al.",
                     year="2021", title="Sensitivity analysis of in silico fluid simulations to predict thrombus formation after left atrial appendage occlusion",
                     journal="Mathematics", vol="9", issue="18", pages="2304"),
    "simard2021": dict(au="Simard T, Jung RG, Lehenbauer K, et al.", au_apa="Simard, T., Jung, R. G., Lehenbauer, K., et al.", short="Simard et al.",
                       year="2021", title="Predictors of device-related thrombus following percutaneous left atrial appendage occlusion",
                       journal="Journal of the American College of Cardiology", vol="78", issue="4", pages="297–313"),
}

TITLE = "Is there a blood clot on the occluder? Imaging and blood-flow simulation of a left atrial appendage occlusion device (Case 1)"
AUTHOR = "Marc Serrano Sanz"
AFFIL = "Modelling of Organs and Systems (MOS), Universitat Pompeu Fabra · Individual laboratory report, November 2026"

ABSTRACT = (
    "Patients with atrial fibrillation (AF) can receive a small umbrella-shaped device that closes the left atrial appendage, the pouch where most "
    "clots form. Sometimes a new clot grows on the device itself (device-related thrombus, DRT). We asked whether Case 1 has a DRT. "
    "We answered it in two ways: by measuring the cardiac CT directly, and by building a 3D model of the patient's left atrium and simulating "
    "two heartbeats of blood flow. <b>The answer is no: the CT shows no clot on the device.</b> The simulation explains why the device still "
    "deserves attention: next to it, blood moves at half the average speed and is replaced three times more slowly than in the rest of the atrium, "
    "although the measures of risk on the wall stay below the usual threshold.")

KEYWORDS = "left atrial appendage occlusion · device-related thrombus · cardiac CT · computational fluid dynamics · ECAP"

BODY = r"""
<h2>1. Introduction</h2>
<p>In atrial fibrillation the upper chambers of the heart shake instead of squeezing properly, so blood moves slowly in the left atrium (LA). Most of the
clots that cause strokes in these patients form in the left atrial appendage (LAA), a small pouch of the LA. When blood thinners cannot be used, the
LAA can be closed with an occluder (here, a WATCHMAN-type device). In a few percent of patients, a clot then grows on the side of the device that faces the atrium. This is called device-related thrombus (DRT), and it raises the risk of stroke [[dukkipati2018]] [[simard2021]].</p>
<p>The question of this report is simple: <b>does Case 1 have a DRT?</b> The CT scan is what can show us. We also simulated the blood flow,
because the flow helps explain <i>why</i> a clot may or may not form: clots tend to grow where blood is slow and still [[mill2020]] [[aguado2019]].</p>

<figure class="wide"><img style="width:72%;margin:0 auto" src="../figures/fig_pipeline.png">
<figcaption>Figure 1. From image to simulation: (a) CT slice with the LA outline (red) and the device metal (yellow); (b) 3D model with the mitral valve tube (blue), the vein inlets (orange) and the device (black); (c) inside of the volume mesh; (d) simulated blood speed while the ventricle fills.</figcaption></figure>

<h2>2. Methods</h2>
<h3>2.1 Images and segmentation</h3>
<p>We used the contrast cardiac CT of Case 1, a 3D image with points about half a millimetre apart. In this CT, blood with contrast looks bright (about 490 HU, the CT brightness scale) and the metal of the device looks very bright (above 700 HU). A clot does not soak up the contrast dye, so on CT a DRT shows up as a darker layer covering the device, called hypo-attenuated thickening (HAT) [[korsholm2020]]. In 3D Slicer we traced the LA, the four pulmonary veins (PVs) and the mitral annulus (192.6 mL in total), and, separately, the metal of the device (bonus file).</p>
<p>To check for this dark layer with numbers rather than by eye, we drew 516 short lines across the device face, one every 0.5 mm, and measured on each one how much dark tissue (below 250 HU) sits between the bright blood and the metal.</p>

<h3>2.2 3D model and mesh</h3>
<p>We cleaned the LA surface in Meshmixer and cut it where the four PVs and the mitral valve (MV, the opening towards the ventricle, 597 mm²) end. We rotated it so that the MV faces down the Z axis, because the heart motion we apply acts along Z. Below the MV we added a short round tube (5 mm to become round, then 10 mm straight), so that the valve can slide up and down like a piston (see 2.3). Finally, Gmsh filled the inside with 245,471 small tetrahedra (well under the 500,000 limit, and all of good enough shape).</p>

<h3>2.3 Blood-flow simulation</h3>
<p>Ansys Fluent calculated how the blood moves, one step every 0.01 s, for two heartbeats of 0.875 s each (blood with density 1060 kg/m³ and viscosity 3.5 mPa·s, smooth laminar flow). The inputs were the course profiles: the pressure at the PVs (5–8.5 mmHg), the speed of the blood leaving through the MV (a single filling wave, as in AF, up to 0.94 m/s) and the up-and-down movement of the MV (8.9 mm). The mesh stretches with the valve, and where its little cells get too bent out of shape, Fluent rebuilds them. Our first two attempts, in which the whole atrial wall could deform, stopped with an error when the valve moved back up: the cells next to the valve were squeezed so much that they turned inside out. With the tube and a fixed atrial wall, the simulation ran to the end without errors. We only analysed the second beat, because the first one still carries effects of the start.</p>

<h3>2.4 What we measured</h3>
<p><b>Speed and washout.</b> We measured the average blood speed in the whole LA and within 10 mm of the device. For washout, we placed virtual particles all over the LA (one every 3 mm), let the flow carry them, and counted how many were still inside after each beat. <b>Wall indices.</b> TAWSS is the average rubbing force of the blood on the wall during a beat (in Pa); it is low where blood is slow. OSI (from 0 to 0.5) is high where the flow keeps changing direction. ECAP = OSI / TAWSS puts both together: it is high where blood is slow and goes back and forth. Values above about 1.4 Pa<sup>−1</sup> have been linked to clot formation [[diachille2014]] [[mill2021]].</p>



<h2>3. Results</h2>
<h3>3.1 The CT shows no clot on the device</h3>
<p>On 95 % of the lines there is no dark layer at all: the bright blood touches the device directly. Only one line in five hundred (0.2 %) shows 3 mm or more, at single points on the edge of the frame, where the metal blurs the image. A real DRT would look like a continuous dark cap over the centre of the device. The appendage behind the device is completely dark, which means that no blood gets in: the device closes it fully (Figure 2).</p>

<figure class="wide"><img style="width:74%;margin:0 auto" src="../figures/drt_imaging.png">
<figcaption>Figure 2. CT around the device. (a, b) Two long-axis planes (red: LA outline): the bright blood touches the metal and the appendage behind stays dark. (c) The device face, with its hub and struts. (d) Thickness of the dark layer in front of the metal on each of the 516 lines (0 = blood directly on the metal).</figcaption></figure>

<h3>3.2 The simulated flow is realistic</h3>
<p>The two beats are almost the same (the strongest outflow through the MV is 500 and 514 mL/s), and each beat pushes out 82 mL, a normal amount for a heart. The blood entering through the PVs matches the blood leaving through the MV, once the small change in atrial volume (190.7–196.1 mL) is taken into account. When the ventricle fills, a strong stream crosses the atrium towards the valve. Between filling waves, the blood in the body of the atrium turns slowly in a large swirl, or vortex (Figure 3).</p>

<figure class="wide"><img style="width:72%;margin:0 auto" src="../figures/fig_flow3.png">
<figcaption>Figure 3. (a, b) Blood speed and streamlines on a plane through the device (black) at the peak of ventricular filling and between filling waves.
(c) ECAP on the atrial wall over the second beat, seen from outside towards the device; the cyan line encloses the wall within 12 mm of the device.</figcaption></figure>

<h3>3.3 The device sits in a slow region</h3>
<p>Next to the device, blood moves at about half the average speed of the atrium (6.8 vs 13.0 cm/s), and it is replaced much more slowly: after three beats, 54 % of the blood that started next to the device is still there, compared with 19 % for the atrium as a whole (Figures 4 and 5). On the wall around the device, the flow also changes direction more often (OSI 0.38 vs 0.29) and ECAP is higher (0.59 vs 0.44 Pa<sup>−1</sup>). Still, ECAP stays below 1.4 Pa<sup>−1</sup> everywhere on the wall.</p>

<figure class="col"><img style="width:90%;margin:0 auto" src="../figures/fig_flow_col.png">
<figcaption>Figure 4. Top: average blood speed in the whole atrium (grey) and next to the device (red) over the two simulated beats. Bottom: share of the blood still
inside the atrium after it is released, counted beat by beat (washout).</figcaption></figure>

<figure class="col"><img style="width:92%;margin:0 auto" src="../figures/fig_keynumbers_col.png">
<figcaption>Figure 5. Next to the device (red) versus the whole left atrium (grey), second beat. Every measure points the same way, but only moderately.</figcaption></figure>



<h2>4. Discussion and conclusion</h2>
<p><b>Answer: there is no device-related thrombus in Case 1.</b> The CT is what decides this: the bright, contrast-filled blood touches the device everywhere and no dark layer covers it. The simulation does not change the answer, but it helps to understand the risk. The device sits in the quietest corner of the atrium, where blood moves more slowly, stays longer and pushes on the wall back and forth. This is the kind of place where clots like to form [[mill2020]] [[mill2021]] [[dukkipati2018]], but here they are only moderate, and no point of the wall reaches the ECAP threshold. In simple terms: there is no clot today and the risk is low to moderate, which supports keeping the usual treatment and the planned follow-up scan.</p>
<p><b>Limitations.</b> The atrial wall was kept still (only the valve moves), the boundary profiles are general and were not measured in this patient, blood was treated as a simple fluid, we simulated only two beats on one mesh, and the CT is a single picture in time. The ECAP threshold was first defined for aortic aneurysms [[diachille2014]].</p>
"""

STYLES = {
    "A_nature": dict(
        label="A · Nature-style",
        body_font='"Charter", "Georgia", serif', head_font='"Helvetica Neue", Helvetica, Arial, sans-serif',
        size="8.75pt", accent="#1a1a1a", cite="super", h2case="none", numbered=True,
        extra="h2{font-family:var(--hf);font-weight:700;font-size:10.5pt;border-bottom:0.6pt solid #000;padding-bottom:0.6mm}"
              " h3{font-family:var(--hf);font-weight:700;font-size:9pt}"
              " .abstract{font-family:var(--hf);font-weight:500;font-size:9pt;line-height:1.38}"),
    "B_ieee": dict(
        label="B · Engineering journal (IEEE-like)",
        body_font='"Times New Roman", Times, serif', head_font='"Times New Roman", Times, serif',
        size="9.3pt", accent="#000", cite="bracket", h2case="smallcaps", numbered=True,
        extra="h2{text-align:center;font-variant:small-caps;font-weight:400;font-size:11pt;letter-spacing:0.3pt}"
              " h3{font-style:italic;font-weight:400;font-size:9.8pt}"
              " .abstract{font-size:9pt;font-weight:700} .abstract b{font-weight:700}"
              " .title{text-align:center} .author,.affil{text-align:center}"),
    "C_apa": dict(
        label="C · Author–year (APA)",
        body_font='"Palatino", "Palatino Linotype", "Book Antiqua", serif', head_font='"Palatino", "Palatino Linotype", serif',
        size="9.1pt", accent="#7a1f2b", cite="apa", h2case="none", numbered=True,
        extra="h2{color:var(--acc);font-weight:700;font-size:11pt} h3{color:var(--acc);font-style:italic;font-weight:400;font-size:9.6pt}"
              " .abstract{border-left:2pt solid var(--acc);padding-left:3mm;font-size:9pt}"),
}

CSS = """
@page { size: A4; margin: 10mm 13mm 10mm 13mm; }
:root{ --bf:%(body_font)s; --hf:%(head_font)s; --acc:%(accent)s; }
body{ font-family:var(--bf); font-size:%(size)s; line-height:1.3; color:#111; margin:0; }
.title{ font-family:var(--hf); font-size:16.5pt; line-height:1.15; font-weight:700; margin:0 0 2mm 0; }
.author{ font-size:10pt; margin-bottom:0.6mm; } .affil{ font-size:8.3pt; color:#444; margin-bottom:3mm; }
.abstract{ margin:0 0 2mm 0; text-align:justify; } .kw{ font-size:8pt; color:#444; margin-bottom:3mm; }
.cols{ column-count:2; column-gap:6.5mm; text-align:justify; hyphens:auto; }
h2{ margin:2.6mm 0 1.2mm 0; break-after:avoid; } h3{ margin:2mm 0 0.6mm 0; break-after:avoid; }
p{ margin:0 0 1.6mm 0; } figure{ margin:1.6mm 0 2.2mm 0; break-inside:avoid; column-span:all; } figure.col{ column-span:none; }
figure img{ width:100%%; display:block; } .row{ display:flex; gap:1.5mm; } .row img{ flex:1; width:0; height:36mm; object-fit:contain; }
figcaption{ font-style:italic; font-size:8pt; line-height:1.3; margin-top:1mm; text-align:justify; color:#222; }
.refs{ break-before:page; column-count:2; column-gap:6.5mm; font-size:7.8pt; line-height:1.3; margin-top:2mm; }
.refs li{ margin-bottom:1.2mm; break-inside:avoid; } .refs h2{ column-span:all; }
.ver{ position:fixed; bottom:-9mm; right:0; font-size:7pt; color:#999; }
%(extra)s
"""


def cite_fmt(text, style, order):
    def one(key):
        if key not in order:
            order.append(key)
        return key
    keys_in = re.findall(r"\[\[(\w+)\]\]", text)
    for k in keys_in:
        one(k)

    def repl_group(m):
        keys = re.findall(r"\[\[(\w+)\]\]", m.group(0))
        nums = sorted(order.index(k) + 1 for k in keys)
        if style == "super":
            return "<sup>" + ",".join(map(str, nums)) + "</sup>"
        if style == "bracket":
            return "[" + ", ".join(map(str, nums)) + "]"
        parts = [f"{REFS[k]['short']}, {REFS[k]['year']}" for k in keys]
        return "(" + "; ".join(parts) + ")"
    return re.sub(r"(?:\s*\[\[\w+\]\])+", lambda m: (" " if style == "apa" or style == "bracket" else "") + repl_group(m), text)


def ref_list(style, order):
    if style == "apa":
        keys = sorted(REFS, key=lambda k: (REFS[k]["au_apa"], REFS[k]["year"]))
        items = []
        for k in keys:
            r = REFS[k]; iss = f"({r['issue']})" if r["issue"] else ""
            items.append(f"<li>{r['au_apa']} ({r['year']}). {r['title']}. <i>{r['journal']}, {r['vol']}</i>{iss}, {r['pages']}.</li>")
        return "<ul style='list-style:none;padding-left:0'>" + "".join(items) + "</ul>"
    items = []
    for k in order:
        r = REFS[k]; iss = f"({r['issue']})" if r["issue"] else ""
        if style == "super":
            items.append(f"<li>{r['au']} {r['title']}. <i>{r['journal']}</i> <b>{r['vol']}</b>, {r['pages']} ({r['year']}).</li>")
        else:
            items.append(f"<li>{r['au']} “{r['title']},” <i>{r['journal']}</i>, vol. {r['vol']}{', no. ' + r['issue'] if r['issue'] else ''}, pp. {r['pages']}, {r['year']}.</li>")
    tag = "ol" if style == "super" else "ol"
    return f"<{tag} style='padding-left:4.5mm'>" + "".join(items) + f"</{tag}>"


for name, st in STYLES.items():
    order = []
    body = cite_fmt(BODY, st["cite"], order)
    abstract = cite_fmt(ABSTRACT, st["cite"], order)
    css = CSS % st
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Case 1 DRT report</title><style>{css}</style></head><body>
<div class="title">{TITLE}</div><div class="author">{AUTHOR}</div><div class="affil">{AFFIL}</div>
<div class="abstract"><b>Abstract.</b> {abstract}</div>
<div class="cols">{body}</div>
<div class="refs"><h2>References</h2>{ref_list(st['cite'], order)}</div>
</body></html>"""
    open(os.path.join(HERE, f"paper_{name}.html"), "w").write(html)
    print("written", name)
