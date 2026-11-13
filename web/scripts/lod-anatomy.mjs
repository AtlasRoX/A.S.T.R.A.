// Per-part simplification for the anatomy model, tuned for integrated GPUs.
// Usage: node scripts/lod-anatomy.mjs <in.glb> <out.glb>
// Each node is "<system>--<part>". Every part but the muscles is first simplified within 0.08% of its size (the
// optimiser's pass), then to its own budget: an error (fraction of the part's own size) and a ratio, with a triangle
// floor, so small or hidden parts lose detail and the skin keeps its silhouette. The muscles go straight from the
// build's full detail to a triangle count per region, simplified with their baked vertex colour (tendon, occlusion)
// and normals as attributes, so tendon edges and the grooves between muscles keep their vertices.
import { createRequire } from 'node:module';
import { join } from 'node:path';

const pnpm = join(process.cwd(), 'node_modules', '.pnpm');
const req = createRequire(join(pnpm, '@gltf-transform+functions@4.5.1_@types+node@22.20.5', 'node_modules', '@gltf-transform', 'functions', 'package.json'));
const { NodeIO } = req('@gltf-transform/core');
const { ALL_EXTENSIONS } = req('@gltf-transform/extensions');
const { simplifyPrimitive, compactPrimitive, dequantizePrimitive, weld, meshopt, prune, dedup } =
  req('@gltf-transform/functions');
const { MeshoptSimplifier, MeshoptEncoder, MeshoptDecoder } = req('meshoptimizer');

const [input, output] = process.argv.slice(2);

// ratio = target fraction of triangles, error = max deviation relative to the part's size. Organs keep most of
// their detail (smooth, with every lobe and segment); the skeleton, muscles and vessels are seen from further away.
const KEEP = { ratio: 1, error: 0 }; // small organs: every triangle (the coarse ones are subdivided in the viewer)
const BUDGET = {
  skin: KEEP, // full detail: the skin is the hero surface
  brain: { ratio: 0.5, error: 0.0016 },
  vestibular: { ratio: 0.5, error: 0.004 }, // the inner ear's thin canals; subdivided again in the viewer
  eye_r: { ratio: 0.08, error: 0.01 },
  eye_l: { ratio: 0.05, error: 0.01 },
  optic_nerve: KEEP,
  heart: { ratio: 0.6, error: 0.0012 },
  vessels: KEEP,
  // Long thin tubes: a tight error keeps them round, the ratio removes the dense rings along them.
  arteries: { ratio: 0.3, error: 0.0008 },
  veins: { ratio: 0.25, error: 0.0008 },
  lung_r: { ratio: 0.4, error: 0.003 }, // bronchial trees: only seed the rebuilt lung surfaces
  lung_l: { ratio: 0.4, error: 0.003 },
  airway: { ratio: 0.7, error: 0.002 },
  larynx: KEEP,
  diaphragm: { ratio: 0.15, error: 0.002 },
  liver: { ratio: 0.6, error: 0.0012 },
  gallbladder: KEEP,
  esophagus: KEEP,
  stomach: KEEP,
  pancreas: { ratio: 0.7, error: 0.0015 },
  small_intestine: { ratio: 0.8, error: 0.0012 },
  large_intestine: { ratio: 0.7, error: 0.0012 },
  thyroid: KEEP,
  kidney_r: KEEP,
  kidney_l: KEEP,
  adrenals: { ratio: 0.7, error: 0.002 },
  ureters: { ratio: 0.8, error: 0.002 },
  bladder: KEEP,
  spleen: KEEP,
  thymus: KEEP,
  lymph_nodes: KEEP,
  skeleton_skull: { ratio: 0.3, error: 0.004 },
  // Spine and hips were split out of skeleton_bones and keep about its absolute error (the error is relative to the
  // part's size, and they are smaller).
  skeleton_bones: { ratio: 0.6, error: 0.002 },
  skeleton_spine: { ratio: 0.5, error: 0.004 },
  skeleton_hips: { ratio: 0.6, error: 0.006 },
  skeleton_thorax: { ratio: 0.5, error: 0.003 },
};
const DEFAULT = { ratio: 0.5, error: 0.004 };
const FLOOR = 400; // never go below this many triangles
/** The optimiser's own pass, which `anatomy:optimize` leaves to this script (the muscles skip it). */
const FIRST_PASS = { ratio: 0, error: 0.0008 };
/**
 * The muscles, the hero surface of the Muscles view: triangles per region (about 270k in all). Simplification puts
 * them where the shape, the shading and the baked tendons and occlusion change most.
 */
