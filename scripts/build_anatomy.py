"""Build ASTRA's 3D anatomy model from BodyParts3D 4.0 (CC BY 4.0).

BodyParts3D, (c) The Database Center for Life Science, licensed under CC Attribution 4.0 International.
https://dbarchive.biosciencedbc.jp/en/bodyparts3d/lic.html

Usage (run from the project root; the data folder holds the official downloads, untouched):
  uv run --no-project --with trimesh --with numpy --with scipy python -I scripts/build_anatomy.py <data_dir> anatomy-raw.glb

<data_dir> must contain (from https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/):
  isa_BP3D_4.0_obj_99.zip, isa_element_parts.txt, partof_element_parts.txt

Then optimise it into the web app (this is `npm run anatomy:optimize` in package.json, run from the project root):
  cd web
  pnpm exec gltf-transform optimize ../anatomy-raw.glb public/models/astra-anatomy.glb --compress meshopt \
    --join false --flatten false --instance false --palette false --simplify false
  node scripts/lod-anatomy.mjs public/models/astra-anatomy.glb public/models/astra-anatomy.glb
The second step simplifies each part to its own budget (organs within 0.08% of their size, then per part; the
muscles to a triangle count per region, keeping their baked tendons and occlusion) and re-applies meshopt compression.
The build takes a few minutes and about 2 GB of memory; the raw file is about 180 MB.

Each ASTRA part becomes one named node "<system>--<part>" so the web viewer can colour and pick it.
Coordinates: BodyParts3D is millimetres, Z up, anterior = -Y. Output is metres, Y up, facing +Z.

FMA ids of the concepts used (BodyParts3D concept tables; "isa" unless noted):
  muscles      every skeletal muscle BodyParts3D has: muscle organ FMA5022, zone of muscle organ FMA10474 (the parts of
               pectoralis major, deltoid, trapezius, quadriceps), head of muscle organ FMA85453 (biceps, triceps,
               gastrocnemius, biceps femoris, ...), musculature FMA32558 (interossei, lumbricals, levatores costarum),
               ascending / descending part of trapezius FMA32555 / FMA32557, tendon FMA9721, calcaneal tendon FMA51061, linea alba FMA11336, iliotibial tract FMA51048, flexor
               retinaculum of wrist FMA39988. Left out by name (MUSCLE_SKIP): larynx, pharynx, palate, tongue,
               heart and gut muscles, pelvic floor and perineum, platysma, the inner chest wall; the diaphragm is
               its own part. BodyParts3D 4.0 has no latissimus dorsi, temporalis or masseter: they are modelled
               (latissimus(), jaw_muscles()). It has no rectus abdominis, internal oblique, transversus abdominis,
               quadratus lumborum or facial muscles either; those are not modelled. Split by region into
               muscles_head, muscles_trunk, muscles_arm_r/l and muscles_leg_r/l. Coarse elements are subdivided and
               rounded; the vertex colour (COLOR_0) carries what the viewer's shader needs: red = tendon or
               aponeurosis (thin sheets, thin round cords, the tendinous elements), green = ambient occlusion from
               the neighbouring muscles and bones, blue and alpha = fibre direction (octahedral; a harmonic field
               along each piece, or FIBRE_HINT for flat muscles). See prepare_muscles().
  optic_nerve  optic nerve FMA50863 (right FMA50875, left FMA50878), optic chiasm FMA62045.
  larynx       laryngeal cartilage FMA55108 (thyroid FMA55099, cricoid FMA9615, arytenoid FMA55109, corniculate,
               cuneiform), epiglottis FMA55130.
  diaphragm    diaphragm FMA13295 (also the floor the lungs are rebuilt on, see web/components/body/organGeometry.ts).
  lung_r/l     right / left lung (part-of FMA7309 / FMA7310): in BodyParts3D only the bronchial and vascular trees.
               Each vertex is coloured by lobe (COLOR_0: red upper, green middle, blue lower lobe, black unassigned)
               from the part-of lobes: upper / middle / lower lobe of right lung FMA7333 / FMA7383 / FMA7337, upper /
               lower lobe of left lung FMA7370 / FMA7371. The viewer rebuilds each lung's surface around its tree and
               cuts the fissures where the lobes meet.
  large_int.   large intestine (part-of FMA7201: colon, rectum FMA14544) plus the appendix FMA14542.
  adrenals     right / left adrenal gland FMA15629 / FMA15630.
  arteries     descending thoracic aorta FMA87217, abdominal aorta FMA3789, common carotid FMA3939, internal carotid
               FMA3947, vertebral FMA3956, subclavian FMA3951, axillary FMA22654, brachial FMA22689, radial FMA22730,
               ulnar FMA22796, celiac trunk FMA14812, superior mesenteric FMA14749, renal FMA14751, common / external /
               internal iliac FMA14764 / FMA18805 / FMA18808, femoral FMA70248, popliteal FMA77155, anterior /
               posterior tibial FMA43894 / FMA43895, dorsalis pedis FMA43915 arteries.
  veins        superior / inferior vena cava FMA4720 / FMA10951, brachiocephalic FMA4723, internal jugular FMA4724,
               subclavian FMA4725, axillary FMA13329, brachial FMA22934, cephalic FMA13324, basilic FMA22908, renal
               FMA14334, common / external iliac FMA14333 / FMA18883, femoral FMA21185, popliteal FMA44327, anterior /
               posterior tibial FMA44331 / FMA44332, great / small saphenous FMA21376 / FMA44333 veins.
  thyroid      BodyParts3D 4.0 has no thyroid gland: modelled (two lobes and the isthmus, textbook size) on the trachea
               just below the cricoid cartilage; see thyroid().
  lymph_nodes  BodyParts3D 4.0 has no lymph nodes: the major groups (deep cervical, axillary, inguinal, para-aortic,
               tracheobronchial) are modelled as small nodes along their landmark vessels; see lymph_nodes().
The figure is unisex on purpose: no reproductive organs.
  skeleton     skeleton (in vivo), skeletal system (part-of FMA23881), bone organ, minus the elements of the parts
               above (the part-of tree also lists the eyeballs' tissues); split by element name into skull, thorax
               (ribs, sternum, costal cartilage), spine (vertebral column FMA13478: 24 vertebrae, intervertebral disks
               FMA10446, sacrum FMA16202) and hips (hip bone FMA16585, right / left FMA16586 / FMA16587, plus the
               proximal fifth of each femur, right / left FMA24474 / FMA24475: head, neck and trochanters, the sites
               of spaceflight bone loss; cut on a plane and both pieces capped). The rest stays skeleton_bones.
  vestibular   BodyParts3D 4.0 has no inner ear, so the bony labyrinth (vestibule, three semicircular canals with
               their ampullae, cochlea) is modelled here from textbook dimensions and placed in each petrous temporal
               bone; see labyrinth().
"""

from __future__ import annotations

import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import trimesh

# Every skeletal muscle in BodyParts3D: the muscle organs, their named parts and heads (the deltoid's three parts,
# the heads of biceps and triceps, the quadriceps), the sets of small muscles (interossei, lumbricals, levatores
# costarum), and the tendons, aponeuroses and fasciae stored as elements of their own.
MUSCLE_CONCEPTS = [
    "muscle organ", "zone of muscle organ", "head of muscle organ", "musculature", "tendon",
    "ascending part of trapezius", "descending part of trapezius",  # not filed as zones of a muscle organ
    "calcaneal tendon", "linea alba", "iliotibial tract", "flexor retinaculum of wrist",
]
# Left out: the muscles inside the larynx, pharynx, palate, tongue, heart and gut; the pelvic floor and perineum (the
# figure is unisex: nothing between the legs); the platysma, a skin muscle that would veil the neck; the inner layers
# of the chest wall, which are never seen; and the diaphragm, which is its own part.
MUSCLE_SKIP = re.compile(
    r"crico|aryt|vocalis|aryepiglott|epiglott|pharyn|palat|uvul|glossus|papillary|taenia|coccygeus|iliococcygeus|"
    r"pubococcygeus|puborectalis|levator ani|anal sphincter|perine|platysma|internal intercostal|"
    r"innermost intercostal|transversus thoracis|diaphragm",
    re.I,
)
FASCIA_LATA = re.compile(r"iliotibial|fascia lata", re.I)
# Bones the latissimus lies over.
BACK_BONES = re.compile(r"\brib\b|costal|vertebra|sacrum|coccy|hip bone|scapula|intervertebral")
# Elements that are tendon or fascia throughout (BodyParts3D names the linea alba's element "decussation").
TENDINOUS = re.compile(r"tendon|linea alba|iliotibial|fascia lata|retinaculum|decussation", re.I)
# Fibre direction of flat muscles whose long axis is not the way their fibres run (right side; mirrored for the
# left). Other muscles take their long axis.
FIBRE_HINT = [
    (re.compile(r"external oblique", re.I), (0.55, -0.7, 0.45)),  # down and forward to the linea alba
    (re.compile(r"serratus anterior", re.I), (0.25, 0.25, -0.95)),  # round the chest wall to the scapula
    (re.compile(r"external intercostal", re.I), (0.3, -0.75, 0.6)),  # down and forward between the ribs
]

ARTERIES = [
    "descending thoracic aorta", "abdominal aorta", "common carotid artery", "internal carotid artery",
    "vertebral artery", "subclavian artery", "axillary artery", "brachial artery", "radial artery", "ulnar artery",
    "celiac trunk", "superior mesenteric artery", "renal artery",
    "common iliac artery", "external iliac artery", "internal iliac artery", "femoral artery", "popliteal artery",
    "anterior tibial artery", "posterior tibial artery", "dorsalis pedis artery",
]
VEINS = [
    "superior vena cava", "inferior vena cava", "brachiocephalic vein", "internal jugular vein", "subclavian vein",
    "axillary vein", "brachial vein", "cephalic vein", "basilic vein", "renal vein",
    "common iliac vein", "external iliac vein", "femoral vein", "popliteal vein", "anterior tibial vein",
    "posterior tibial vein", "great saphenous vein", "small saphenous vein",
]
# Lobes of each lung (part-of concepts), coloured red, green, blue on the lung's vertices.
LOBES = {
    "lung_r": ["upper lobe of right lung", "middle lobe of lung", "lower lobe of right lung"],
    "lung_l": ["upper lobe of left lung", "", "lower lobe of left lung"],
}

