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
    "two heartbeats of blood flow. <b>The answer is no: the CT shows no clot on the device.</b> The simulation shows why the device still deserves "
    "attention: blood near it moves at half the average speed and is renewed three times more slowly than in the rest of the atrium, "
    "although the wall indices stay below the usual risk threshold.")

KEYWORDS = "left atrial appendage occlusion · device-related thrombus · cardiac CT · computational fluid dynamics · ECAP"

BODY = r"""
<h2>1. Introduction</h2>
<p>In atrial fibrillation the upper chambers of the heart quiver instead of contracting, so blood moves slowly in the left atrium (LA). Most of the
clots that cause strokes in these patients form in the left atrial appendage (LAA), a small pouch of the LA. When blood thinners cannot be used, the
LAA can be closed with an occluder (here, a WATCHMAN-type device). In a few percent of patients a thrombus then grows on the atrial face of the device
(DRT), which increases the risk of stroke [[dukkipati2018]] [[simard2021]].</p>
<p>The question of this report is simple: <b>does Case 1 have a DRT?</b> Medical images are the evidence for this. We also simulated the blood flow,
because flow explains <i>why</i> a clot may or may not form: clots like slow, stagnant blood [[mill2020]] [[aguado2019]].</p>

<figure class="wide"><img style="width:80%;margin:0 auto" src="../figures/fig_pipeline.png">
<figcaption>Figure 1. From image to simulation. (a) CT slice with the left-atrium segmentation (red) and the metal of the occluder (yellow). (b) 3D model:
mitral valve tube (blue), pulmonary vein inlets (orange) and the device (black). (c) Inside view of the volume mesh (245,471 tetrahedra).
(d) Simulated blood speed during early filling of the ventricle.</figcaption></figure>

<h2>2. Methods</h2>
<h3>2.1 Images and segmentation</h3>
<p>We used the contrast cardiac CT of Case 1 (voxels of 0.45 × 0.45 × 0.3 mm). In this CT, blood with contrast appears bright (about 490 HU) and the metal
of the device very bright (above 700 HU). A clot does not take up contrast, so on CT a DRT appears as a darker layer covering the device, called
hypo-attenuated thickening (HAT) [[korsholm2020]]. We segmented the LA, the four pulmonary veins (PVs) and the mitral annulus in 3D Slicer (192.6 mL),
and the metal of the device separately (bonus file).</p>
<p>To look for HAT objectively, we drew 516 short lines perpendicular to the device face, 0.5 mm apart, and measured on each line how much dark tissue
(below 250 HU) lies between the bright blood and the metal.</p>

<h3>2.2 3D model and mesh</h3>
<p>The surface of the LA was cleaned and cut in Meshmixer at the four PVs and at the mitral valve (MV, 597 mm²), and rotated so that the MV faces the −Z axis,
because the heart motion we impose acts along Z. The MV outline was then extended by a short circular tube (5 mm transition + 10 mm straight).
The tube lets the valve slide like a piston, which keeps the mesh valid while it moves (see 2.3). Gmsh then filled the volume with 245,471 tetrahedra
(limit 500,000; worst skewness 0.91).</p>

<h3>2.3 Blood-flow simulation</h3>
<p>Ansys Fluent solved the equations of blood flow (laminar, density 1060 kg/m³, viscosity 3.5 mPa·s) every 0.01 s for two heartbeats of 0.875 s.
We used the course boundary profiles: pressure at the PVs (5–8.5 mmHg), outflow velocity at the MV (one filling wave only, as in AF, peak 0.94 m/s),
and the up–down motion of the MV plane (8.9 mm). The mesh follows this motion and is rebuilt locally when cells get too distorted.
Our first two runs, in which the whole atrial wall was allowed to deform, crashed when the valve moved back up, because cells next to the valve were
squeezed until they turned inside out. With the valve tube and a fixed atrial wall the simulation ran without errors. We analysed only the second beat,
once the start-up effects had gone.</p>

<h3>2.4 What we measured</h3>
<p><b>Speed and washout.</b> Average blood speed in the whole LA and within 10 mm of the device. For washout we released virtual particles everywhere in the LA
(one every 3 mm) and counted how many were still inside after each beat. <b>Wall indices.</b> The friction of blood on the wall averaged over the beat
(TAWSS, in Pa) is low where blood is slow. The oscillatory shear index (OSI, 0–0.5) is high where the flow keeps changing direction. ECAP = OSI / TAWSS
combines both. Values above about 1.4 Pa<sup>−1</sup> have been linked to thrombus formation [[diachille2014]] [[mill2021]].</p>

<figure class="wide"><img style="width:82%;margin:0 auto" src="../figures/drt_imaging.png">
<figcaption>Figure 2. CT around the occluder. Left and centre: two long-axis planes through the device (red: LA segmentation). The bright blood touches the
metal directly, and the appendage behind the device stays dark (no contrast). Third: view of the device face, with the hub and the struts. Right: thickness of
dark tissue in front of the metal on each of the 516 lines (0 = blood directly on the metal).</figcaption></figure>

<h2>3. Results</h2>
<h3>3.1 The CT shows no clot on the device</h3>
<p>On 95 % of the lines the dark layer has zero thickness: bright blood touches the device directly. Only one line in five hundred (0.2 %) shows 3 mm or more,
at isolated points on the edge of the frame, where metal blurs the image. A true DRT would appear as a continuous dark cap over the hub. The appendage behind
the device is completely dark, so the device closes it fully (no leak) (Figure 2).</p>

<h3>3.2 The simulated flow is realistic</h3>
<p>The two beats are almost identical (peak MV outflow 500 and 514 mL/s), and each beat moves 82 mL, which is a normal value. Inflow and outflow balance once the small volume change of the atrium (190.7–196.1 mL) is counted. During ventricular filling a strong
jet crosses the atrium towards the valve. Between filling waves a slow rotating flow (vortex) occupies the body of the atrium (Figure 3).</p>

<figure class="wide"><div class="row"><img src="../figures/cfd_vel_Epeak_crop.png"><img src="../figures/cfd_vel_diastasis_crop.png"><img src="../figures/cfd_ecap_crop.png"></div>
<figcaption>Figure 3. Left and centre: blood speed and streamlines on a plane through the device (black) at the peak of ventricular filling (t = 1.31 s) and between
filling waves (t = 1.60 s). Right: ECAP on the atrial wall over the second beat, seen from outside towards the device. The cyan line encloses the wall within 12 mm of the device.</figcaption></figure>

<h3>3.3 The device sits in a slow region</h3>
<p>Blood near the device moves at about half the average speed of the atrium (6.8 vs 13.0 cm/s). It is also renewed much more slowly. After three beats
54 % of the blood that started next to the device is still there, against 19 % for the atrium as a whole (Figures 4 and 5). On the wall around the device the flow
oscillates more (OSI 0.38 vs 0.29) and ECAP is higher (0.59 vs 0.44 Pa<sup>−1</sup>). However, ECAP stays below 1.4 Pa<sup>−1</sup> at every point of the wall.</p>

<figure class="col"><img src="../figures/fig_flow_col.png">
<figcaption>Figure 4. Top: average blood speed in the whole atrium (grey) and next to the device (red) over the two simulated beats. Bottom: share of the blood still
inside the atrium after it is released, counted beat by beat (washout).</figcaption></figure>

<figure class="col"><img src="../figures/fig_keynumbers_col.png">
<figcaption>Figure 5. Next to the device (red, within 10–12 mm) versus the whole left atrium (grey, LA), second beat. Slower blood, slower washout and higher
OSI and ECAP all point the same way, but the size of the effect is moderate.</figcaption></figure>



<h2>4. Discussion and conclusion</h2>
<p><b>Answer: there is no device-related thrombus in Case 1.</b> The CT decides it: contrast-filled blood touches the device everywhere and no dark layer covers it.
The simulation adds context. The occluder sits in the quietest corner of the atrium, where blood is slower, stays longer and rubs the wall in changing
directions. These are the conditions that favour clotting [[mill2020]] [[mill2021]] [[dukkipati2018]], but here they are moderate and no point of the wall
crosses the ECAP threshold. In plain words: no clot today and a low-to-moderate risk, which supports the usual treatment and the planned follow-up scan.</p>
<p><b>Limitations.</b> Rigid atrial wall (only the valve moves), generic boundary profiles, blood as a simple fluid, two beats on one mesh, and a single CT
snapshot. The ECAP threshold comes from aortic aneurysms [[diachille2014]].</p>
"""

STYLES = {
    "A_nature": dict(
        label="A · Nature-style",
        body_font='"Charter", "Georgia", serif', head_font='"Helvetica Neue", Helvetica, Arial, sans-serif',
        size="8.85pt", accent="#1a1a1a", cite="super", h2case="none", numbered=True,
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
<div class="abstract"><b>Abstract.</b> {abstract}</div><div class="kw"><b>Keywords:</b> {KEYWORDS}</div>
<div class="cols">{body}</div>
<div class="refs"><h2>References</h2>{ref_list(st['cite'], order)}</div>
</body></html>"""
    open(os.path.join(HERE, f"paper_{name}.html"), "w").write(html)
    print("written", name)