const MUSCLES = {
  muscles_head: 28000,
  muscles_trunk: 108000,
  muscles_arm_r: 26000,
  muscles_arm_l: 26000,
  muscles_leg_r: 42000,
  muscles_leg_l: 42000,
};
/** Weights of the attributes in the muscles' simplification: normal (x, y, z), tendon, occlusion. */
const MUSCLE_WEIGHTS = [0.35, 0.35, 0.35, 0.6, 0.4];

/** Simplifies a muscle region to `target` triangles, normals and baked colour as attributes. */
function simplifyMuscles(prim, target) {
  dequantizePrimitive(prim);
  const pos = prim.getAttribute('POSITION').getArray();
  const nrm = prim.getAttribute('NORMAL')?.getArray();
  const col = prim.getAttribute('COLOR_0');
  const count = pos.length / 3;
  const attrs = new Float32Array(count * 5);
  const c = col?.getArray();
  const cs = col?.getElementSize() ?? 4;
  for (let i = 0; i < count; i++) {
    attrs.set(nrm ? nrm.subarray(i * 3, i * 3 + 3) : [0, 0, 0], i * 5);
    attrs[i * 5 + 3] = c ? c[i * cs] : 0;
    attrs[i * 5 + 4] = c ? c[i * cs + 1] : 0;
  }
  const indices = Uint32Array.from(prim.getIndices().getArray());
  const [dst] = MeshoptSimplifier.simplifyWithAttributes(indices, pos, 3, attrs, 5, MUSCLE_WEIGHTS, null,
    Math.min(indices.length, target * 3), 0.05);
  prim.setIndices(prim.getIndices().clone().setArray(dst));
  compactPrimitive(prim);
}

await MeshoptDecoder.ready;
await MeshoptEncoder.ready;
await MeshoptSimplifier.ready;

const io = new NodeIO()
  .registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({ 'meshopt.decoder': MeshoptDecoder, 'meshopt.encoder': MeshoptEncoder });
const doc = await io.read(input);
await doc.transform(weld());

let before = 0;
let after = 0;
for (const mesh of doc.getRoot().listMeshes()) {
  const part = (mesh.getName() || '').split('--')[1] ?? '';
  const { ratio, error } = BUDGET[part] ?? DEFAULT;
  for (const prim of mesh.listPrimitives()) {
    const tris = (prim.getIndices()?.getCount() ?? 0) / 3;
    before += tris;
    if (MUSCLES[part]) {
      simplifyMuscles(prim, MUSCLES[part]);
    } else {
      simplifyPrimitive(prim, { simplifier: MeshoptSimplifier, ...FIRST_PASS, lockBorder: false });
      const mid = (prim.getIndices()?.getCount() ?? 0) / 3;
      const r = Math.max(ratio, Math.min(1, FLOOR / Math.max(1, mid)));
      simplifyPrimitive(prim, { simplifier: MeshoptSimplifier, ratio: r, error, lockBorder: false });
    }
    const now = (prim.getIndices()?.getCount() ?? 0) / 3;
    after += now;
    console.log(`${mesh.getName().padEnd(30)} ${String(tris).padStart(7)} -> ${String(now).padStart(7)}`);
  }
}
console.log(`total ${before} -> ${after} triangles`);

await doc.transform(dedup(), prune(), meshopt({ encoder: MeshoptEncoder, level: 'medium' }));
await io.write(output, doc);