# (part key, ASTRA system, BodyParts3D concept names)
PARTS: list[tuple[str, str, list[str]]] = [
    ("skin", "skin", ["skin"]),
    ("brain", "brain", ["brain"]),
    ("vestibular", "brain", []),  # modelled, see labyrinth()
    ("eye_r", "eyes", ["right eyeball"]),
    ("eye_l", "eyes", ["left eyeball"]),
    ("optic_nerve", "eyes", ["optic nerve", "optic chiasm"]),
    ("heart", "heart", ["heart"]),
    ("vessels", "heart", ["ascending aorta", "arch of aorta", "pulmonary trunk"]),
    ("arteries", "heart", ARTERIES),
    ("veins", "heart", VEINS),
    ("lung_r", "lungs", ["right lung"]),
    ("lung_l", "lungs", ["left lung"]),
    ("airway", "lungs", ["trachea", "right main bronchus", "left main bronchus"]),
    ("larynx", "lungs", ["laryngeal cartilage", "epiglottis"]),
    ("diaphragm", "lungs", ["diaphragm"]),
    ("liver", "metabolism", ["liver"]),
    ("gallbladder", "metabolism", ["gallbladder"]),
    ("esophagus", "metabolism", ["esophagus"]),
    ("stomach", "metabolism", ["stomach"]),
    ("pancreas", "metabolism", ["pancreas"]),
    ("small_intestine", "metabolism", ["small intestine"]),
    ("large_intestine", "metabolism", ["large intestine", "appendix"]),
    ("thyroid", "metabolism", []),  # modelled, see thyroid()
    ("kidney_r", "kidneys", ["right kidney"]),
    ("kidney_l", "kidneys", ["left kidney"]),
    ("adrenals", "kidneys", ["adrenal gland"]),
    ("ureters", "kidneys", ["right ureter", "left ureter"]),
    ("bladder", "kidneys", ["urinary bladder"]),
    ("spleen", "immune", ["spleen"]),
    ("thymus", "immune", ["thymus"]),
    ("lymph_nodes", "immune", []),  # modelled, see lymph_nodes()
    ("muscles", "musculo", MUSCLE_CONCEPTS),  # split into regions, see muscle_regions()
    ("skeleton", "musculo", ["skeleton (in vivo)", "skeletal system", "bone organ"]),
]

# BodyParts3D sometimes holds two versions of one structure (e.g. each optic nerve twice): keep the larger.
DEDUPE = {"optic_nerve", "muscles", "larynx", "arteries", "veins"}

# Skeleton is split so the skull and ribcage can be rendered see-through over the brain, heart and lungs, and so the
# sites of bone loss in space (spine, hips) can be shown on their own.
SKULL = re.compile(
    r"skull|cran|frontal bone|parietal bone|occipital bone|temporal bone|sphenoid|ethmoid|mandible|maxilla|"
    r"zygomatic|nasal bone|lacrimal|palatine bone|vomer|tooth|teeth|incisor|canine|molar|hyoid|concha|"
    r"nasal septum|auditory ossicle|malleus|incus|stapes",
    re.I,
)
THORAX = re.compile(r"\brib\b|ribs|sternum|sternal|costal|manubrium|xiphoid", re.I)
SPINE = re.compile(r"vertebra|intervertebral|sacrum|coccy|\batlas\b|\baxis\b", re.I)
HIPS = re.compile(r"hip bone|pelvic girdle|\bilium\b|ischium|\bpubis\b", re.I)
FEMUR = re.compile(r"\bfemur\b", re.I)
FEMUR_HIP_FRACTION = 0.2  # proximal share of the femur's length counted as "hip": head, neck, trochanters


def read_table(path: Path) -> tuple[dict[str, set[str]], dict[str, str]]:
    """concept name -> element ids, and element id -> most specific name."""
    concept: dict[str, set[str]] = defaultdict(set)
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
        cols = line.split("\t")
        if len(cols) >= 3:
            concept[cols[1].strip()].add(cols[2].strip())
    element_name: dict[str, str] = {}
    for name, els in concept.items():
        if len(els) == 1:
            (el,) = tuple(els)
            element_name.setdefault(el, name)
    return concept, element_name


def parse_obj(text: str) -> tuple[np.ndarray, np.ndarray, str]:
    """Minimal parser for BodyParts3D OBJ files (v / vn / f a//a b//b c//c, plus a commented header)."""
    verts: list[str] = []
    faces: list[list[int]] = []
    name = ""
    for line in text.splitlines():
        if line.startswith("v "):
            verts.append(line[2:])
        elif line.startswith("f "):
            idx = [int(tok.split("/", 1)[0]) - 1 for tok in line[2:].split()]
            for i in range(1, len(idx) - 1):  # fan-triangulate any polygon
                faces.append([idx[0], idx[i], idx[i + 1]])
        elif line.startswith("# English name"):
            name = line.split(":", 1)[1].strip()
    v = np.array(" ".join(verts).split(), dtype=np.float64).reshape(-1, 3)
    return v, np.array(faces, dtype=np.int64).reshape(-1, 3), name


def to_three(v: np.ndarray) -> np.ndarray:
    return np.column_stack([v[:, 0], v[:, 2], -v[:, 1]]) * 0.001  # mm -> m, Z-up -> Y-up, face +Z


def dedupe(items: list[tuple[str, str, trimesh.Trimesh]]) -> list[tuple[str, str, trimesh.Trimesh]]:
    """Drops an element when a larger one of the same name covers mostly the same box (a second version of it)."""
    kept: list[tuple[str, str, trimesh.Trimesh]] = []
    for el, nm, m in sorted(items, key=lambda x: -len(x[2].faces)):
        lo, hi = m.bounds
        dup = False
        for _, knm, km in kept:
            if knm.lower() != nm.lower():
                continue
            klo, khi = km.bounds
            inter = np.prod(np.clip(np.minimum(hi, khi) - np.maximum(lo, klo), 0, None))
            if inter > 0.5 * min(np.prod(hi - lo), np.prod(khi - klo)):
                dup = True
                break
        if dup:
            print(f"    dropped duplicate {el} ({nm})")
        else:
            kept.append((el, nm, m))
    return kept


def _cap(m: trimesh.Trimesh, y: float, outward: float) -> trimesh.Trimesh:
    """Closes the open loops a horizontal cut at height y left, with flat fans facing `outward` (+1 up, -1 down)."""
    m.merge_vertices()
    edges, counts = np.unique(m.edges_sorted, axis=0, return_counts=True)
    open_ = edges[counts == 1]
    on_plane = np.abs(m.vertices[:, 1] - y) < 1e-7
    open_ = open_[on_plane[open_[:, 0]] & on_plane[open_[:, 1]]]
    nxt: dict[int, list[int]] = defaultdict(list)
    for a, b in open_:
        nxt[int(a)].append(int(b))
        nxt[int(b)].append(int(a))
    verts = [m.vertices]
    faces = [m.faces]
    count = len(m.vertices)
    seen: set[int] = set()
    for start in list(nxt):
        if start in seen:
            continue
        loop, prev, cur = [start], -1, start
        seen.add(start)
        while True:
            options = [v for v in nxt[cur] if v != prev and v not in seen]
            if not options:
                break
            prev, cur = cur, options[0]
            seen.add(cur)
            loop.append(cur)
        if len(loop) < 3:
            continue
        centre = m.vertices[loop].mean(axis=0)
        fan = np.array([[count, loop[i], loop[(i + 1) % len(loop)]] for i in range(len(loop))])
        e1 = m.vertices[fan[:, 1]] - centre
        e2 = m.vertices[fan[:, 2]] - centre
        if np.cross(e1, e2)[:, 1].sum() * outward < 0:
            fan = fan[:, [0, 2, 1]]
        verts.append(centre[None])
        faces.append(fan)
        count += 1
    return trimesh.Trimesh(vertices=np.vstack(verts), faces=np.vstack(faces), process=False)


def cut_capped(m: trimesh.Trimesh, y: float) -> tuple[trimesh.Trimesh, trimesh.Trimesh]:
    """
    (part above, part below) a horizontal plane, cut exactly along it and each closed with a flat cap. The caps sit
    inside the bone, back to back: if simplification moves the two seams apart, the gap shows bone, not a hole.
    """
    return _cap(_clip(m, y, 1.0), y, -1.0), _cap(_clip(m, y, -1.0), y, 1.0)


def _clip(m: trimesh.Trimesh, y: float, keep: float) -> trimesh.Trimesh:
    """The part of a mesh above (keep = 1) or below (keep = -1) height y, triangles split exactly on the plane."""
    v = m.vertices
    d = (v[:, 1] - y) * keep
    inside = d >= 0
    verts = list(v)
    cache: dict[tuple[int, int], int] = {}

    def cut(a: int, b: int) -> int:
        key = (min(a, b), max(a, b))
        if key not in cache:
            p = v[a] + (v[b] - v[a]) * (d[a] / (d[a] - d[b]))
            p[1] = y
            cache[key] = len(verts)
            verts.append(p)
        return cache[key]

    faces: list[list[int]] = []
    for tri in m.faces.tolist():
        ins = [bool(inside[i]) for i in tri]
        n = sum(ins)
        if n == 3:
            faces.append(tri)
        elif n == 1:
            k = ins.index(True)
            a, b, c = tri[k:] + tri[:k]
            faces.append([a, cut(a, b), cut(a, c)])
        elif n == 2:
            k = ins.index(False)
            c, a, b = tri[k:] + tri[:k]  # c is outside; a, b follow in winding order
            faces += [[a, b, cut(b, c)], [a, cut(b, c), cut(c, a)]]
    out = trimesh.Trimesh(vertices=np.array(verts), faces=np.array(faces), process=False)
    out.remove_unreferenced_vertices()
    return out


# ------------------------------------------------------------------ inner ear (modelled)

