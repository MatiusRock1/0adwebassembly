// Automatic graphics profile for weak GPUs. The launcher writes the low profile
// to config/local.cfg (the engine's SYSTEM namespace): it replaces default.cfg,
// while settings saved from the in-game options (user.cfg) still take precedence.

export const GRAPHICS_MODES = ['auto', 'low', 'original'];

// The lowest option of every quality setting in the in-game options, except
// those that change what the player sees of the game itself (silhouettes,
// particles, fog) and the water shader (its "off" mode is the fixed pipeline).
export const LOW_GRAPHICS_SETTINGS = Object.freeze({
  'textures.quality': 0,
  'textures.maxanisotropy': 1,
  shadowquality: -1,
  shadowpcf: false,
  waterfancyeffects: false,
  waterrealdepth: false,
  waterrefraction: false,
  waterreflection: false,
  postproc: false,
  antialiasing: 'disabled',
  sharpening: 'disabled',
  smoothlos: false,
  max_actor_quality: 100,
  'materialmgr.quality': 0
});

// Matched against the WEBGL_debug_renderer_info string, e.g.
// "ANGLE (AMD, AMD Radeon(TM) Graphics (0x00001638) Direct3D11 vs_5_0 ps_5_0, D3D11)".
const SOFTWARE = /SwiftShader|llvmpipe|softpipe|lavapipe|Basic Render|\bWARP\b|GDI Generic|Software Rasterizer/i;
const ENTRY_LEVEL = [
  /GeForce\s+(MX|GT)\s*\d/i, // GeForce MX110–MX570, GT 610–1030
  /GeForce\s+\d/i, // names before GTX/RTX: GeForce 940MX, 920M, 8800 GT
  /GeForce\s+GTX\s+([4-8]\d\d|9[0-6]\d)M?\b/i, // GTX 400–960
  /GeForce\s+GTX\s+10[1-5]0\b/i, // GTX 1050 and 1050 Ti
  /RTX\s+(2050|A500)\b/i,
  /NVIDIA\s+T(400|500|550)\b/i,
  /Quadro\s+(NVS|[KMP]\d{3}\b)/i, // Quadro NVS, K620, P620
  /Radeon\s+(R\d\s+M\d|HD\s+\d)/i, // Radeon R7 M260, HD 7770
  /Radeon\s*(\(TM\))?\s*(5[2-5]0|6[1-3]0|625)X?\b/i, // mobile Radeon 520–630
  /Radeon\s*(\(TM\))?\s*RX\s+(5[3-6]0|640|6300)X?\b/i,
  /Radeon\s+Pro\s+WX\s*[2-4]\d{3}|FirePro/i,
  /Arc\(TM\)\s*(Pro\s*)?A3\d\d/i // Intel Arc A310–A380
];
const INTEGRATED = [
  /Radeon\s*(\(TM\))?\s*(RX\s+)?(Vega\s+\d+\s+|R\d\s+)?Graphics/i, // AMD APUs
  /Radeon\s*(\(TM\))?\s*\d{3}M\b/i, // Radeon 610M–890M
  /Adreno|Mali|PowerVR|Immortalis|VideoCore/i,
  /Apple\s+M\d+(?!\s+(Pro|Max|Ultra))/i
];
// Every Intel GPU is integrated except the Arc A5xx/B5xx cards and above.
const INTEL = /Intel/i;
const INTEL_DISCRETE = /Arc\(TM\)\s*(Pro\s*)?[AB][5-9]\d/i;
const KNOWN_VENDOR = /NVIDIA|GeForce|Quadro|\bRTX\b|AMD|\bATI\b|Radeon|Intel|Apple|Qualcomm|Adreno|\bARM\b|Mali|PowerVR|Microsoft|Google|Mesa/i;

const WEAK = new Set(['software', 'integrated', 'entry']);

function classifyRenderer(renderer) {
  if (SOFTWARE.test(renderer)) return 'software';
  if (ENTRY_LEVEL.some(pattern => pattern.test(renderer))) return 'entry';
  if (INTEGRATED.some(pattern => pattern.test(renderer))) return 'integrated';
  if (INTEL.test(renderer) && !INTEL_DISCRETE.test(renderer)) return 'integrated';
  return KNOWN_VENDOR.test(renderer) ? 'capable' : 'unknown';
}