def _unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def _tube(points: np.ndarray, radii: np.ndarray, sides: int = 8) -> trimesh.Trimesh:
    """Closed tube along a polyline (parallel-transport frames, capped ends)."""
    n = len(points)
    tan = np.gradient(points, axis=0)
    tan /= np.linalg.norm(tan, axis=1, keepdims=True)
    ref = np.array([0.0, 0.0, 1.0]) if abs(tan[0][2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    nrm = np.cross(tan[0], ref)
    nrm /= np.linalg.norm(nrm)
    ang = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    rings = []
    for i in range(n):
        nrm = nrm - tan[i] * np.dot(nrm, tan[i])
        nrm /= np.linalg.norm(nrm)
        bin_ = np.cross(tan[i], nrm)
        rings.append(points[i] + radii[i] * (np.cos(ang)[:, None] * nrm + np.sin(ang)[:, None] * bin_))
    v = np.vstack([np.vstack(rings), points[0], points[-1]])
    f = []
    for i in range(n - 1):
        for j in range(sides):
            a, b = i * sides + j, (i + 1) * sides + j
            c, d = (i + 1) * sides + (j + 1) % sides, i * sides + (j + 1) % sides
            f += [[a, d, b], [b, d, c]]
    c0, c1 = n * sides, n * sides + 1
    for j in range(sides):
        f.append([c0, (j + 1) % sides, j])
        f.append([c1, (n - 1) * sides + j, (n - 1) * sides + (j + 1) % sides])
    t = trimesh.Trimesh(vertices=v, faces=np.array(f), process=False)
    t.fix_normals()
    return t


def labyrinth(side: int) -> trimesh.Trimesh:
    """
    Bony labyrinth of one ear in BodyParts3D millimetres (side -1 = right, +1 = left): an ovoid vestibule, the three
    semicircular canals (lateral tilted 30 degrees up at the front, anterior and posterior vertical at about 45
    degrees to the midline, each with an ampulla) and a 2.6-turn cochlea in front of and medial to the vestibule,
    its apex pointing forward, outward and slightly down. Placed medial to the external acoustic meatus, inside the
    petrous part of the temporal bone (checked against BodyParts3D's temporal bones and external ear).
    """
    lat = np.array([side * 1.0, 0.0, 0.0])
    med = -lat
    ant = np.array([0.0, -1.0, 0.0])
    post = -ant
    sup = np.array([0.0, 0.0, 1.0])
    vest = np.array([side * 31.0, -90.0, 1506.0])
    parts: list[trimesh.Trimesh] = []

    # Vestibule: about 5 x 4 x 3 mm, long axis front to back.
    ball = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
    ball.apply_scale([1.5, 2.6, 2.1])
    ball.apply_translation(vest)
    parts.append(ball)

    def canal(plane_a: np.ndarray, plane_b: np.ndarray, to_centre: np.ndarray, radius: float,
              ampulla_dir: np.ndarray) -> trimesh.Trimesh:
        normal = _unit(np.cross(plane_a, plane_b))
        d = _unit(to_centre - normal * np.dot(to_centre, normal))
        centre = vest + d * radius * 0.95
        a = -d
        b = np.cross(normal, a)
        th = np.radians(np.linspace(40, 320, 56))
        pts = centre + radius * (np.cos(th)[:, None] * a + np.sin(th)[:, None] * b)
        if np.dot(pts[-1] - pts[0], ampulla_dir) > 0:
            pts = pts[::-1]  # ampulla first
        s = np.linspace(0, 1, len(pts))
        r = 0.45 + 0.45 * np.exp(-((s / 0.09) ** 2))
        return _tube(pts, r)

    tilt = _unit(np.cos(np.radians(30)) * ant + np.sin(np.radians(30)) * sup)
    parts.append(canal(tilt, lat, 0.85 * lat - 0.53 * tilt, 2.3, ant))  # lateral canal
    al = _unit(ant + lat)
    parts.append(canal(sup, al, sup + 0.3 * al, 3.2, al))  # anterior canal
    pl = _unit(post + lat)
    parts.append(canal(sup, pl, 0.95 * pl - 0.15 * sup, 3.1, -sup))  # posterior canal

    # Cochlea: base towards the internal acoustic meatus, 2.6 turns narrowing to the apex.
    base = vest + 4.0 * _unit(0.8 * ant + 0.6 * med) - 1.0 * sup
    axis = _unit(0.5 * ant + 0.75 * lat - 0.4 * sup)
    e1 = vest - base
    e1 = _unit(e1 - axis * np.dot(e1, axis))
    e2 = np.cross(axis, e1) * side  # mirror-symmetric coiling
    s = np.linspace(0, 1, 110)
    phi = s * 2.6 * 2 * np.pi
    rho = 3.5 * (1 - s) ** 0.85 + 0.7 * s
    ring = np.cos(phi)[:, None] * e1 + np.sin(phi)[:, None] * e2
    pts = base + axis[None] * (4.0 * s)[:, None] + rho[:, None] * ring
    parts.append(_tube(pts, 1.0 - 0.55 * s))

    mesh = trimesh.util.concatenate(parts)
    mesh.vertices = to_three(mesh.vertices)
    return mesh


# ------------------------------------------------------------------ thyroid and lymph nodes (modelled)
# Both are placed from landmarks of the loaded model (named meshes, in metres, Y up, facing +Z).

def _blob(half: tuple[float, float, float], centre: np.ndarray, subdivisions: int = 2,
          rotation: np.ndarray | None = None) -> trimesh.Trimesh:
    b = trimesh.creation.icosphere(subdivisions=subdivisions, radius=1.0)
    b.vertices = b.vertices * np.array(half)
    if rotation is not None:
        b.vertices = b.vertices @ rotation.T
    b.apply_translation(centre)
    return b


def thyroid(named: dict[str, trimesh.Trimesh]) -> trimesh.Trimesh:
    """
    Thyroid gland: two lobes about 5 cm tall, 2 cm wide and 1.7 cm deep, pointed at the upper pole, hugging the
    sides of the trachea from the thyroid cartilage down to about the sixth tracheal ring, joined in front of the
    second to fourth rings by an isthmus.
    """
    yc = named["cricoid cartilage"].bounds[0][1]  # lower edge of the cricoid
    tv = named["trachea"].vertices
    band = tv[(tv[:, 1] < yc - 0.006) & (tv[:, 1] > yc - 0.035)]
    cx, cz = band[:, 0].mean(), band[:, 2].mean()
    r = float(np.hypot(band[:, 0] - cx, band[:, 2] - cz).mean())
    parts = []
    for side in (-1.0, 1.0):
        lobe = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
        v = lobe.vertices.copy()
        v[:, [0, 2]] *= (1 - 0.45 * np.clip(v[:, 1], 0, 1))[:, None]  # pointed upper pole
        lobe.vertices = v * np.array([0.0105, 0.025, 0.0085])
        lobe.apply_transform(trimesh.transformations.rotation_matrix(np.radians(side * 10), [0, 0, 1]))
        lobe.apply_translation([cx + side * (r + 0.0085), yc - 0.01, cz + 0.003])
        parts.append(lobe)
    parts.append(_blob((0.011, 0.0075, 0.0035), np.array([cx, yc - 0.016, cz + r + 0.0025])))
    return trimesh.util.concatenate(parts)


def lymph_nodes(named: dict[str, trimesh.Trimesh]) -> trimesh.Trimesh:
    """
    The major lymph node groups as small bean-shaped nodes (3 to 8 mm), seeded for a fixed layout: deep cervical
    along each internal jugular vein up to the angle of the jaw, axillary in each armpit, superficial inguinal below
    each groin crease, para-aortic beside the abdominal aorta and tracheobronchial at the carina.
    """
    rng = np.random.default_rng(7)
    nodes: list[tuple[np.ndarray, float]] = []
    for side, sgn in (("left", 1.0), ("right", -1.0)):
        v = named[f"{side} internal jugular vein"].vertices
        lo, hi = v[v[:, 1].argmin()], v[v[:, 1].argmax()]
        for t in np.linspace(0.2, 2.6, 5):
            nodes.append((lo + (hi - lo) * t + np.array([sgn * 0.008, 0, -0.004]) + rng.normal(0, 0.002, 3),
                          0.0055 * rng.uniform(0.8, 1.2)))
        ax = named[f"{side} axillary vein"].vertices
        c = ax[np.abs(ax[:, 0]) < np.percentile(np.abs(ax[:, 0]), 50)].mean(axis=0)
        for _ in range(5):
            nodes.append((c + np.array([-sgn * 0.01, -0.02, 0]) + rng.normal(0, 0.009, 3),
                          0.006 * rng.uniform(0.8, 1.2)))
        fv = named[f"{side} femoral vein"].vertices
        top = fv[fv[:, 1] > fv[:, 1].max() - 0.03].mean(axis=0)
        for k in range(4):
            nodes.append((top + np.array([sgn * (0.012 * k - 0.014), -0.012 - 0.008 * (k % 2), 0.014])
                          + rng.normal(0, 0.002, 3), 0.007 * rng.uniform(0.8, 1.15)))
    ao = named["abdominal aorta"].vertices
    y0, y1 = ao[:, 1].min(), ao[:, 1].max()
    for t in (0.3, 0.55, 0.8):
        y = y0 + (y1 - y0) * t
        c = ao[np.abs(ao[:, 1] - y) < 0.006].mean(axis=0)
        for sgn in (-1.0, 1.0):
            nodes.append((c + np.array([sgn * 0.017, 0, -0.004]) + rng.normal(0, 0.0015, 3), 0.0045))
    tr = named["trachea"].vertices
    carina = tr[tr[:, 1] < tr[:, 1].min() + 0.01].mean(axis=0)
    for off in ([0.014, -0.006, 0.0], [-0.014, -0.004, 0.0], [0.0, -0.016, -0.006]):
        nodes.append((carina + np.array(off), 0.0055))
    parts = []
    for centre, size in nodes:
        q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        if np.linalg.det(q) < 0:
            q[:, 0] *= -1  # a rotation, not a mirror (that would turn the faces inside out)
        parts.append(_blob((size, size * 0.65, size * 0.5), centre, subdivisions=1, rotation=q))
    return trimesh.util.concatenate(parts)


MODELLED = {"thyroid": thyroid, "lymph_nodes": lymph_nodes}


def tint_lobes(items: list[tuple[str, str, trimesh.Trimesh]], lobes: list[set[str]], key: str) -> list[trimesh.Trimesh]:
    """Copies of a lung's meshes with every vertex coloured by its lobe: red, green, blue, or black when unassigned."""
    colours = np.array([[255, 0, 0, 255], [0, 255, 0, 255], [0, 0, 255, 255], [0, 0, 0, 255]], dtype=np.uint8)
    out = []
    counts = [0, 0, 0, 0]
    for el, _, m in items:
        lobe = next((i for i, els in enumerate(lobes) if el in els), 3)
        counts[lobe] += 1
        t = m.copy()
        t.visual = trimesh.visual.ColorVisuals(t, vertex_colors=np.tile(colours[lobe], (len(t.vertices), 1)))
        out.append(t)
    print(f"  {key} lobes (upper, middle, lower, unassigned elements): {counts}")
    return out


# ------------------------------------------------------------------ muscles

# Muscle meshes coarser than this (mean edge, metres) are subdivided to MUSCLE_EDGE and rounded before anything is
# baked: some BodyParts3D muscles are modelled with 8 mm facets.
MUSCLE_COARSE = 0.003
MUSCLE_EDGE = 0.004
# Thickness probe depths (metres) for telling tendon and aponeurosis from muscle belly.
PROBE = np.array([0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.5]) * 0.001


def _smoothstep(a: float, b: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _adjacency(n: int, faces: np.ndarray):
    from scipy.sparse import coo_matrix

    e = np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    a = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)).tocsr()
    a = ((a + a.T) > 0).astype(np.float64)
    return a


def _neighbour_smooth(values: np.ndarray, adj, passes: int) -> np.ndarray:
    deg = np.asarray(adj.sum(axis=1)).ravel()
    for _ in range(passes):
        values = (values + adj @ values) / (1 + deg)
    return values


def _cot_laplacian(v: np.ndarray, f: np.ndarray):
    """Cotangent weights (clamped positive, so the solve stays well posed) as a symmetric sparse matrix."""
    from scipy.sparse import coo_matrix

    rows, cols, vals = [], [], []
    for k in range(3):
        i, j, o = f[:, (k + 1) % 3], f[:, (k + 2) % 3], f[:, k]
        a = v[i] - v[o]
        b = v[j] - v[o]
        cot = np.einsum("ij,ij->i", a, b) / np.maximum(np.linalg.norm(np.cross(a, b), axis=1), 1e-12)
        w = np.clip(0.5 * cot, 1e-4, 50.0)
        rows += [i, j]
        cols += [j, i]
        vals += [w, w]
    n = len(v)
    return coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsr()


def fibre_field(m: trimesh.Trimesh, hint: np.ndarray | None) -> tuple[np.ndarray, np.ndarray]:
    """
    Fibre direction per vertex (unit, along the surface) and the coordinate along the fibres (0 to 1), per connected
    piece: a harmonic field between the two ends of the piece's long axis (or of the hint), so the fibres follow the
    muscle's own shape, converging on a tendon or fanning out over a flat muscle.
    """
    from scipy.sparse import diags, identity
    from scipy.sparse.csgraph import connected_components
    from scipy.sparse.linalg import spsolve

    v, f = m.vertices, m.faces
    n = len(v)
    _, labels = connected_components(_adjacency(n, f), directed=False)
    w = _cot_laplacian(v, f)
    lap = (diags(np.asarray(w.sum(axis=1)).ravel()) - w).tocsr()
    coord = np.zeros(n)
    axis_of = np.zeros((n, 3))
    for c in np.unique(labels):
        idx = np.nonzero(labels == c)[0]
        pts = v[idx]
        if hint is not None:
            axis = hint
        else:
            cov = np.cov((pts - pts.mean(axis=0)).T) if len(idx) > 3 else np.eye(3)
            axis = np.linalg.eigh(cov)[1][:, -1]
        axis_of[idx] = axis
        s = (pts - pts.mean(axis=0)) @ axis
        s = (s - s.min()) / max(s.max() - s.min(), 1e-9)
        lo, hi = s <= 0.02, s >= 0.98
        x = s.copy()
        x[lo], x[hi] = 0.0, 1.0
        free = ~(lo | hi)
        if free.any() and lo.any() and hi.any() and len(idx) > 8:
            sub = lap[idx][:, idx]
            a = sub[free][:, free] + identity(int(free.sum())) * 1e-12
            x[free] = spsolve(a.tocsc(), -(sub[free][:, ~free] @ x[~free]))
        coord[idx] = np.clip(x, 0.0, 1.0)
    # Gradient of the field per face (area weighted onto the vertices), kept in the tangent plane.
    tri = v[f]
    nrm = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area2 = np.maximum(np.linalg.norm(nrm, axis=1), 1e-18)
    nrm = nrm / area2[:, None]
    cf = coord[f]
    grad = (cf[:, 0, None] * np.cross(nrm, tri[:, 2] - tri[:, 1]) + cf[:, 1, None] * np.cross(nrm, tri[:, 0] - tri[:, 2])
            + cf[:, 2, None] * np.cross(nrm, tri[:, 1] - tri[:, 0]))
    gv = np.zeros((n, 3))
    for k in range(3):
        np.add.at(gv, f[:, k], grad)
    vn = m.vertex_normals
    gv -= vn * np.einsum("ij,ij->i", gv, vn)[:, None]
    length = np.linalg.norm(gv, axis=1)
    weak = length < 1e-9
    fallback = axis_of - vn * np.einsum("ij,ij->i", axis_of, vn)[:, None]
    gv[weak] = fallback[weak]
    gv /= np.maximum(np.linalg.norm(gv, axis=1), 1e-12)[:, None]
    return gv, coord


def tendon_weight(m: trimesh.Trimesh) -> np.ndarray:
    """
    How much each vertex is tendon or aponeurosis rather than muscle belly (0 to 1), from the shape alone: a sheet
    thinner than about 2 mm (aponeurosis), or a thin round cord (tendon). Thickness is probed inward along the normal
    for the opposite surface; a cord differs from a thin flat muscle by how much the normals turn around it.
    """
    from scipy.spatial import cKDTree

    count = int(np.clip(m.area / (0.0011 ** 2), 2000, 300000))
    pts, face = trimesh.sample.sample_surface(m, count, seed=7)
    pn = m.face_normals[face]
    pts = np.vstack([pts, m.vertices])
    pn = np.vstack([pn, m.vertex_normals])
    tree = cKDTree(pts)
    v, n = m.vertices, m.vertex_normals
    thick = np.full(len(v), np.inf)
    for t in PROBE[::-1]:
        d, j = tree.query(v - n * t)
        hit = (d < max(0.0006, 0.22 * t)) & (np.einsum("ij,ij->i", pn[j], n) < -0.3)
        thick[hit] = t
    sheet = 1.0 - _smoothstep(0.0013, 0.0023, thick)
    cord = np.zeros(len(v))
    cand_all = np.nonzero(thick < 0.0065)[0]
    for s0 in range(0, len(cand_all), 3000):
        cand = cand_all[s0:s0 + 3000]
        lists = tree.query_ball_point(v[cand], r=0.0035)
        sizes = np.fromiter((len(x) for x in lists), dtype=np.int64, count=len(lists))
        if not sizes.sum():
            continue
        rows = np.repeat(np.arange(len(cand)), sizes)
        cols = np.concatenate([np.asarray(x, dtype=np.int64) for x in lists])
        same = np.einsum("ij,ij->i", pn[cols], n[cand][rows]) > 0
        acc = np.zeros((len(cand), 3))
        np.add.at(acc, rows[same], pn[cols[same]])
        cnt = np.maximum(np.bincount(rows[same], minlength=len(cand)), 1)
        spread = np.linalg.norm(acc, axis=1) / cnt
        cord[cand] = (1.0 - _smoothstep(0.004, 0.0065, thick[cand])) * (1.0 - _smoothstep(0.74, 0.88, spread))
    return np.maximum(sheet, cord)


def _hemisphere(count: int) -> np.ndarray:
    """Cosine-weighted directions over the hemisphere around +Z (a Fibonacci spiral on the disc, lifted)."""
    i = np.arange(count) + 0.5
    r = np.sqrt(i / count)
    phi = i * np.pi * (3 - np.sqrt(5))
    return np.column_stack([r * np.cos(phi), r * np.sin(phi), np.sqrt(1 - r * r)])


def bake_occlusion(muscles: list[trimesh.Trimesh], bones: list[trimesh.Trimesh], fascia: set[int]
                   ) -> tuple[list[np.ndarray], dict[int, np.ndarray]]:
    """
    Ambient occlusion per muscle vertex from the muscles and bones around it (not the muscle itself): dark in the
    grooves between neighbouring bellies, under overlapping edges, in the armpit and between the fingers. Rays march
    a 2.5 mm voxel grid up to 3.5 cm. For the `fascia` elements also the depth, straight in, to the muscle or bone
    under each vertex (up to 8 mm).
    """
    cell, reach, step = 0.0025, 0.035, 0.0012
    allv = np.vstack([m.vertices for m in muscles + bones])
    lo = allv.min(axis=0) - 4 * cell
    dims = np.ceil((allv.max(axis=0) - lo) / cell).astype(int) + 8
    grid = np.zeros(dims, dtype=np.int16)

    def mark(m: trimesh.Trimesh, ident: int) -> None:
        tri = m.triangles
        pts = np.vstack([m.vertices, tri.mean(axis=1), (tri[:, 0] + tri[:, 1]) / 2, (tri[:, 1] + tri[:, 2]) / 2,
                         (tri[:, 2] + tri[:, 0]) / 2])
        ijk = np.floor((pts - lo) / cell).astype(int)
        grid[ijk[:, 0], ijk[:, 1], ijk[:, 2]] = ident

    for k, m in enumerate(muscles):
        mark(m, k + 1)
    for m in bones:
        mark(m, 32000)
    dirs = _hemisphere(16).astype(np.float32)
    ts = np.arange(0.001, reach, step, dtype=np.float32)
    fall = 1.0 - ts / reach
    lo32 = lo.astype(np.float32)
    out = []
    depth: dict[int, np.ndarray] = {}
    inward = np.arange(0.0005, 0.008, 0.0005, dtype=np.float32)
    for k, m in enumerate(muscles):
        v = m.vertices.astype(np.float32)
        n = m.vertex_normals.astype(np.float32)
        ref = np.where(np.abs(n[:, 1:2]) < 0.9, np.array([[0.0, 1.0, 0.0]], np.float32),
                       np.array([[1.0, 0.0, 0.0]], np.float32))
        t1 = np.cross(n, ref)
        t1 /= np.maximum(np.linalg.norm(t1, axis=1), 1e-12)[:, None]
        t2 = np.cross(n, t1)
        occ = np.zeros(len(v))
        for s0 in range(0, len(v), 2000):
            sl = slice(s0, s0 + 2000)
            d = (dirs[None, :, 0, None] * t1[sl, None, :] + dirs[None, :, 1, None] * t2[sl, None, :]
                 + dirs[None, :, 2, None] * n[sl, None, :])  # (c, 16, 3)
            p = v[sl, None, None, :] + d[:, :, None, :] * ts[None, None, :, None]  # (c, 16, steps, 3)
            ijk = np.floor((p - lo32) / cell).astype(np.int32)
            for a in range(3):
                np.clip(ijk[..., a], 0, dims[a] - 1, out=ijk[..., a])
            g = grid[ijk[..., 0], ijk[..., 1], ijk[..., 2]]
            hit = (g != 0) & (g != k + 1)
            first = hit.argmax(axis=2)
            w = np.where(hit.any(axis=2), fall[first], 0.0)
            occ[sl] = w.mean(axis=1)
        out.append(1.0 - occ)
        if k in fascia:
            p = v[:, None, :] - n[:, None, :] * inward[None, :, None]
            ijk = np.floor((p - lo32) / cell).astype(np.int32)
            for a in range(3):
                np.clip(ijk[..., a], 0, dims[a] - 1, out=ijk[..., a])
            g = grid[ijk[..., 0], ijk[..., 1], ijk[..., 2]]
            hit = (g != 0) & (g != k + 1)
            depth[k] = np.where(hit.any(axis=1), inward[hit.argmax(axis=1)], 0.01)
    return out, depth


def _octahedral(d: np.ndarray) -> np.ndarray:
    """Axial unit vectors (sign free) to two values in [0, 1]: octahedral encoding of the half with z >= 0."""
    d = np.where(d[:, 2:3] < 0, -d, d)
    d = d / np.maximum(np.abs(d).sum(axis=1, keepdims=True), 1e-12)
    return np.column_stack([d[:, 0] * 0.5 + 0.5, d[:, 1] * 0.5 + 0.5])


def prepare_muscles(items: list[tuple[str, str, trimesh.Trimesh]], bones: list[trimesh.Trimesh],
                    modelled: list[tuple[str, trimesh.Trimesh, np.ndarray, np.ndarray]]
                    ) -> list[tuple[str, trimesh.Trimesh]]:
    """
    Muscle elements ready for the viewer: coarse ones subdivided and rounded, then three things baked into the vertex
    colour (COLOR_0) for the shader: red = tendon or aponeurosis (0 to 1; tendinous elements lying thin over a muscle
    get 0.8, which the shader draws as translucent fascia), green = ambient occlusion, blue and alpha = fibre
    direction (octahedral, see _octahedral). `modelled` muscles (see latissimus() and jaw_muscles()) bring their own
    fibres and tendons. Returns (name, mesh) pairs.
    """
    ready: list[tuple[str, trimesh.Trimesh, np.ndarray, np.ndarray]] = []
    for el, name, src in items:
        m = trimesh.Trimesh(vertices=src.vertices.copy(), faces=src.faces.copy(), process=True)
        m.remove_unreferenced_vertices()
        if m.edges_unique_length.mean() > MUSCLE_COARSE:
            v, f = trimesh.remesh.subdivide_to_size(m.vertices, m.faces, max_edge=MUSCLE_EDGE, max_iter=6)
            m = trimesh.Trimesh(vertices=v, faces=f, process=True)
            trimesh.smoothing.filter_taubin(m, lamb=0.5, nu=0.53, iterations=12)
        side = -1.0 if m.vertices[:, 0].mean() < 0 else 1.0
        hint = next((np.array(h, dtype=np.float64) for rx, h in FIBRE_HINT if rx.search(name)), None)
        if hint is not None:
            hint = hint * np.array([-side, 1.0, 1.0])  # given for the right side (x < 0)
            hint /= np.linalg.norm(hint)
        direction, _ = fibre_field(m, hint)
        tendon = np.ones(len(m.vertices)) if TENDINOUS.search(name) else tendon_weight(m)
        if FASCIA_LATA.search(name):
            # The iliotibial tract and the gluteal aponeurosis above it lie thin on muscle: translucent fascia (the
            # shader lets some red through below about 0.95), thinnest over gluteus medius.
            y = m.vertices[:, 1]
            tendon = 0.88 - 0.06 * _smoothstep(0.7, 0.85, (y - y.min()) / max(np.ptp(y), 1e-9))
        # Smoothed over about a centimetre, so the border between muscle and tendon runs clean instead of ragged.
        passes = int(np.clip(round(0.01 / max(m.edges_unique_length.mean(), 1e-4)), 2, 8))
        tendon = _neighbour_smooth(tendon, _adjacency(len(m.vertices), m.faces), passes)
        ready.append((name, m, direction, tendon))
        if len(ready) % 40 == 0:
            print(f"  ... {len(ready)} muscles prepared", flush=True)
    ready += modelled
    fascia = {k for k, (name, *_) in enumerate(ready) if TENDINOUS.search(name)}
    occlusion, depth = bake_occlusion([m for _, m, _, _ in ready], bones, fascia)
    out = []
    for k, ((name, m, direction, tendon), ao) in enumerate(zip(ready, occlusion)):
        adj = _adjacency(len(m.vertices), m.faces)
        ao = _neighbour_smooth(ao, adj, 2)
        if k in depth:
            # Fascia lying within a few millimetres of the muscle under it reads as a thin, translucent sheet.
            thin = 1.0 - _smoothstep(0.0015, 0.004, _neighbour_smooth(depth[k], adj, 3))
            tendon = np.minimum(tendon, 1.0 - 0.2 * thin)
        mean_t = float(tendon.mean())
        if mean_t > 0.3:
            print(f"    tendon {mean_t:.2f}  {name}")
        rgba = np.column_stack([tendon, ao, _octahedral(direction)])
        m.visual = trimesh.visual.ColorVisuals(m, vertex_colors=np.round(np.clip(rgba, 0, 1) * 255).astype(np.uint8))
        out.append((name, m))
    return out


def muscle_regions(named: list[tuple[str, trimesh.Trimesh]], shift: np.ndarray) -> dict[str, list[trimesh.Trimesh]]:
    """
    Splits the muscles into head and neck, trunk, arms and legs by each element's centre (in the final frame: metres,
    feet on y = 0, once `shift` is applied). Smaller meshes keep more detail through the optimiser (its error is
    relative to a mesh's size) and are culled when off screen.
    """
    out: dict[str, list[trimesh.Trimesh]] = defaultdict(list)
    for name, m in named:
        c = m.vertices.mean(axis=0) + shift
        side = "r" if c[0] < 0 else "l"
        if c[1] > 1.48 and abs(c[0]) < 0.1:
            region = "muscles_head"
        elif abs(c[0]) > 0.165 and c[1] > 0.6:
            region = f"muscles_arm_{side}"
        elif c[1] < 0.93 and abs(c[0]) > 0.02:
            region = f"muscles_leg_{side}"
        else:
            region = "muscles_trunk"
        out[region].append(m)
        print(f"    {region:18s} {name}")
    return dict(sorted(out.items()))


# ------------------------------------------------------------------ muscles BodyParts3D lacks (modelled)
# The latissimus dorsi, temporalis and masseter are not in BodyParts3D 4.0. Each is modelled as a sheet laid over
# the anatomy under it: a height field over a 2D parameter domain (around the trunk for the latissimus, across the
# side of the head for the jaw muscles), its border drawn from landmarks of the loaded model and smoothed, its
# thickness tapering to a thin edge, closed into one solid. Heights come from rays marched through a fine voxel grid
# of the structures underneath.

class _Voxels:
    """Bit flags on a voxel grid: which kinds of surface pass through each cell."""

    def __init__(self, lo: np.ndarray, hi: np.ndarray, cell: float):
        self.lo = lo.astype(np.float64)
        self.cell = cell
        self.dims = np.ceil((hi - lo) / cell).astype(int) + 1
        self.grid = np.zeros(self.dims, dtype=np.uint8)

    def mark(self, meshes: list[trimesh.Trimesh], bit: int, spacing: float) -> None:
        rng = np.random.default_rng(3)
        for m in meshes:
            tri = m.triangles
            keep = np.all((tri >= self.lo - spacing) & (tri <= self.lo + self.dims * self.cell + spacing), axis=(1, 2))
            tri = tri[keep]
            if not len(tri):
                continue
            area = np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1) / 2
            count = np.clip(np.ceil(area / spacing ** 2), 1, 400).astype(int)
            idx = np.repeat(np.arange(len(tri)), count)
            r1 = np.sqrt(rng.random(len(idx)))
            r2 = rng.random(len(idx))
            pts = ((1 - r1)[:, None] * tri[idx, 0] + (r1 * (1 - r2))[:, None] * tri[idx, 1]
                   + (r1 * r2)[:, None] * tri[idx, 2])
            pts = np.vstack([pts, tri.reshape(-1, 3)])
            ijk = np.floor((pts - self.lo) / self.cell).astype(int)
            ok = np.all((ijk >= 0) & (ijk < self.dims), axis=1)
            ijk = ijk[ok]
            self.grid[ijk[:, 0], ijk[:, 1], ijk[:, 2]] |= bit

    def march(self, origins: np.ndarray, dirs: np.ndarray, ts: np.ndarray) -> np.ndarray:
        """Flags met along each ray at each step: (rays, steps)."""
        out = np.zeros((len(origins), len(ts)), dtype=np.uint8)
        for s0 in range(0, len(origins), 4000):
            sl = slice(s0, s0 + 4000)
            p = origins[sl, None, :] + dirs[sl, None, :] * ts[None, :, None]
            ijk = np.floor((p - self.lo) / self.cell).astype(np.int32)
            ok = np.all((ijk >= 0) & (ijk < self.dims), axis=2)
            ijk = np.where(ok[..., None], ijk, 0)
            out[sl] = np.where(ok, self.grid[ijk[..., 0], ijk[..., 1], ijk[..., 2]], 0)
        return out


def _first(hits: np.ndarray, ts: np.ndarray, limit: np.ndarray | None = None) -> np.ndarray:
    """Distance of the first hit along each ray (NaN if none, or none before `limit`)."""
    any_ = hits.any(axis=1)
    t = np.where(any_, ts[hits.argmax(axis=1)], np.nan)
    if limit is not None:
        t = np.where(t < limit, t, np.nan)
    return t


def _last_before(hits: np.ndarray, ts: np.ndarray, limit: np.ndarray) -> np.ndarray:
    """Distance of the last hit before `limit` along each ray (NaN if none)."""
    masked = hits & (ts[None, :] < limit[:, None])
    any_ = masked.any(axis=1)
    last = masked.shape[1] - 1 - masked[:, ::-1].argmax(axis=1)
    return np.where(any_, ts[last], np.nan)


def _fill_nan(f: np.ndarray) -> np.ndarray:
    """NaN cells take the value of the nearest valid one."""
    from scipy.ndimage import distance_transform_edt

    bad = np.isnan(f)
    if not bad.any() or bad.all():
        return np.nan_to_num(f)
    idx = distance_transform_edt(bad, return_distances=False, return_indices=True)
    return f[tuple(idx)]


def _chaikin(poly: np.ndarray, rounds: int = 3) -> np.ndarray:
    """Corner-cutting smoothing of a closed polygon."""
    for _ in range(rounds):
        nxt = np.roll(poly, -1, axis=0)
        poly = np.column_stack([0.75 * poly + 0.25 * nxt, 0.25 * poly + 0.75 * nxt]).reshape(-1, 2)
    return poly