// WebGPU only reports vendor and architecture; most architectures are shared
// by integrated and discrete GPUs.
function classifyAdapter(adapter, fallbackAdapter) {
  if (fallbackAdapter || adapter?.isFallbackAdapter || /swiftshader/i.test(adapter?.architecture ?? ''))
    return 'software';
  if (adapter?.vendor === 'intel' && /^gen-/.test(adapter.architecture ?? '')) return 'integrated';
  return 'unknown';
}

export function gpuDisplayName(renderer) {
  const angle = /^ANGLE \([^,]*, (.*)\)$/.exec(renderer ?? '');
  return (angle ? angle[1] : renderer ?? '')
    .replace(/, (D3D|OpenGL|Vulkan|Metal|Unspecified).*$/, '')
    .replace(/\s*\(0x[0-9a-f]+\)/i, '')
    .replace(/\s+Direct3D.*$/, '')
    .replace(/^ANGLE Metal Renderer:\s*/, '')
    .trim() || null;
}

// renderer: the unmasked WebGL renderer string, or null. adapter: the WebGPU
// adapter info when the game runs on WebGPU; the WebGL name is then used only
// if it names the same vendor, i.e. most likely the same GPU.
export function classifyGPU({ renderer = null, adapter = null, fallbackAdapter = false } = {}) {
  const vendor = adapter?.vendor ?? '';
  const named = renderer && (!adapter || !vendor || renderer.toLowerCase().includes(vendor.toLowerCase()));
  let category = named ? classifyRenderer(renderer) : 'unknown';
  if (adapter && category !== 'software') {
    const fromAdapter = classifyAdapter(adapter, fallbackAdapter);
    if (fromAdapter === 'software' || category === 'unknown') category = fromAdapter;
  }
  const name = (named && gpuDisplayName(renderer)) ||
    [adapter?.vendor, adapter?.architecture].filter(Boolean).join(' ') || null;
  return { category, weak: WEAK.has(category), name, renderer: named ? renderer : null,
    source: named ? 'webgl-renderer' : adapter ? 'webgpu-adapter' : 'none' };
}

// windows, macos, linux, or other (mobile, ChromeOS, unknown): which steps the
// GPU guide opens first.
export function detectOS(environment = globalThis) {
  const navigator = environment.navigator;
  const platform = [navigator?.userAgentData?.platform, navigator?.platform, navigator?.userAgent].join(' ');
  if (/Android|CrOS|Chrome OS|iPhone|iPad/i.test(platform)) return 'other';
  if (/\bWin/i.test(platform)) return 'windows';
  if (/\bMac/i.test(platform)) return 'macos';
  return /Linux/i.test(platform) ? 'linux' : 'other';
}

// Chrome gives every page the GPU its GPU process started on and, on Windows
// and Linux, ignores powerPreference: a laptop with two GPUs runs the game on
// the integrated one until the operating system (or a browser flag) assigns
// the dedicated one. 'dedicated': how to do that; 'acceleration': the browser
// renders in software; null: nothing to suggest.
const SINGLE_GPU_DEVICE = /Apple|Adreno|Mali|PowerVR|Immortalis|VideoCore/i;
export function gpuGuide(gpu, os) {
  if (gpu?.category === 'software') return 'acceleration';
  if (gpu?.category !== 'integrated' || os === 'other' || SINGLE_GPU_DEVICE.test(gpu.renderer ?? '')) return null;
  return 'dedicated';
}

export function selectGraphicsProfile(mode, gpu) {
  if (mode === 'low' || mode === 'original') return mode;
  return gpu?.weak ? 'low' : 'original';
}

export function graphicsConfig(settings) {
  return ['; Written by the web launcher: low graphics profile for a weak GPU.',
    '; Settings saved from the in-game options (user.cfg) take precedence.',
    ...Object.entries(settings).map(([key, value]) =>
      `${key} = ${typeof value === 'string' ? JSON.stringify(value) : value}`), ''].join('\n');
}

// The unmasked renderer of a short-lived WebGL 2 context. Chrome runs WebGL
// and WebGPU on the same adapter; classifyGPU still checks the vendor.
export function readWebGLRenderer(powerPreference = 'default', environment = globalThis) {
  const canvas = environment.document?.createElement('canvas');
  const gl = canvas?.getContext('webgl2', { powerPreference });
  if (!gl) return null;
  try {
    const debug = gl.getExtension('WEBGL_debug_renderer_info');
    return debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : null;
  } finally {
    gl.getExtension('WEBGL_lose_context')?.loseContext();
  }
}