def _signed_distance(pts: np.ndarray, poly: np.ndarray) -> np.ndarray:
    """Distance from each 2D point to a closed polygon: positive inside, negative outside."""
    a = poly
    b = np.roll(poly, -1, axis=0)
    out = np.empty(len(pts))
    inside = np.zeros(len(pts), dtype=bool)
    for s0 in range(0, len(pts), 20000):
        p = pts[s0:s0 + 20000]
        pa = p[:, None, :] - a[None]
        ba = (b - a)[None]
        h = np.clip((pa * ba).sum(-1) / np.maximum((ba * ba).sum(-1), 1e-18), 0, 1)
        out[s0:s0 + 20000] = np.linalg.norm(pa - ba * h[..., None], axis=-1).min(axis=1)
        cross = ((a[None, :, 1] > p[:, None, 1]) != (b[None, :, 1] > p[:, None, 1])) & (
            p[:, None, 0] < (b[None, :, 0] - a[None, :, 0]) * (p[:, None, 1] - a[None, :, 1])
            / np.where(np.abs(b[None, :, 1] - a[None, :, 1]) < 1e-18, 1e-18, b[None, :, 1] - a[None, :, 1])
            + a[None, :, 0])
        inside[s0:s0 + 20000] = cross.sum(axis=1) % 2 == 1
    return np.where(inside, out, -out)


def _param_sheet(u: np.ndarray, v: np.ndarray, poly: np.ndarray, place) -> trimesh.Trimesh:
    """
    A closed sheet over the part of the (u, v) grid inside `poly` (metres in parameter space). `place(u, v, sd)`
    returns (outer, inner) 3D points for parameter points and their signed distance to the border. Grid points just
    outside are pulled onto the border, so the outline runs smooth, not in steps.
    """
    nu, nv = len(u), len(v)
    uu, vv = np.meshgrid(u, v, indexing="ij")
    flat = np.column_stack([uu.ravel(), vv.ravel()])
    sd = _signed_distance(flat, poly).reshape(nu, nv)
    du, dv = u[1] - u[0], v[1] - v[0]
    h = 0.75 * max(du, dv)
    active = sd > -h
    gu, gv = np.gradient(sd, du, dv)
    norm = np.maximum(np.hypot(gu, gv), 1e-9)
    pu = np.where(sd < 0, uu - sd * gu / norm, uu)
    pv = np.where(sd < 0, vv - sd * gv / norm, vv)
    psd = np.where(sd < 0, 0.0, sd)
    ids = -np.ones((nu, nv), dtype=np.int64)
    ids[active] = np.arange(active.sum())
    pu_a, pv_a, psd_a = pu[active], pv[active], psd[active]
    outer, inner = place(pu_a, pv_a, psd_a)
    n = len(outer)
    faces = []
    a, b, c, d = ids[:-1, :-1], ids[1:, :-1], ids[1:, 1:], ids[:-1, 1:]
    for t in ((a, b, c), (a, c, d)):
        f = np.stack([x.ravel() for x in t], axis=1)
        faces.append(f[(f >= 0).all(axis=1)])
    # Cells with three corners inside get the one triangle they can.
    for t in ((a, b, d), (b, c, d)):
        f = np.stack([x.ravel() for x in t], axis=1)
        full = (a.ravel() >= 0) & (b.ravel() >= 0) & (c.ravel() >= 0) & (d.ravel() >= 0)
        faces.append(f[(f >= 0).all(axis=1) & ~full])
    top = np.vstack(faces)
    # Edges used once are the border: rim quads join the outer and inner surfaces there.
    e = np.vstack([top[:, [0, 1]], top[:, [1, 2]], top[:, [2, 0]]])
    key = np.sort(e, axis=1)
    _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    border = e[cnt[inv.ravel()] == 1]
    rim = np.vstack([np.column_stack([border[:, 1], border[:, 0], border[:, 0] + n]),
                     np.column_stack([border[:, 1], border[:, 0] + n, border[:, 1] + n])])
    faces = np.vstack([top, top[:, ::-1] + n, rim])
    mesh = trimesh.Trimesh(vertices=np.vstack([outer, inner]), faces=faces, process=False)
    mesh.merge_vertices(digits_vertex=7)
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    return mesh


def _orient_out(mesh: trimesh.Trimesh) -> None:
    """Turns the closed sheet's faces outward (a solid with outward faces has a positive volume)."""
    if mesh.volume < 0:
        mesh.invert()


def _converge(mesh: trimesh.Trimesh, target: np.ndarray) -> np.ndarray:
    """Fibre directions converging on a point (an insertion), kept along the surface."""
    d = target[None] - mesh.vertices
    n = mesh.vertex_normals
    d -= n * np.einsum("ij,ij->i", d, n)[:, None]
    return d / np.maximum(np.linalg.norm(d, axis=1), 1e-9)[:, None]


def latissimus(named: dict[str, trimesh.Trimesh], under: list[trimesh.Trimesh], over: list[trimesh.Trimesh]
               ) -> list[tuple[str, trimesh.Trimesh, np.ndarray, np.ndarray]]:
    """
    Latissimus dorsi of each side, laid over the deep back muscles, ribs, serratus and teres major (`under`) and
    under the trapezius (`over`). Borders: the spinous processes from T7 down, by the thoracolumbar fascia, to the
    sacrum; the iliac crest; the lower ribs at the flank; just over the inferior angle of the scapula; converging
    through the posterior axillary fold onto teres major's insertion near the humerus. The medial part is aponeurosis
    (the thoracolumbar fascia, widest over the loins), the fibres converge on the insertion, the belly is 7 to 10 mm
    thick and thins to its free borders.
    """
    from scipy.ndimage import gaussian_filter, maximum_filter, minimum_filter

    def pts(name: str) -> np.ndarray:
        return named[name].vertices

    skin = pts("skin")
    mid = skin[np.abs(skin[:, 0]) < 0.03]
    ys = np.arange(0.84, 1.34, 0.005)
    zc = np.array([0.5 * (mid[np.abs(mid[:, 1] - y) < 0.004, 2].min() + mid[np.abs(mid[:, 1] - y) < 0.004, 2].max())
                   if (np.abs(mid[:, 1] - y) < 0.004).sum() > 4 else np.nan for y in ys])
    zc = gaussian_filter(_fill_nan(zc), 4)

    def axis_z(y: np.ndarray) -> np.ndarray:
        return np.interp(y, ys, zc)

    t7 = pts("seventh thoracic vertebra")
    t7 = t7[t7[:, 2].argmin()]
    l5 = pts("fifth lumbar vertebra")
    l5 = l5[l5[:, 2].argmin()]
    vox = _Voxels(np.array([-0.26, 0.82, -0.12]), np.array([0.26, 1.36, 0.26]), 0.0012)
    vox.mark(under, 1, 0.0007)
    vox.mark(over, 2, 0.0007)
    vox.mark([named["skin"]], 4, 0.0007)
    out = []
    for side, word in ((-1.0, "right"), (1.0, "left")):
        ang = pts(f"{word} scapula")
        ang = ang[ang[:, 1].argmin()]
        teres = pts(f"{word} teres major")
        ins = teres[(teres[:, 0] * side).argmax()]
        hip = pts(f"{word} hip bone")

        def phi_of(p: np.ndarray) -> np.ndarray:
            return np.degrees(np.arctan2(p[:, 0] * side, axis_z(p[:, 1]) - p[:, 2]))

        # Iliac crest: the top of the hip bone seen from the trunk's axis, per degree round it.
        hp = phi_of(hip)
        crest = np.array([hip[(np.abs(hp - a) < 1.5), 1].max() if (np.abs(hp - a) < 1.5).any() else np.nan
                          for a in range(0, 100)])
        crest = _fill_nan(crest)
        a_ang = float(phi_of(ang[None])[0])
        a_ins = float(phi_of(ins[None])[0])
        r0 = 0.12  # metres per radian round the trunk, for distances in parameter space

        def uv(a: float, y: float) -> tuple[float, float]:
            return (np.radians(a) * r0, y)

        c = lambda a: float(crest[int(np.clip(round(a), 0, 99))]) + 0.006  # noqa: E731
        border = [uv(0, l5[1] - 0.025)]
        border += [uv(a, c(a)) for a in (10, 18, 26, 34, 42, 50)]
        border += [uv(56, c(56) + 0.02), uv(66, c(56) + 0.1), uv(74, ins[1] - 0.12), uv(a_ins + 3, ins[1] - 0.06),
                   uv(a_ins + 4, ins[1] - 0.02), uv(a_ins + 1, ins[1] + 0.008), uv(a_ins - 6, ins[1] + 0.006),
                   uv(a_ang + 8, ang[1] + 0.022), uv(a_ang, ang[1] + 0.016), uv(a_ang - 14, t7[1] + 0.008),
                   uv(0, t7[1] + 0.004)]
        poly = _chaikin(np.array(border), 3)
        # Keep the medial edge on the midline: corner cutting pulled it off.
        poly[:, 0] = np.where(poly[:, 0] < np.radians(1.5) * r0, 0.0, poly[:, 0])

        # Rays from the trunk's axis outward: the outermost structure under the muscle, the trapezius over it, the
        # inner layer of the skin as a ceiling.
        a_grid = np.radians(np.arange(-2.0, 104.0, 0.7))
        y_grid = np.arange(0.86, 1.33, 0.0022)
        aa, yy = np.meshgrid(a_grid, y_grid, indexing="ij")
        origins = np.column_stack([np.zeros(aa.size), yy.ravel(), axis_z(yy.ravel())])
        dirs = np.column_stack([side * np.sin(aa.ravel()), np.zeros(aa.size), -np.cos(aa.ravel())])
        ts = np.arange(0.02, 0.3, 0.0006)
        flags = vox.march(origins, dirs, ts)
        r_skin = _first((flags & 4) > 0, ts)
        r_skin = np.where(np.isnan(r_skin), 0.3, r_skin)
        r_under = _last_before((flags & 1) > 0, ts, r_skin)
        r_trap = _first((flags & 2) > 0, ts, r_skin)
        shape = aa.shape
        r_under = _fill_nan(r_under.reshape(shape))
        # Bridge the grooves between ribs and spinous processes, then smooth; never sink below what lies under.
        base = gaussian_filter(maximum_filter(r_under, size=5), 1.6)
        base = np.maximum(base, r_under) + 0.0014
        base = gaussian_filter(base, 0.8)
        base = np.maximum(base, r_under + 0.0011)
        ceiling = r_skin.reshape(shape) - 0.0025
        trap = r_trap.reshape(shape)
        trap = np.where(np.isnan(trap), 1.0, trap)
        trap = gaussian_filter(minimum_filter(trap, size=5), 1.0) - 0.001

        def field(f: np.ndarray, pa: np.ndarray, py: np.ndarray) -> np.ndarray:
            from scipy.ndimage import map_coordinates

            ia = (pa / r0 - a_grid[0]) / (a_grid[1] - a_grid[0])
            iy = (py - y_grid[0]) / (y_grid[1] - y_grid[0])
            return map_coordinates(f, [ia, iy], order=1, mode="nearest")

        ins_p = ins.copy()
        y_ap = np.array([l5[1], t7[1]])

        def thickness(pa: np.ndarray, py: np.ndarray, psd: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            # Aponeurosis: a band beside the spine, about 9 cm wide over the loins, 2.5 cm at T7.
            reach = np.interp(py, y_ap, [0.08, 0.022])
            apo = 1.0 - _smoothstep(-0.012, 0.012, pa - reach)
            close = 1.0 - _smoothstep(0.02, 0.09, np.hypot(np.radians(a_ins) * r0 - pa, ins_p[1] - py))
            t = (0.007 + 0.004 * close) * (1 - apo) + 0.0015 * apo
            return t * (0.08 + 0.92 * _smoothstep(0.0, 0.016, psd)), apo

        def place(pu: np.ndarray, pv: np.ndarray, psd: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            t, _ = thickness(pu, pv, psd)
            inner_r = field(base, pu, pv)
            outer_r = np.minimum(inner_r + t, field(ceiling, pu, pv))
            cap = field(trap, pu, pv)
            outer_r = np.minimum(outer_r, cap)
            inner_r = np.minimum(inner_r, outer_r - 0.0004)
            a = pu / r0
            z0 = axis_z(pv)

            def to3(r: np.ndarray) -> np.ndarray:
                return np.column_stack([side * r * np.sin(a), pv, z0 - r * np.cos(a)])

            return to3(outer_r), to3(inner_r)

        u = np.arange(0.0, np.radians(103.0) * r0, 0.0019)
        v = np.arange(0.88, 1.31, 0.0022)
        mesh = _param_sheet(u, v, poly, place)
        _orient_out(mesh)
        p = mesh.vertices
        # Parameters again for the (merged) vertices: angle and height, from the positions.
        pa = np.radians(np.abs(np.degrees(np.arctan2(p[:, 0] * side, axis_z(p[:, 1]) - p[:, 2])))) * r0
        _, apo = thickness(pa, p[:, 1], np.full(len(p), 1.0))
        tendon = np.maximum(apo, 1.0 - _smoothstep(0.015, 0.035, np.linalg.norm(p - ins_p, axis=1)))
        fibre = _converge(mesh, ins_p)
        print(f"  {word} latissimus dorsi: {len(mesh.faces)} triangles")
        out.append((f"{word} latissimus dorsi", mesh, fibre, tendon))
    return out


def jaw_muscles(named: dict[str, trimesh.Trimesh]) -> list[tuple[str, trimesh.Trimesh, np.ndarray, np.ndarray]]:
    """
    Temporalis and masseter of each side, laid over the skull and mandible (seen from the side, as height fields
    across the head). Temporalis: a fan filling the temporal fossa, from the superior temporal line down to the
    zygomatic arch, its fibres converging on the coronoid process under the arch, a short pale tendon where they
    gather. Masseter: from the lower border of the zygomatic arch to the angle and lateral surface of the ramus, about
    a centimetre thick, fibres running down and back, tendinous along its origin.
    """
    from scipy.ndimage import gaussian_filter, map_coordinates, maximum_filter

    skull = [m for k, m in named.items() if SKULL.search(k) and not re.search(r"tooth|teeth|incisor|canine|molar", k)]
    vox = _Voxels(np.array([-0.11, 1.40, -0.05]), np.array([0.11, 1.67, 0.21]), 0.0007)
    vox.mark(skull, 1, 0.0005)
    zs = np.arange(-0.03, 0.19, 0.001)
    ys = np.arange(1.41, 1.65, 0.001)
    zz, yy = np.meshgrid(zs, ys, indexing="ij")
    ts = np.arange(0.0, 0.12, 0.0003)
    mand = named["mandible"].vertices
    out = []
    for side, word in ((-1.0, "right"), (1.0, "left")):
        origins = np.column_stack([np.full(zz.size, side * 0.12), yy.ravel(), zz.ravel()])
        dirs = np.tile([-side, 0.0, 0.0], (zz.size, 1))
        flags = vox.march(origins, dirs, ts)
        lat_bone = 0.12 - _first((flags & 1) > 0, ts)
        bone = _fill_nan(lat_bone.reshape(zz.shape))
        # Bridge small hollows (sutures, foramina) and smooth; never sink into the bone. (The scalp of the model is
        # thinner than these muscles, so unlike the latissimus they are not kept under the skin, which the Muscles view
        # doesn't draw.)
        base = gaussian_filter(maximum_filter(bone, size=5), 1.5)
        base = np.maximum(base, bone) + 0.001

        def at(f: np.ndarray, pz: np.ndarray, py: np.ndarray) -> np.ndarray:
            return map_coordinates(f, [(pz - zs[0]) / 0.001, (py - ys[0]) / 0.001], order=1, mode="nearest")

        half = mand[mand[:, 0] * side > 0.02]
        ramus = half[half[:, 2] < 0.125]
        condyle = ramus[ramus[:, 1].argmax()]
        front = half[(half[:, 2] > 0.12) & (half[:, 2] < 0.15)]
        coronoid = front[front[:, 1].argmax()]
        angle = half[(half[:, 1] + half[:, 2]).argmin()]
        zyg = named[f"{word} zygomatic bone"].vertices
        arch_pts = np.vstack([zyg, named[f"{word} temporal bone"].vertices])
        arch_pts = arch_pts[(arch_pts[:, 0] * side > 0.055) & (arch_pts[:, 1] < 1.53) & (arch_pts[:, 2] > 0.085)]

        def arch_low(z: float) -> float:
            sel = arch_pts[np.abs(arch_pts[:, 2] - z) < 0.004]
            return float(sel[:, 1].min()) if len(sel) else float(arch_pts[:, 1].min())

        # Top of the arch, column by column: where the outermost bone steps in to the wall of the temporal fossa.
        def arch_top(z: float) -> float:
            lo = arch_low(z)
            col = int(round((z - zs[0]) / 0.001))
            rows = np.nonzero((ys > lo + 0.004) & (ys < lo + 0.03))[0]
            ref = bone[col, rows[0]]
            step = np.nonzero(bone[col, rows] < ref - 0.004)[0]
            return float(ys[rows[step[0]]]) if len(step) else lo + 0.014

        def lower_border(z: float) -> float:
            sel = half[np.abs(half[:, 2] - z) < 0.003]
            return float(sel[:, 1].min())

        def post_border(y: float) -> float:
            sel = ramus[np.abs(ramus[:, 1] - y) < 0.003]
            return float(sel[:, 2].min()) if len(sel) else float(condyle[2])

        # Masseter.
        z_back = float(condyle[2]) + 0.008
        z_zyg = float(zyg[:, 2].min()) + 0.022
        border = [(z, arch_low(z) - 0.001) for z in np.linspace(z_back, z_zyg, 8)]
        border += [(z_zyg + 0.002, arch_low(z_zyg) - 0.02), (float(angle[2]) + 0.04, lower_border(angle[2] + 0.04) + 0.006)]
        border += [(z, lower_border(z) + 0.003) for z in np.linspace(angle[2] + 0.03, angle[2] + 0.004, 5)]
        border += [(post_border(y) + 0.002, y) for y in np.linspace(float(angle[1]) + 0.008, arch_low(z_back) - 0.012, 6)]
        poly = _chaikin(np.array(border), 3)
        top_y = np.array([arch_low(z) for z in zs])

        def m_thick(pz: np.ndarray, py: np.ndarray, psd: np.ndarray) -> np.ndarray:
            return (0.0035 + 0.0075 * _smoothstep(0.0, 0.012, psd)) * (0.1 + 0.9 * _smoothstep(0.0, 0.008, psd))

        def m_place(pz: np.ndarray, py: np.ndarray, psd: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            inner = at(base, pz, py)
            outer = inner + m_thick(pz, py, psd)
            return (np.column_stack([side * outer, py, pz]), np.column_stack([side * inner, py, pz]))

        mesh = _param_sheet(np.arange(0.07, 0.17, 0.0008), np.arange(1.42, 1.52, 0.0008), poly, m_place)
        _orient_out(mesh)
        p = mesh.vertices
        fib = np.tile([0.0, -0.86, -0.51], (len(p), 1))
        n = mesh.vertex_normals
        fib -= n * np.einsum("ij,ij->i", fib, n)[:, None]
        fib /= np.maximum(np.linalg.norm(fib, axis=1), 1e-9)[:, None]
        tendon = _smoothstep(-0.014, -0.004, p[:, 1] - np.interp(p[:, 2], zs, top_y))
        out.append((f"{word} masseter", mesh, fib, tendon))
        print(f"  {word} masseter: {len(mesh.faces)} triangles")

        # Temporalis.
        z_front = float(zyg[zyg[:, 1].argmax(), 2]) - 0.007
        tops = [(z, arch_top(z)) for z in np.linspace(0.088, z_front - 0.004, 7)]
        # Superior temporal line: from behind the orbit's lateral rim, arching about two thirds of the way up the side
        # of the skull, down to the supramastoid crest above and behind the ear.
        line = [(z_front, 1.55), (z_front - 0.016, 1.574), (0.105, 1.589), (0.08, 1.593), (0.06, 1.586),
                (0.045, 1.569), (0.04, 1.549), (0.05, 1.533), (0.065, 1.527)]
        border = [(z_front, tops[-1][1] + 0.004)] + line + [(0.075, tops[0][1] + 0.004)] + tops
        poly = _chaikin(np.array(border), 3)
        low = np.interp(zs, [b[0] for b in tops], [b[1] for b in tops])
        crown = sorted([b for b in line if b[1] > 1.56] + [(0.035, 1.55), (z_front, 1.55)])
        high = np.interp(zs, [b[0] for b in crown], [b[1] for b in crown])
        hold = np.array([coronoid[2], float(np.interp(coronoid[2], zs, low)) + 0.005])

        def t_thick(pz: np.ndarray, py: np.ndarray, psd: np.ndarray) -> np.ndarray:
            span = np.maximum(np.interp(pz, zs, high) - np.interp(pz, zs, low), 0.01)
            v = np.clip((py - np.interp(pz, zs, low)) / span, 0, 1)
            return (0.0015 + 0.0075 * (1 - v) ** 1.4) * (0.15 + 0.85 * _smoothstep(0.0, 0.007, psd))

        def t_place(pz: np.ndarray, py: np.ndarray, psd: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            inner = at(base, pz, py)
            outer = inner + t_thick(pz, py, psd)
            return (np.column_stack([side * outer, py, pz]), np.column_stack([side * inner, py, pz]))

        mesh = _param_sheet(np.arange(0.02, 0.16, 0.0011), np.arange(1.49, 1.61, 0.0011), poly, t_place)
        _orient_out(mesh)
        p = mesh.vertices
        fib = _converge(mesh, coronoid.astype(np.float64))
        tendon = 1.0 - _smoothstep(0.012, 0.03, np.hypot(p[:, 2] - hold[0], p[:, 1] - hold[1]))
        out.append((f"{word} temporalis", mesh, fib, tendon))
        print(f"  {word} temporalis: {len(mesh.faces)} triangles")
    return out


def main(data_dir: Path, out_path: Path) -> None:
    isa, isa_names = read_table(data_dir / "isa_element_parts.txt")
    partof, partof_names = read_table(data_dir / "partof_element_parts.txt")
    names = {**partof_names, **isa_names}

    archive = zipfile.ZipFile(data_dir / "isa_BP3D_4.0_obj_99.zip")
    members = {Path(n).stem: n for n in archive.namelist() if n.lower().endswith(".obj")}
    print(f"archive: {len(members)} OBJ elements")

    cache: dict[str, trimesh.Trimesh] = {}
    loaded = 0

    def load(el: str) -> trimesh.Trimesh | None:
        nonlocal loaded
        if el in cache:
            return cache[el]
        member = members.get(el)
        if not member:
            return None
        v, f, name = parse_obj(archive.read(member).decode("utf-8", "replace"))
        if len(f) == 0:
            return None
        if name:
            names[el] = name
        cache[el] = trimesh.Trimesh(vertices=to_three(v), faces=f, process=False)
        loaded += 1
        if loaded % 100 == 0:
            print(f"  ... {loaded} meshes parsed", flush=True)
        return cache[el]

    groups: dict[str, tuple[str, list[trimesh.Trimesh]]] = {}
    claimed: set[str] = set()  # elements of the specific parts, kept out of the skeleton
    muscle_items: list[tuple[str, str, trimesh.Trimesh]] = []
    for key, system, concepts in PARTS:
        if key == "vestibular":
            groups[key] = (system, [labyrinth(-1), labyrinth(1)])
            continue
        if key in MODELLED:
            groups[key] = (system, [])  # built once its landmarks are loaded
            continue
        elements: set[str] = set()
        for c in concepts:
            found = isa.get(c, set()) | partof.get(c, set())
            if not found:
                print(f"  ! {key}: no elements for concept {c!r}")
            elements |= found
        if not elements:
            print(f"  ! no elements for {key}: {concepts}")
            continue
        if key == "skeleton":
            buckets: dict[str, list[trimesh.Trimesh]] = defaultdict(list)
            skipped = 0
            for el in sorted(elements):
                if el in claimed:
                    skipped += 1
                    continue
                m = load(el)
                if m is None:
                    continue
                nm = names.get(el, "")
                if SKULL.search(nm):
                    buckets["skull"].append(m)
                elif THORAX.search(nm):
                    buckets["thorax"].append(m)
                elif SPINE.search(nm):
                    buckets["spine"].append(m)
                elif HIPS.search(nm):
                    buckets["hips"].append(m)
                elif FEMUR.search(nm):
                    lo, hi = m.vertices[:, 1].min(), m.vertices[:, 1].max()
                    top, rest = cut_capped(m, hi - FEMUR_HIP_FRACTION * (hi - lo))
                    buckets["hips"].append(top)
                    buckets["bones"].append(rest)
                else:
                    buckets["bones"].append(m)
            if skipped:
                print(f"  skeleton: {skipped} elements belong to other parts (eyes, nerves) and were left out")
            for b, ms in buckets.items():
                groups[f"skeleton_{b}"] = (system, ms)
            continue
        if key == "muscles":
            elements -= claimed  # the diaphragm and the heart's papillary muscles belong to their organs
        claimed |= elements
        items = [(el, names.get(el, ""), m) for el in sorted(elements) if (m := load(el)) is not None]
        missing = len(elements) - len(items)
        if key == "muscles":
            skipped = [nm for _, nm, _ in items if MUSCLE_SKIP.search(nm)]
            items = [x for x in items if not MUSCLE_SKIP.search(x[1])]
            print(f"  muscles: {len(skipped)} elements left out (throat, mouth, pelvic floor, platysma, inner chest wall)")
        if key in DEDUPE:
            items = dedupe(items)
        if key == "muscles":
            muscle_items = items
            groups[key] = (system, [])  # prepared once the skeleton is loaded (it shades them)
            continue
        meshes = [m for _, _, m in items]
        if key in LOBES:
            meshes = tint_lobes(items, [isa.get(c, set()) | partof.get(c, set()) for c in LOBES[key]], key)
        groups[key] = (system, meshes)
        if missing:
            print(f"  ! {key}: {missing} of {len(elements)} elements missing in archive")

    named = {names.get(el, "").lower(): m for el, m in cache.items()}
    for key, make in MODELLED.items():
        groups[key] = (groups[key][0], [make(named)])

    bones = [m for k, (_, ms) in groups.items() if k.startswith("skeleton_") for m in ms]
    # The muscles BodyParts3D lacks: the latissimus over the trunk's own muscles and bones, under the trapezius.
    back = [m for _, nm, m in muscle_items if "trapezius" not in nm.lower()
            and abs(m.vertices[:, 0].mean()) < 0.17 and 0.84 < m.vertices[:, 1].mean() < 1.36]
    back += [m for k, m in named.items() if BACK_BONES.search(k)]
    trapezius = [m for _, nm, m in muscle_items if "trapezius" in nm.lower()]
    modelled = latissimus(named, back, trapezius) + jaw_muscles(named)
    print(f"  preparing {len(muscle_items)} muscle elements and {len(modelled)} modelled ones (fibres, tendons, "
          "occlusion)", flush=True)
    muscles = prepare_muscles(muscle_items, bones, modelled)
    groups["muscles"] = (groups["muscles"][0], [m for _, m in muscles])

    # Centre the whole body on the origin, feet on y = 0.
    all_v = np.vstack([m.vertices for _, ms in groups.values() for m in ms])
    lo, hi = all_v.min(axis=0), all_v.max(axis=0)
    shift = np.array([-(lo[0] + hi[0]) / 2, -lo[1], -(lo[2] + hi[2]) / 2])
    print(f"body size (m): {np.round(hi - lo, 3)}")
    # The muscles go out as one node per region (see muscle_regions), in place of the single "muscles" entry.
    system = groups.pop("muscles")[0]
    for region, ms in muscle_regions(muscles, shift).items():
        groups[region] = (system, ms)

    scene = trimesh.Scene()
    total = 0
    for key, (system, ms) in groups.items():
        mesh = trimesh.util.concatenate(ms)
        mesh.apply_translation(shift)
        name = f"{system}--{key}"
        scene.add_geometry(mesh, node_name=name, geom_name=name)
        total += len(mesh.faces)
        print(f"  {name:32s} {len(ms):4d} elements {len(mesh.faces):8d} triangles", flush=True)
    print(f"total triangles: {total}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(scene.export(file_type="glb", include_normals=True))
    print(f"wrote {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
