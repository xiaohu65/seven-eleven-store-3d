import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { SMAAPass } from 'three/addons/postprocessing/SMAAPass.js';
import glbUrl from '../../seven_eleven_store.glb';

/* --------------------------------------------------------------------------
   A small, deterministic 3D film set: one convenience store, three weathers.
   Blender Z-up becomes glTF Y-up, so the shopfront sits at positive Z.
   -------------------------------------------------------------------------- */

const TAU = Math.PI * 2;
const IS_TOUCH = matchMedia('(pointer: coarse)').matches;
const IS_SMALL = innerWidth < 800;
const REDUCED_MOTION = matchMedia('(prefers-reduced-motion: reduce)').matches;
const QUERY = new URLSearchParams(location.search);
const CAPTURE = QUERY.has('capture');
const UI_HIDDEN = QUERY.get('ui') === '0';
const FORCE_MODE = ['day', 'night'].includes(QUERY.get('mode')) ? QUERY.get('mode') : null;
const SKIP_INTRO = QUERY.get('intro') === '0' || CAPTURE;
const AUTO_PARAM = QUERY.get('auto');
const DPR_OVERRIDE = Number(QUERY.get('dpr')) || null;
const BASE_DPR = Math.min(devicePixelRatio || 1, DPR_OVERRIDE || (IS_TOUCH ? 1.5 : 2));
const QUALITY = IS_TOUCH || (navigator.hardwareConcurrency || 8) <= 5 ? 'low' : 'high';

const state = {
  ready: false,
  mode: FORCE_MODE || 'night',
  modeLabelPending: null,
  autoRotate: AUTO_PARAM === '1' ? true : AUTO_PARAM === '0' ? false : !REDUCED_MOTION,
  intro: !SKIP_INTRO && !REDUCED_MOTION,
  introStart: 0,
  introDuration: 2500,
  tween: null,
  modalOpen: false,
  dragging: false,
  hasInteracted: false,
  frame: 0,
  captureReady: false,
  clockText: '--:--',
  inside: false,
  entering: false,
  exiting: false,
  streetView: null,
  doorForceOpen: false,
  doorOpen: 0,
  doorCloseAt: 0,
  look: { yaw: 0, pitch: 0, dragging: false, lastX: 0, lastY: 0 },
  tour: null,
  time: 1,
  hour: 12,
  photoMode: false,
  coffeeOpen: false,
  shopOpen: false,
  walking: false,
  insideStop: 'entrance',
};

const MODE_INDEX = { day: '01', night: '02' };
const MODE_COPY = {
  day: {
    kicker: 'FIRST LIGHT / STREET AWAKENS',
    title: '城市刚刚醒来',
    copy: '清晨的光把玻璃照得发白，货架已经排好第一排饮料；城市还没完全醒，店里先亮了起来。',
    toast: 'DAYLIGHT',
  },
  night: {
    kicker: 'MIDNIGHT / ALWAYS OPEN',
    title: '总有一盏灯亮着',
    copy: '凌晨的街道安静下来，冰柜的低鸣和店招的暖光，替街角守着最后一格清醒。',
    toast: 'NIGHT',
  },
  dusk: {
    kicker: 'BLUE HOUR / LIGHTS COMING ON',
    title: '天色正在暗下来',
    copy: '路灯先醒，店招跟上；白昼退到街角后面，玻璃开始映出室内的暖光。',
    toast: 'DUSK',
  },
  dawn: {
    kicker: 'FIRST LIGHT / STREET WAKING',
    title: '天快亮了',
    copy: '街道还留着夜里的安静，店招和路灯慢慢退到晨光后面。',
    toast: 'DAWN',
  },
};

// Parameters are deliberately authored rather than physically constrained.
// They are blended continuously when the mode changes.
const MODE_PARAMS = {
  day: {
    skyTop: '#578bb9', skyHorizon: '#ead9c1', skyGround: '#8e9a9b',
    sunColor: '#ffeccd', sunDir: new THREE.Vector3(-0.72, 0.40, 0.20).normalize(),
    skyGlow: '#ffd7a3', glowStrength: 0.16,
    cloudColor: '#f3efe1', cloudiness: 0.23,
    fogColor: '#b6c7cb', fogNear: 45, fogFar: 165,
    hemiSky: '#c9e2f2', hemiGround: '#626354', hemiI: 0.38,
    ambientColor: '#c9d8e2', ambientI: 0.08,
    sunI: 3.8,
    exposure: 0.97, bloom: 0.05, bloomThreshold: 1.30,
    sign: 0.16, led: 0.28, fridge: 0.26, warm: 0.14, street: 0.0,
    neon: 0.15, screen: 0.45, decal: 0.70,
    star: 0.0, moon: 0.0, spill: 0.10, glassReflect: 0.26,
    interior: 0.36, streetLight: 0.0, canopy: 0.12, pylonLight: 0.18,
  },
  night: {
    skyTop: '#02070f', skyHorizon: '#172431', skyGround: '#05080b',
    sunColor: '#abc9e8', sunDir: new THREE.Vector3(-0.36, 0.45, 0.72).normalize(),
    sunI: 0.48, skyGlow: '#d5a06a', glowStrength: 0.22,
    cloudColor: '#26323a', cloudiness: 0.16,
    fogColor: '#0a141a', fogNear: 34, fogFar: 135,
    hemiSky: '#456883', hemiGround: '#080706', hemiI: 0.34,
    ambientColor: '#52697a', ambientI: 0.14,
    exposure: 0.85, bloom: 0.18, bloomThreshold: 1.18,
    sign: 0.58, led: 0.35, fridge: 0.42, warm: 0.58, street: 0.62,
    neon: 0.58, screen: 0.56, decal: 0.55,
    star: 0.72, moon: 0.8, spill: 0.26, glassReflect: 0.15,
    interior: 1.0, streetLight: 0.9, canopy: 0.66, pylonLight: 0.8,
  },
  dusk: {
    skyTop: '#263f55', skyHorizon: '#d9a173', skyGround: '#37342f',
    sunColor: '#ffcf9b', sunDir: new THREE.Vector3(-0.82, 0.16, 0.32).normalize(),
    sunI: 1.25, skyGlow: '#ff9d5f', glowStrength: 0.34,
    cloudColor: '#655f5e', cloudiness: 0.27,
    fogColor: '#4a555b', fogNear: 28, fogFar: 120,
    hemiSky: '#9a8c83', hemiGround: '#2c2823', hemiI: 0.31,
    ambientColor: '#5f646a', ambientI: 0.10,
    exposure: 0.91, bloom: 0.14, bloomThreshold: 1.22,
    sign: 0.36, led: 0.31, fridge: 0.34, warm: 0.30, street: 0.35,
    neon: 0.38, screen: 0.50, decal: 0.62,
    star: 0.06, moon: 0.12, spill: 0.20, glassReflect: 0.22,
    interior: 0.72, streetLight: 0.38, canopy: 0.38, pylonLight: 0.45,
  },
};

const TONE_BASE = {
  M_Sign_Fascia: 'sign', M_Sign_Pylon: 'sign', M_Neon_Open: 'neon',
  M_Interior_LED: 'led', M_Fridge_Glow: 'fridge', M_Fridge_Header: 'fridge',
  M_Warm_Glow: 'warm', M_Streetlight_Glow: 'street', M_Screen_Glow: 'screen',
  M_Decal_Door: 'decal', M_Glass_Store: null,
};
const EMISSIVE_MATERIALS = [];
const LIGHT_POOL_MATS = [];
const STARS = { points: null, mat: null };

// ---------------------------------------------------------------------------
// Tiny helpers
// ---------------------------------------------------------------------------
function mulberry32(seed) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const lerp = (a, b, t) => a + (b - a) * t;
const smooth = (t) => t * t * (3 - 2 * t);
const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);
const easeInOutCubic = (t) => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
function damp(current, target, lambda, dt) {
  return lerp(current, target, 1 - Math.exp(-lambda * dt));
}
function color(hex) { return new THREE.Color(hex); }

function makeCanvasTexture(w, h, draw, { srgb = true, repeat = null } = {}) {
  const canvas = document.createElement('canvas');
  canvas.width = w; canvas.height = h;
  const ctx = canvas.getContext('2d');
  draw(ctx, w, h);
  const tex = new THREE.CanvasTexture(canvas);
  if (srgb) tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  if (repeat) {
    tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
    tex.repeat.set(repeat[0], repeat[1]);
  }
  return tex;
}

function makeRadialTexture(size = 256, stops = [[0, 'rgba(255,255,255,1)'], [0.3, 'rgba(255,255,255,.55)'], [1, 'rgba(255,255,255,0)']]) {
  return makeCanvasTexture(size, size, (ctx, w, h) => {
    const g = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w / 2);
    for (const [p, c] of stops) g.addColorStop(p, c);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
  });
}

function makeGlowSprite(size, inner, outer) {
  return makeCanvasTexture(size, size, (ctx, w, h) => {
    const g = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w / 2);
    g.addColorStop(0, inner);
    g.addColorStop(0.12, inner);
    g.addColorStop(0.4, outer);
    g.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
  });
}

function makeEnvTexture(p) {
  return makeCanvasTexture(1024, 512, (ctx, w, h) => {
    const g = ctx.createLinearGradient(0, 0, 0, h);
    g.addColorStop(0, p.skyTop);
    g.addColorStop(0.46, p.skyHorizon);
    g.addColorStop(0.53, p.skyHorizon);
    g.addColorStop(1, p.skyGround);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
    // Warm horizon haze and a few very distant lights.
    const hg = ctx.createLinearGradient(0, h * 0.38, 0, h * 0.6);
    hg.addColorStop(0, 'rgba(255,255,255,0)');
    hg.addColorStop(0.52, p.skyGlow + '33');
    hg.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = hg;
    ctx.fillRect(0, h * 0.36, w, h * 0.26);
    const rng = mulberry32(p === MODE_PARAMS.day ? 42 : 12);
    for (let i = 0; i < 130; i++) {
      const x = rng() * w;
      const y = h * (0.47 + rng() * 0.08);
      const s = 1 + rng() * 2.4;
      ctx.fillStyle = `rgba(255,${170 + rng() * 60},${90 + rng() * 60},${0.1 + rng() * 0.25})`;
      ctx.fillRect(x, y, s, s);
    }
    // A faint cool studio light high in the sky helps glossy materials read.
    const gl = ctx.createRadialGradient(w * 0.72, h * 0.2, 0, w * 0.72, h * 0.2, w * 0.2);
    gl.addColorStop(0, p === MODE_PARAMS.day ? 'rgba(255,246,219,.35)' : 'rgba(155,188,218,.09)');
    gl.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = gl;
    ctx.fillRect(0, 0, w, h);
  }, { srgb: true });
}

function updateClock() {
  const el = document.getElementById('clock');
  if (!el) return;
  try {
    const text = new Intl.DateTimeFormat('zh-TW', {
      hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Taipei',
    }).format(new Date());
    el.textContent = text;
    state.clockText = text;
  } catch (_) {
    el.textContent = '--:--';
  }
}

// ---------------------------------------------------------------------------
// Renderer / scene / camera
// ---------------------------------------------------------------------------
const canvas = document.getElementById('scene');
let renderer;
try {
  renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: false,
    stencil: false,
    preserveDrawingBuffer: true,
    powerPreference: 'high-performance',
  });
} catch (err) {
  document.getElementById('fallback').hidden = false;
  throw err;
}
renderer.setPixelRatio(BASE_DPR);
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = MODE_PARAMS.night.exposure;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.info.autoReset = true;

const scene = new THREE.Scene();
scene.background = new THREE.Color('#020508');
scene.fog = new THREE.Fog(MODE_PARAMS.night.fogColor, MODE_PARAMS.night.fogNear, MODE_PARAMS.night.fogFar);

const DEFAULT_VIEW = {
  desktop: {
    pos: new THREE.Vector3(-11.60, 5.72, 19.15),
    target: new THREE.Vector3(2.55, 1.98, 0.38),
    fov: 39.5,
  },
  medium: {
    pos: new THREE.Vector3(-12.6, 6.2, 20.7),
    target: new THREE.Vector3(2.3, 2.2, 0.25),
    fov: 40,
  },
  portrait: {
    pos: new THREE.Vector3(-17.0, 8.5, 34.0),
    target: new THREE.Vector3(2.2, 2.00, 0.2),
    fov: 48,
  },
};
function getViewKey() {
  const aspect = innerWidth / innerHeight;
  if (aspect < 0.95) return 'portrait';
  if (aspect < 1.5) return 'medium';
  return 'desktop';
}
function getView() { return DEFAULT_VIEW[getViewKey()]; }
const initialViewKey = getViewKey();
const camera = new THREE.PerspectiveCamera(DEFAULT_VIEW[initialViewKey].fov, innerWidth / innerHeight, 0.08, 350);
const startView = getView();
camera.fov = startView.fov;
camera.position.copy(startView.pos);
camera.updateProjectionMatrix();

const orbit = new OrbitControls(camera, canvas);
orbit.target.copy(startView.target);
orbit.enableDamping = true;
orbit.dampingFactor = 0.055;
orbit.enablePan = false;
orbit.minDistance = 6.2;
orbit.maxDistance = 50;
orbit.minPolarAngle = 0.22;
orbit.maxPolarAngle = 1.52;
orbit.autoRotate = false;
orbit.autoRotateSpeed = 0.24;
orbit.rotateSpeed = 0.64;
orbit.zoomSpeed = 0.8;
orbit.touches.ONE = THREE.TOUCH.ROTATE;
orbit.touches.TWO = THREE.TOUCH.DOLLY_ROTATE;
orbit.enabled = !state.intro;
orbit.update();

const doorLeaves = { left: null, right: null, leftX: 0, rightX: 0, open: 0 };
const DOOR_POINT = new THREE.Vector3(0.4, 1.6, 4.8);
const INTERIOR_POS = new THREE.Vector3(0.4, 1.68, 3.32);
const INTERIOR_TARGET = new THREE.Vector3(0.4, 1.55, -1.3);
const STAGING_POS = new THREE.Vector3(0.4, 2.02, 9.4);
const STAGING_TARGET = new THREE.Vector3(0.4, 1.9, 4.8);

const WALK_STOPS = {
  entrance: {
    label: '入口', en: 'ENTRANCE',
    pos: new THREE.Vector3(0.4, 1.68, 3.32),
    target: new THREE.Vector3(0.4, 1.55, -1.3),
    anchor: new THREE.Vector3(0.4, 2.05, 3.45),
    category: null,
  },
  drinks: {
    label: '冷藏饮料', en: 'COLD DRINKS',
    pos: new THREE.Vector3(-0.45, 1.68, -2.3),
    target: new THREE.Vector3(-2.0, 1.5, -4.02),
    anchor: new THREE.Vector3(-2.7, 2.15, -4.0),
    category: 'drinks',
  },
  snacks: {
    label: '零食', en: 'SNACKS',
    pos: new THREE.Vector3(0.65, 1.68, 1.15),
    target: new THREE.Vector3(-2.7, 1.35, -0.38),
    anchor: new THREE.Vector3(-2.7, 1.75, -0.38),
    category: 'snacks',
  },
  daily: {
    label: '日用品', en: 'DAILY GOODS',
    pos: new THREE.Vector3(0.9, 1.68, 3.0),
    target: new THREE.Vector3(-2.6, 1.35, 1.9),
    anchor: new THREE.Vector3(-2.6, 1.75, 1.9),
    category: 'daily',
  },
};
const sceneFade = document.getElementById('scene-fade');
const btnEnter = document.getElementById('btn-enter');
const hintEl = document.getElementById('hint');
const hintOriginal = hintEl ? hintEl.innerHTML : '';
const walkLayer = document.getElementById('walk-layer');
const walkMarkerEls = [...document.querySelectorAll('.walk-marker')];
const routeBtns = [...document.querySelectorAll('[data-route-stop]')];
const storeServices = document.getElementById('store-services');

const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloomPass = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.28, 0.58, 1.05);
composer.addPass(bloomPass);
const smaaPass = QUALITY === 'high' ? new SMAAPass() : null;
if (smaaPass) composer.addPass(smaaPass);
composer.addPass(new OutputPass());
composer.setSize(innerWidth, innerHeight);
composer.setPixelRatio(BASE_DPR);

// ---------------------------------------------------------------------------
// Lights
// ---------------------------------------------------------------------------
const hemi = new THREE.HemisphereLight('#456883', '#080706', 0.43);
scene.add(hemi);
const ambient = new THREE.AmbientLight('#52697a', 0.2);
scene.add(ambient);

const keyLight = new THREE.DirectionalLight('#abc9e8', 0.28);
keyLight.position.set(7, 16, 23);
keyLight.castShadow = true;
keyLight.shadow.mapSize.set(QUALITY === 'low' ? 1024 : 2048, QUALITY === 'low' ? 1024 : 2048);
keyLight.shadow.camera.left = -24;
keyLight.shadow.camera.right = 24;
keyLight.shadow.camera.top = 22;
keyLight.shadow.camera.bottom = -16;
keyLight.shadow.camera.near = 1;
keyLight.shadow.camera.far = 65;
keyLight.shadow.bias = -0.0003;
keyLight.shadow.normalBias = 0.035;
keyLight.shadow.radius = 1.5;
scene.add(keyLight);
scene.add(keyLight.target);
keyLight.target.position.set(1, 0.5, 0.5);

const interiorLights = [
  new THREE.PointLight('#ffe2b8', 17, 7.0, 1.9),
  new THREE.PointLight('#ffe3b8', 14, 6.8, 1.9),
  new THREE.PointLight('#ffdfb4', 17, 7.0, 1.9),
  new THREE.PointLight('#ffe0b2', 12, 6.2, 1.9),
];
interiorLights[0].position.set(-4.1, 3.15, 1.1);
interiorLights[1].position.set(-0.9, 3.15, -0.7);
interiorLights[2].position.set(3.7, 3.15, 1.2);
interiorLights[3].position.set(-2.7, 3.1, -3.1);
for (const l of interiorLights) scene.add(l);
const fridgeLight = new THREE.PointLight('#d5f3ff', 5.2, 3.8, 2);
fridgeLight.position.set(-2.7, 2.15, -3.25);
scene.add(fridgeLight);

const canopyLights = [];
[-1.0, 0.4, 1.8].forEach((x, index) => {
  const l = new THREE.SpotLight('#ffd7a1', 13, 6.5, 0.78, 0.86, 1.8);
  l.position.set(x, 3.35, 5.43);
  l.target.position.set(x, 0.12, 6.0);
  if (index === 1 && QUALITY === 'high') {
    l.castShadow = true;
    l.shadow.mapSize.set(1024, 1024);
    l.shadow.bias = -0.0015;
    l.shadow.normalBias = 0.02;
    l.shadow.camera.near = 0.3;
    l.shadow.camera.far = 8;
  }
  scene.add(l); scene.add(l.target);
  canopyLights.push(l);
});

const streetLamp = new THREE.SpotLight('#d5eaff', 150, 18, 0.78, 0.7, 1.8);
streetLamp.position.set(-9.35, 6.76, 12.3);
streetLamp.target.position.set(-9.35, 0.0, 13.2);
streetLamp.castShadow = QUALITY === 'high';
streetLamp.shadow.mapSize.set(1024, 1024);
streetLamp.shadow.bias = -0.001;
streetLamp.shadow.camera.near = 0.6;
streetLamp.shadow.camera.far = 25;
scene.add(streetLamp); scene.add(streetLamp.target);

const pylonLight = new THREE.PointLight('#ffecd0', 1.2, 5.0, 1.8);
pylonLight.position.set(8.55, 3.8, 9.35);
scene.add(pylonLight);

const spillLight = new THREE.PointLight('#ffc98d', 8.0, 9.0, 2.0);
spillLight.position.set(0.2, 2.35, 5.55);
scene.add(spillLight);

// A second, human-scale street lamp by the bench. It gives the left-hand
// pavement its own pool of light and a visible street object in the frame.
const pedLamp = new THREE.SpotLight('#ffd0a0', 72, 14, 0.95, 0.82, 1.7);
pedLamp.position.set(-6.8, 4.62, 7.9);
pedLamp.target.position.set(-6.8, 0.05, 8.7);
pedLamp.castShadow = QUALITY === 'high';
pedLamp.shadow.mapSize.set(1024, 1024);
pedLamp.shadow.bias = -0.0015;
pedLamp.shadow.normalBias = 0.03;
pedLamp.shadow.camera.near = 0.4;
pedLamp.shadow.camera.far = 13;
scene.add(pedLamp); scene.add(pedLamp.target);

// Dedicated downward spots reveal the stocked shelves and the two window
// counters without washing the whole interior out.
const displaySpots = [];
[
  [-4.2, 3.25, 3.15, 16],
  [3.3, 3.25, 3.35, 14],
  [4.45, 3.2, 1.75, 5],
].forEach(([x, y, z, power]) => {
  const l = new THREE.SpotLight('#fff0d6', power, 6.5, 0.9, 0.78, 1.65);
  l.position.set(x, y, z);
  l.target.position.set(x, 1.1, z + 0.35);
  l.userData.power = power;
  scene.add(l); scene.add(l.target);
  displaySpots.push(l);
});

// ---------------------------------------------------------------------------
// Sky dome, stars, moon
// ---------------------------------------------------------------------------
const skyUniforms = {
  topColor: { value: color(MODE_PARAMS.night.skyTop) },
  horizonColor: { value: color(MODE_PARAMS.night.skyHorizon) },
  groundColor: { value: color(MODE_PARAMS.night.skyGround) },
  glowColor: { value: color(MODE_PARAMS.night.skyGlow) },
  sunColor: { value: color(MODE_PARAMS.night.sunColor) },
  cloudColor: { value: color(MODE_PARAMS.night.cloudColor) },
  sunDir: { value: MODE_PARAMS.night.sunDir.clone() },
  sunI: { value: MODE_PARAMS.night.sunI },
  glowStrength: { value: MODE_PARAMS.night.glowStrength },
  cloudiness: { value: MODE_PARAMS.night.cloudiness },
  time: { value: 0 },
};
const skyMat = new THREE.ShaderMaterial({
  uniforms: skyUniforms,
  side: THREE.BackSide,
  depthWrite: false,
  fog: false,
  vertexShader: /* glsl */`
    varying vec3 vWorld;
    void main() {
      vec4 wp = modelMatrix * vec4(position, 1.0);
      vWorld = wp.xyz;
      gl_Position = projectionMatrix * viewMatrix * wp;
    }
  `,
  fragmentShader: /* glsl */`
    uniform vec3 topColor;
    uniform vec3 horizonColor;
    uniform vec3 groundColor;
    uniform vec3 glowColor;
    uniform vec3 sunColor;
    uniform vec3 cloudColor;
    uniform vec3 sunDir;
    uniform float sunI;
    uniform float glowStrength;
    uniform float cloudiness;
    uniform float time;
    varying vec3 vWorld;

    float hash(vec2 p) {
      p = fract(p * vec2(123.34, 456.21));
      p += dot(p, p + 45.32);
      return fract(p.x * p.y);
    }
    float noise(vec2 p) {
      vec2 i = floor(p);
      vec2 f = fract(p);
      f = f * f * (3.0 - 2.0 * f);
      return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
                 mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
    }
    float fbm(vec2 p) {
      float v = 0.0;
      float a = 0.5;
      mat2 rot = mat2(0.86, 0.51, -0.51, 0.86);
      for (int i = 0; i < 5; i++) {
        v += a * noise(p);
        p = rot * p * 2.03 + 7.1;
        a *= 0.5;
      }
      return v;
    }

    void main() {
      vec3 dir = normalize(vWorld);
      float h = clamp(dir.y, -0.08, 1.0);
      float high = pow(clamp(h, 0.0, 1.0), 0.48);
      vec3 col = mix(horizonColor, topColor, high);

      // Horizon glow and atmospheric veil.
      float band = exp(-pow((h - 0.02) / 0.14, 2.0));
      col += glowColor * band * glowStrength;
      float lowerHaze = smoothstep(0.0, -0.07, h);
      col = mix(col, groundColor, lowerHaze * 0.86);

      // Sun / moon halo. The disc is intentionally soft and cinematic.
      float sd = max(dot(dir, normalize(sunDir)), 0.0);
      col += sunColor * (pow(sd, 900.0) * 3.1 + pow(sd, 18.0) * 0.065) * sunI;

      // Clouds: mostly high-altitude layers with a quiet drift.
      if (h > 0.0) {
        vec2 cp = dir.xz / (h + 0.16);
        float n = fbm(cp * 1.15 + vec2(time * 0.003, time * 0.0012));
        n = smoothstep(0.43, 0.78, n);
        float lower = smoothstep(0.02, 0.24, h);
        float cloud = n * cloudiness * lower;
        col = mix(col, cloudColor, cloud * 0.56);
      }

      // A very subtle dither stops dark-sky banding on 8-bit displays.
      float dither = (hash(gl_FragCoord.xy) - 0.5) / 255.0;
      col += dither;
      gl_FragColor = vec4(max(col, 0.0), 1.0);
    }
  `,
});
const sky = new THREE.Mesh(new THREE.SphereGeometry(190, 32, 24), skyMat);
sky.frustumCulled = false;
sky.renderOrder = -100;
scene.add(sky);

// Stars are a separate point cloud for crisp, controllable twinkle.
function createStars() {
  const rng = mulberry32(7331);
  const count = QUALITY === 'low' ? 360 : 760;
  const positions = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const phases = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    const theta = rng() * TAU;
    const u = rng();
    const y = 0.08 + Math.pow(u, 0.85) * 0.9;
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    positions[i * 3] = Math.cos(theta) * r * 170;
    positions[i * 3 + 1] = y * 170;
    positions[i * 3 + 2] = Math.sin(theta) * r * 170;
    sizes[i] = (rng() < 0.06 ? 2.5 : 1.1) + rng() * 1.3;
    phases[i] = rng() * TAU;
  }
  const geom = new THREE.BufferGeometry();
  geom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geom.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));
  geom.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
  const mat = new THREE.ShaderMaterial({
    uniforms: { uOpacity: { value: 0.0 }, uTime: { value: 0 }, uPixelRatio: { value: BASE_DPR } },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexShader: /* glsl */`
      attribute float aSize;
      attribute float aPhase;
      uniform float uTime;
      uniform float uOpacity;
      uniform float uPixelRatio;
      varying float vAlpha;
      void main() {
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        gl_Position = projectionMatrix * mv;
        gl_PointSize = aSize * uPixelRatio * (0.82 + 0.18 * sin(uTime * 0.8 + aPhase));
        vAlpha = uOpacity * (0.55 + 0.45 * sin(uTime * 1.3 + aPhase));
      }
    `,
    fragmentShader: /* glsl */`
      varying float vAlpha;
      void main() {
        float d = length(gl_PointCoord - 0.5);
        float a = smoothstep(0.5, 0.06, d);
        if (a <= 0.001) discard;
        gl_FragColor = vec4(vec3(0.78, 0.87, 1.0), a * vAlpha);
      }
    `,
  });
  const points = new THREE.Points(geom, mat);
  points.frustumCulled = false;
  points.renderOrder = -90;
  scene.add(points);
  STARS.points = points;
  STARS.mat = mat;
}
createStars();

const moonTex = makeGlowSprite(256, 'rgba(248,244,226,.98)', 'rgba(197,218,245,.34)');
const moon = new THREE.Sprite(new THREE.SpriteMaterial({
  map: moonTex, color: '#e7eef8', transparent: true, opacity: 0.0,
  depthWrite: false, blending: THREE.AdditiveBlending, fog: false,
}));
moon.scale.set(13, 13, 1);
moon.position.set(-46, 82, -112);
moon.renderOrder = -80;
scene.add(moon);

// A broad, quiet ground plane beneath the exported street geometry.
const farGroundMat = new THREE.MeshStandardMaterial({ color: '#151a1b', roughness: 0.9, metalness: 0.0 });
const farGround = new THREE.Mesh(new THREE.PlaneGeometry(280, 280), farGroundMat);
farGround.rotation.x = -Math.PI / 2;
farGround.position.y = -0.025;
farGround.receiveShadow = true;
scene.add(farGround);

// Long road strips so the horizon does not end abruptly.
const stripMat = new THREE.MeshStandardMaterial({ color: '#202726', roughness: 0.82 });
for (let i = -4; i <= 4; i++) {
  const strip = new THREE.Mesh(new THREE.PlaneGeometry(10, 75), stripMat);
  strip.rotation.x = -Math.PI / 2;
  strip.position.set(i * 17, -0.018, 42);
  strip.receiveShadow = true;
  scene.add(strip);
}

// ---------------------------------------------------------------------------
// Ground light pools and contact shadows
// ---------------------------------------------------------------------------
const glowTexture = makeRadialTexture(256);
const warmPoolMat = new THREE.MeshBasicMaterial({
  map: glowTexture, color: '#ffb35e', transparent: true, opacity: 0.32,
  blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false,
});
const coolPoolMat = new THREE.MeshBasicMaterial({
  map: glowTexture, color: '#bcdfff', transparent: true, opacity: 0.26,
  blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false,
});
const pedPoolMat = new THREE.MeshBasicMaterial({
  map: glowTexture, color: '#ffd09a', transparent: true, opacity: 0.2,
  blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false,
});
LIGHT_POOL_MATS.push({ mat: warmPoolMat, kind: 'spill' }, { mat: coolPoolMat, kind: 'street' });

function addPool(mat, x, z, w, h, rot = 0, y = 0.166) {
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat);
  mesh.rotation.x = -Math.PI / 2;
  mesh.rotation.z = rot;
  mesh.position.set(x, y, z);
  mesh.renderOrder = 2;
  scene.add(mesh);
  return mesh;
}
// Broad storefront spill.
addPool(warmPoolMat, 0.2, 7.1, 16, 4.7);
addPool(warmPoolMat, 4.2, 6.25, 4.2, 3.2);
addPool(coolPoolMat, -9.35, 12.65, 8.2, 8.2, 0, 0.03);
addPool(coolPoolMat, 8.55, 8.1, 3.0, 2.2, 0, 0.168);
addPool(pedPoolMat, -6.8, 8.35, 4.8, 3.8, 0, 0.167);

// Soft contact shadows keep small street props grounded when the only strong
// light is the self-lit storefront.
const contactTexture = makeCanvasTexture(256, 256, (ctx, w, h) => {
  const g = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, w / 2);
  g.addColorStop(0, 'rgba(0,0,0,.66)');
  g.addColorStop(0.55, 'rgba(0,0,0,.25)');
  g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);
});
const contactMat = new THREE.MeshBasicMaterial({
  map: contactTexture, transparent: true, opacity: 0.42, depthWrite: false,
  color: '#000000', toneMapped: false,
});
function addContact(x, z, w, d, rot = 0, y = 0.171) {
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, d), contactMat);
  m.rotation.x = -Math.PI / 2;
  m.rotation.z = rot;
  m.position.set(x, y, z);
  m.renderOrder = 1;
  scene.add(m);
}
addContact(8.55, 7.55, 2.0, 1.5, 0.0);
addContact(7.8, 5.9, 2.7, 1.2, 0.0, 0.172);
addContact(-2.35, 6.15, 1.35, 1.0, 0.0, 0.173);
addContact(-7.7, 5.55, 1.8, 1.3, 0.0);
addContact(6.72, 5.25, 1.1, 0.9, 0.0);
addContact(13.8, 5.9, 4.8, 4.2, 0.0);
addContact(-10.6, 6.2, 3.6, 3.2, 0.0);
addContact(-14.0, 1.4, 3.2, 3.0, 0.0);
addContact(10.2, 6.4, 2.1, 0.85, 0.0, 0.172);
addContact(-7.2, 7.82, 1.8, 0.8, 0.0, 0.172);
addContact(-4.85, 8.2, 0.85, 0.72, 0.0, 0.172);
addContact(-3.2, 9.1, 0.7, 0.7, 0.0, 0.172);
addContact(-9.4, 8.4, 1.25, 0.9, 0.0, 0.172);
addContact(-6.8, 9.25, 1.0, 1.0, 0.0, 0.172);
addContact(6.95, 8.3, 0.55, 0.55, 0.0, 0.172);
addContact(11.9, 7.0, 0.55, 0.55, 0.0, 0.172);

// A thin, hand-authored reflection veil over the shop windows. The physical
// glass material already reflects the environment map; this adds the readable
// sky / street-light sheen that sells the glass at this camera distance.
const glassReflectionTex = makeCanvasTexture(768, 384, (ctx, w, h) => {
  ctx.fillStyle = 'rgb(0,0,0)';
  ctx.fillRect(0, 0, w, h);
  const g = ctx.createLinearGradient(0, 0, 0, h);
  g.addColorStop(0, 'rgba(154,194,224,.48)');
  g.addColorStop(0.28, 'rgba(110,151,181,.14)');
  g.addColorStop(0.65, 'rgba(60,89,104,.05)');
  g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);
  // A soft diagonal street-light reflection.
  ctx.save();
  ctx.translate(w * .55, h * .2);
  ctx.rotate(-0.42);
  const band = ctx.createLinearGradient(-w * .18, 0, w * .16, 0);
  band.addColorStop(0, 'rgba(255,255,255,0)');
  band.addColorStop(0.48, 'rgba(214,233,247,.20)');
  band.addColorStop(0.58, 'rgba(255,255,255,.28)');
  band.addColorStop(0.7, 'rgba(255,234,198,.08)');
  band.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = band;
  ctx.fillRect(-w * .18, -h * .45, w * .36, h * 1.1);
  ctx.restore();
  // Two hairline highlights near the frame edges.
  ctx.fillStyle = 'rgba(255,255,255,.12)';
  ctx.fillRect(w * .04, 0, 2, h);
  ctx.fillStyle = 'rgba(200,226,238,.08)';
  ctx.fillRect(w * .61, 0, 1, h);
});
const glassReflectionMat = new THREE.MeshBasicMaterial({
  map: glassReflectionTex,
  transparent: true,
  opacity: 0.14,
  blending: THREE.AdditiveBlending,
  depthWrite: false,
  side: THREE.DoubleSide,
  toneMapped: false,
});
function addGlassReflection(x, width) {
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, 2.66), glassReflectionMat);
  mesh.position.set(x, 1.95, 4.735);
  mesh.renderOrder = 4;
  scene.add(mesh);
}
addGlassReflection(-3.8, 4.9);
addGlassReflection(4.2, 4.1);

// ---------------------------------------------------------------------------
// GLB loading
// ---------------------------------------------------------------------------
const bootStart = performance.now();
const loadingEl = document.getElementById('loading');
const loadBar = document.getElementById('load-bar');
const loadPct = document.getElementById('load-pct');
const loadStatus = document.getElementById('load-status');
const clockEl = document.getElementById('clock');
updateClock();
setInterval(updateClock, 20000);

let fakeProgress = 0;
const progressTimer = setInterval(() => {
  fakeProgress = Math.min(88, fakeProgress + 3 + Math.random() * 9);
  setProgress(fakeProgress, '正在组装货架与灯箱');
}, 120).unref?.();

function setProgress(value, status) {
  const p = clamp(value, 0, 100);
  if (loadBar) loadBar.style.width = `${p}%`;
  if (loadPct) loadPct.textContent = String(Math.round(p)).padStart(2, '0');
  if (status && loadStatus) loadStatus.textContent = status;
}

let modelRoot = null;
let glbMeshes = [];
let glbMaterialBase = new Map();

function prepareMaterials(root) {
  const seen = new Set();
  root.traverse((o) => {
    if (!o.isMesh) return;
    const material = o.material;
    if (!material) return;
    const name = material.name || '';
    glbMeshes.push(o);
    // Keep shadows architectural and grounded.
    const transparent = material.transparent || /Glass|Neon|Decal|Aisle|Window/.test(name);
    o.castShadow = !transparent && !/Ground|Road|Sidewalk|Curb|Asphalt|Paint|Foundation|Gutter|Lane|Crosswalk|Storm|Manhole|Tree_Leaves/.test(name);
    o.receiveShadow = !transparent || /Glass/.test(name);
    o.frustumCulled = true;
    if (seen.has(material.uuid)) return;
    seen.add(material.uuid);
    material.envMapIntensity = 0.6;
    if (/Glass_Store|Glass_Fridge/.test(name)) {
      material.transparent = true;
      material.depthWrite = false;
      material.side = THREE.DoubleSide;
      material.opacity = name === 'M_Glass_Store' ? 0.17 : 0.11;
      material.roughness = 0.035;
      material.metalness = 0.1;
      material.envMapIntensity = 2.35;
      material.clearcoat = 0.9;
      material.clearcoatRoughness = 0.035;
    }
    if (/Neon|Decal/.test(name)) {
      material.transparent = true;
      material.depthWrite = false;
      material.polygonOffset = true;
      material.polygonOffsetFactor = -1;
      material.polygonOffsetUnits = -1;
      material.toneMapped = !/Neon/.test(name);
    }
    if (/Sign|Neon|LED|Glow|Header|Screen/.test(name)) {
      material.toneMapped = !/Neon/.test(name);
    }
    if (/Store_Floor|Store_Tiles/.test(name)) {
      material.roughness = 0.3;
      material.envMapIntensity = 0.85;
    }
    if (/Sidewalk/.test(name)) material.roughness = 0.74;
    if (/Asphalt/.test(name)) material.roughness = 0.84;
    const group = TONE_BASE[name] || (name.startsWith('M_Aisle') ? 'decal' : null);
    if (group) {
      const base = material.emissiveIntensity ?? 1;
      EMISSIVE_MATERIALS.push({ mat: material, base, group, name });
      glbMaterialBase.set(material.uuid, base);
    }
  });
}

function isUnderDoorLeaf(obj) {
  let p = obj;
  while (p) {
    if (p.name === 'Door_Leaf_Left' || p.name === 'Door_Leaf_Right') return true;
    p = p.parent;
  }
  return false;
}

function mergeOpaqueMeshes(root) {
  // The exporter gives us many tiny objects. Merge opaque meshes by material
  // and attribute layout to keep the interactive scene light on draw calls.
  // Transparent objects (glass, decals, neon) and the two animated door leaves
  // must stay independent, so only actually merged sources are removed.
  const groups = new Map();
  const mergedSources = new Set();
  root.updateWorldMatrix(true, true);
  for (const mesh of glbMeshes) {
    if (!mesh.geometry || !mesh.material) continue;
    if (isUnderDoorLeaf(mesh)) continue;
    if (mesh.material.transparent || /Glass|Neon|Decal/.test(mesh.material.name || '')) continue;
    const geo = mesh.geometry.index ? mesh.geometry.toNonIndexed() : mesh.geometry.clone();
    // Keep a common minimal attribute layout. Some cylinders intentionally
    // have no UVs and will not be grouped with mapped architecture.
    const keep = ['position', 'normal'];
    if (geo.getAttribute('uv')) keep.push('uv');
    for (const key of Object.keys(geo.attributes)) {
      if (!keep.includes(key)) geo.deleteAttribute(key);
    }
    if (!geo.getAttribute('normal')) geo.computeVertexNormals();
    const sig = `${mesh.material.uuid}|${keep.join(',')}`;
    if (!groups.has(sig)) groups.set(sig, { material: mesh.material, geos: [], cast: false, receive: false });
    const g = groups.get(sig);
    geo.applyMatrix4(mesh.matrixWorld);
    g.geos.push(geo);
    g.cast ||= mesh.castShadow;
    g.receive ||= mesh.receiveShadow;
    mergedSources.add(mesh);
  }
  const parent = new THREE.Group();
  parent.name = 'Merged_Store';
  root.add(parent);
  for (const { material, geos, cast, receive } of groups.values()) {
    if (!geos.length) continue;
    let merged;
    try {
      merged = geos.length === 1 ? geos[0] : mergeGeometries(geos, false);
    } catch (e) {
      merged = null;
    }
    if (!merged) {
      for (const g of geos) {
        const m = new THREE.Mesh(g, material);
        m.castShadow = cast; m.receiveShadow = receive;
        parent.add(m);
      }
      continue;
    }
    const mesh = new THREE.Mesh(merged, material);
    mesh.castShadow = cast;
    mesh.receiveShadow = receive;
    parent.add(mesh);
  }
  // Remove only meshes that were actually baked into the merged group.
  for (const mesh of mergedSources) mesh.removeFromParent();
  return parent;
}

function initDoorLeaves() {
  if (!modelRoot) return;
  doorLeaves.left = modelRoot.getObjectByName('Door_Leaf_Left');
  doorLeaves.right = modelRoot.getObjectByName('Door_Leaf_Right');
  if (doorLeaves.left) doorLeaves.leftX = doorLeaves.left.position.x;
  if (doorLeaves.right) doorLeaves.rightX = doorLeaves.right.position.x;
}

new GLTFLoader().load(
  glbUrl,
  (gltf) => {
    clearInterval(progressTimer);
    modelRoot = gltf.scene;
    modelRoot.name = '7-Eleven_World';
    scene.add(modelRoot);
    prepareMaterials(modelRoot);
    try {
      mergeOpaqueMeshes(modelRoot);
    } catch (error) {
      console.warn('Opaque merge skipped:', error);
    }
    initDoorLeaves();
    initMaterialGroups();
    applyCurrentToScene(0, 1);
    // Let the intentionally designed loading card breathe for a moment even
    // when the inlined GLB decodes instantly, then open the doors.
    const remaining = Math.max(0, 1000 - (performance.now() - bootStart));
    setTimeout(() => {
      setProgress(100, '开门营业中');
      setTimeout(() => {
        state.ready = true;
        loadingEl.classList.add('is-done');
        document.body.classList.add('revealed');
        beginExperience();
        window.__SEVEN_READY__ = true;
      }, 450);
    }, remaining);
  },
  (event) => {
    if (event && event.total) {
      fakeProgress = Math.max(fakeProgress, (event.loaded / event.total) * 95);
      setProgress(fakeProgress, '正在组装货架与灯箱');
    }
  },
  (error) => {
    console.error('GLB load failed', error);
    clearInterval(progressTimer);
    setProgress(0, '模型载入失败');
    if (loadStatus) loadStatus.textContent = '模型载入失败，请重新整理';
  },
);

// ---------------------------------------------------------------------------
// Environment map (used mostly by glass, metal and the sky sheen)
// ---------------------------------------------------------------------------
const envTextures = {
  day: makeEnvTexture(MODE_PARAMS.day),
  dusk: makeEnvTexture(MODE_PARAMS.dusk),
  night: makeEnvTexture(MODE_PARAMS.night),
};
for (const tex of Object.values(envTextures)) tex.mapping = THREE.EquirectangularReflectionMapping;
scene.environment = envTextures.night;
scene.environmentIntensity = 0.6;

// ---------------------------------------------------------------------------
// Camera intro, reset and auto-rotate
// ---------------------------------------------------------------------------
const introStartPos = startView.pos.clone().multiplyScalar(1.3).add(new THREE.Vector3(0, 2.2, 0));
const introStartTarget = startView.target.clone();
function beginExperience() {
  if (state.intro) {
    state.introStart = performance.now();
    camera.position.copy(introStartPos);
    orbit.target.copy(introStartTarget);
    orbit.enabled = false;
    orbit.update();
    // The loading screen just dissolved; gently push into the storefront.
    setTimeout(() => {
      if (state.intro) startIntroTween();
    }, 80);
  } else {
    camera.position.copy(startView.pos);
    orbit.target.copy(startView.target);
    orbit.enabled = true;
    orbit.autoRotate = state.autoRotate && !CAPTURE;
    orbit.update();
  }
  if (UI_HIDDEN) document.body.classList.add('ui-hidden');
}
function startIntroTween() {
  const start = performance.now();
  const duration = state.introDuration;
  function tick(now) {
    const t = clamp((now - start) / duration, 0, 1);
    const e = easeInOutCubic(t);
    camera.position.lerpVectors(introStartPos, startView.pos, e);
    orbit.target.lerpVectors(introStartTarget, startView.target, e);
    camera.lookAt(orbit.target);
    if (t < 1) {
      requestAnimationFrame(tick);
    } else {
      state.intro = false;
      orbit.enabled = true;
      orbit.autoRotate = state.autoRotate && !CAPTURE;
      syncAutoRotateUI();
    }
  }
  requestAnimationFrame(tick);
}
function skipIntro() {
  if (!state.intro) return;
  state.intro = false;
  camera.position.copy(startView.pos);
  orbit.target.copy(startView.target);
  orbit.enabled = true;
  orbit.autoRotate = state.autoRotate && !CAPTURE;
  orbit.update();
  syncAutoRotateUI();
}

function resetView(animate = true) {
  if (state.inside) {
    if (state.walking) return;
    if (state.insideStop && state.insideStop !== 'entrance') walkToStop('entrance');
    else resetInteriorLook();
    return;
  }
  const view = getView();
  if (!animate) {
    camera.position.copy(view.pos);
    orbit.target.copy(view.target);
    camera.fov = view.fov;
    camera.updateProjectionMatrix();
    orbit.update();
    return;
  }
  state.tween = {
    start: performance.now(),
    duration: 1100,
    fromPos: camera.position.clone(),
    toPos: view.pos.clone(),
    fromTarget: orbit.target.clone(),
    toTarget: view.target.clone(),
    fromFov: camera.fov,
    toFov: view.fov,
  };
}

function handleTween(now) {
  if (!state.tween) return;
  const t = clamp((now - state.tween.start) / state.tween.duration, 0, 1);
  const e = easeInOutCubic(t);
  camera.position.lerpVectors(state.tween.fromPos, state.tween.toPos, e);
  orbit.target.lerpVectors(state.tween.fromTarget, state.tween.toTarget, e);
  camera.fov = lerp(state.tween.fromFov, state.tween.toFov, e);
  camera.updateProjectionMatrix();
  if (t >= 1) state.tween = null;
}

function updateEnterButton() {
  if (!btnEnter) return;
  const inside = state.inside;
  btnEnter.classList.toggle('is-on', inside);
  btnEnter.setAttribute('aria-pressed', inside ? 'true' : 'false');
  btnEnter.title = state.entering
    ? '正在走进店内'
    : inside
      ? '回到街角'
      : '走进店内';
}

function showHintContent(html) {
  if (!hintEl) return;
  hintEl.innerHTML = html;
  hintEl.style.opacity = '1';
  hideHintSoon();
}

const INTERIOR_HINT = '<span class="hint-line"></span><span>拖动环顾</span><i>·</i><span>右下角「店内导览」或货架标签走动</span><i>·</i><span>点门图示离开</span><span class="hint-line"></span>';

function applyInteriorLook() {
  camera.rotation.order = 'YXZ';
  camera.rotation.set(state.look.pitch, state.look.yaw, 0, 'YXZ');
}

function setInteriorLookFrom(pos, target) {
  const dir = target.clone().sub(pos).normalize();
  state.look.yaw = Math.atan2(-dir.x, -dir.z);
  state.look.pitch = Math.asin(clamp(dir.y, -0.7, 0.7));
  applyInteriorLook();
}

function setInteriorLookFromTarget() {
  setInteriorLookFrom(INTERIOR_POS, INTERIOR_TARGET);
}

function resetInteriorLook() {
  setInteriorLookFromTarget();
  showToast('LOOK RESET');
}

function startInteriorTour() {
  state.tour = {
    start: performance.now(),
    duration: REDUCED_MOTION ? 1 : 1900,
    fromPos: STAGING_POS.clone(),
    toPos: INTERIOR_POS.clone(),
    fromTarget: STAGING_TARGET.clone(),
    toTarget: INTERIOR_TARGET.clone(),
    fromFov: 44,
    toFov: 50,
    onDone: () => {
      state.entering = false;
      state.inside = true;
      state.insideStop = 'entrance';
      state.walking = false;
      document.body.classList.remove('walking');
      state.doorForceOpen = false;
      state.doorCloseAt = performance.now() + 2400;
      setInteriorLookFromTarget();
      updateEnterButton();
      updateWalkMarkers();
      showToast('INTERIOR / 店内视角');
      showHintContent(INTERIOR_HINT);
    },
  };
}

function enterStore() {
  if (!state.ready || CAPTURE || state.photoMode || state.coffeeOpen || state.shopOpen || state.walking || state.entering || state.exiting) return;
  if (state.inside) { exitStore(); return; }
  if (state.modalOpen) closeModal();
  if (state.intro) skipIntro();
  state.streetView = {
    pos: camera.position.clone(),
    target: orbit.target.clone(),
    fov: camera.fov,
  };
  state.entering = true;
  state.autoRotate = false;
  state.hasInteracted = true;
  state.doorForceOpen = true;
  document.body.classList.add('inside');
  updateEnterButton();
  syncAutoRotateUI();
  sceneFade?.classList.add('is-active');
  setTimeout(() => {
    state.tween = null;
    orbit.enabled = false;
    camera.position.copy(STAGING_POS);
    orbit.target.copy(STAGING_TARGET);
    camera.fov = 44;
    camera.updateProjectionMatrix();
    camera.lookAt(orbit.target);
    state.look.dragging = false;
    startInteriorTour();
    sceneFade?.classList.remove('is-active');
  }, REDUCED_MOTION ? 0 : 340);
}

function exitStore() {
  if (!state.inside || state.entering || state.exiting || state.walking) return;
  state.exiting = true;
  state.doorForceOpen = true;
  state.autoRotate = false;
  state.look.dragging = false;
  syncAutoRotateUI();
  sceneFade?.classList.add('is-active');
  setTimeout(() => {
    const saved = state.streetView || getView();
    camera.position.copy(saved.pos);
    orbit.target.copy(saved.target);
    camera.fov = saved.fov;
    camera.updateProjectionMatrix();
    orbit.enabled = true;
    orbit.update();
    state.inside = false;
    state.exiting = false;
    state.entering = false;
    state.walking = false;
    state.insideStop = 'entrance';
    document.body.classList.remove('walking');
    state.doorForceOpen = false;
    state.doorCloseAt = performance.now() + 650;
    document.body.classList.remove('inside');
    updateEnterButton();
    if (hintEl) {
      hintEl.innerHTML = hintOriginal;
      hintEl.style.opacity = '0';
    }
    syncAutoRotateUI();
    sceneFade?.classList.remove('is-active');
    showToast('STREET VIEW / 街角');
  }, REDUCED_MOTION ? 0 : 340);
}

function updateInteriorTour(now) {
  if (!state.tour) return;
  const t = clamp((now - state.tour.start) / state.tour.duration, 0, 1);
  const e = easeInOutCubic(t);
  camera.position.lerpVectors(state.tour.fromPos, state.tour.toPos, e);
  orbit.target.lerpVectors(state.tour.fromTarget, state.tour.toTarget, e);
  camera.fov = lerp(state.tour.fromFov, state.tour.toFov, e);
  camera.updateProjectionMatrix();
  camera.lookAt(orbit.target);
  if (t >= 1) {
    const done = state.tour.onDone;
    state.tour = null;
    if (done) done();
  }
}

function updateDoor(dt, now) {
  if (!doorLeaves.left || !doorLeaves.right) return;
  let want = 0;
  if (state.doorForceOpen || state.entering || state.exiting) {
    want = 1;
  } else if (state.inside) {
    want = (state.doorCloseAt && now > state.doorCloseAt) ? 0 : 1;
  } else if (state.ready && !state.tour && camera.position.z > 5.1) {
    const dx = camera.position.x - DOOR_POINT.x;
    const dz = camera.position.z - DOOR_POINT.z;
    if (Math.hypot(dx, dz) < 7.4) want = 1;
  }
  doorLeaves.open = damp(doorLeaves.open, want, 5.0, dt);
  doorLeaves.left.position.x = doorLeaves.leftX - 0.62 * doorLeaves.open;
  doorLeaves.right.position.x = doorLeaves.rightX + 0.62 * doorLeaves.open;
}

const btnPhoto = document.getElementById('btn-photo');
const photoStateEl = document.getElementById('photo-state');

function enterPhotoMode() {
  if (state.photoMode || state.entering || state.exiting || state.coffeeOpen || state.shopOpen || state.walking) return;
  if (state.modalOpen) closeModal();
  state.photoMode = true;
  state.autoRotate = false;
  syncAutoRotateUI();
  document.body.classList.add('photo-mode');
  if (btnPhoto) {
    btnPhoto.classList.add('is-on');
    btnPhoto.setAttribute('aria-pressed', 'true');
  }
  if (photoStateEl) photoStateEl.textContent = '拖动取景';
}

function exitPhotoMode() {
  if (!state.photoMode) return;
  state.photoMode = false;
  document.body.classList.remove('photo-mode');
  if (btnPhoto) {
    btnPhoto.classList.remove('is-on');
    btnPhoto.setAttribute('aria-pressed', 'false');
  }
  syncAutoRotateUI();
}

function downloadPhoto() {
  if (!state.photoMode) return;
  if (photoStateEl) photoStateEl.textContent = '正在输出…';
  composer.render();
  const name = `7-eleven-${state.mode}${state.inside ? '-interior' : ''}-${new Date().toISOString().replace(/[:.]/g, '-')}.png`;
  const finish = () => {
    if (photoStateEl) photoStateEl.textContent = '已保存';
    setTimeout(() => {
      if (photoStateEl && state.photoMode) photoStateEl.textContent = '拖动取景';
    }, 1600);
  };
  const canvasEl = renderer.domElement;
  if (canvasEl.toBlob) {
    canvasEl.toBlob((blob) => {
      if (!blob) { finish(); return; }
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = name;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 3000);
      finish();
    }, 'image/png');
  } else {
    const a = document.createElement('a');
    a.href = canvasEl.toDataURL('image/png');
    a.download = name;
    a.click();
    finish();
  }
}

if (btnPhoto) btnPhoto.addEventListener('click', () => {
  if (state.photoMode) exitPhotoMode();
  else enterPhotoMode();
});
document.getElementById('btn-photo-exit')?.addEventListener('click', exitPhotoMode);
document.getElementById('btn-photo-save')?.addEventListener('click', downloadPhoto);

// ---------------------------------------------------------------------------
// Night coffee: a small self-service order, payment and artifact flow
// ---------------------------------------------------------------------------
const COFFEE_MENU = {
  americano: { name: '美式', en: 'Americano', price: 45, color: '#3b2418' },
  latte: { name: '拿铁', en: 'Latte', price: 55, color: '#b68a63' },
  cappuccino: { name: '卡布奇诺', en: 'Cappuccino', price: 55, color: '#c9a27b' },
  mocha: { name: '摩卡', en: 'Mocha', price: 65, color: '#6d4934' },
};
const PAY_METHODS = {
  alipay: { name: 'Alipay', zh: '支付宝', color: '#1677ff', mark: '支' },
  wechat: { name: 'WeChat Pay', zh: '微信支付', color: '#07c160', mark: '微' },
  unionpay: { name: 'UnionPay', zh: '银联', color: '#005bac', mark: '银' },
};
const coffeeState = {
  stage: 'order', type: 'latte', hot: true, method: null, discount: false,
  order: null, receiptCanvas: null, cardCanvas: null, payTimer: null,
};
const coffeeModal = document.getElementById('coffee-modal');
const coffeeCta = document.getElementById('btn-coffee');
const coffeePreviewName = document.getElementById('coffee-preview-name');
const coffeeCupScene = document.getElementById('coffee-cup-scene');
const coffeeTotal = document.getElementById('coffee-total');
const coffeePayName = document.getElementById('coffee-pay-name');
const coffeePayPrice = document.getElementById('coffee-pay-price');
const coffeePayTotal = document.getElementById('coffee-pay-total');
const coffeeDiscountInput = document.getElementById('coffee-discount');
const coffeeDiscountLine = document.getElementById('coffee-discount-line');
const coffeeDiscountValue = document.getElementById('coffee-discount-value');
const coffeeQrWrap = document.getElementById('coffee-qr-wrap');
const coffeeQrImg = document.getElementById('coffee-qr');
const coffeeQrHint = document.getElementById('coffee-qr-hint');
const coffeePayBtn = document.getElementById('coffee-pay');
const coffeeReceiptImg = document.getElementById('coffee-receipt-img');
const coffeeCardImg = document.getElementById('coffee-card-img');

function coffeeDisplayName() {
  const item = COFFEE_MENU[coffeeState.type] || COFFEE_MENU.latte;
  return `${coffeeState.hot ? '热' : '冰'}${item.name}`;
}

function setCoffeeStage(stage) {
  coffeeState.stage = stage;
  document.querySelectorAll('.coffee-stage').forEach((el) => {
    const active = el.dataset.coffeeStage === stage;
    el.classList.toggle('is-active', active);
    el.setAttribute('aria-hidden', active ? 'false' : 'true');
  });
}

function coffeeAmounts() {
  const item = COFFEE_MENU[coffeeState.type] || COFFEE_MENU.latte;
  const original = item.price;
  const total = coffeeState.discount ? Math.round(original * 0.88) : original;
  return { original, total, discount: original - total };
}

function renderCoffeeDiscount() {
  const amounts = coffeeAmounts();
  if (coffeePayTotal) coffeePayTotal.textContent = `NT$${amounts.total}`;
  if (coffeeDiscountLine) coffeeDiscountLine.hidden = amounts.discount <= 0;
  if (coffeeDiscountValue) coffeeDiscountValue.textContent = `-NT$${amounts.discount}`;
}

function renderCoffee() {
  const item = COFFEE_MENU[coffeeState.type] || COFFEE_MENU.latte;
  document.querySelectorAll('.coffee-option').forEach((el) => {
    el.classList.toggle('is-selected', el.dataset.coffee === coffeeState.type);
  });
  document.querySelectorAll('.coffee-temp button').forEach((el) => {
    el.classList.toggle('is-active', (el.dataset.temp === 'hot') === coffeeState.hot);
  });
  if (coffeePreviewName) coffeePreviewName.textContent = coffeeDisplayName();
  if (coffeeCupScene) {
    coffeeCupScene.style.setProperty('--coffee-liquid', item.color);
    coffeeCupScene.classList.toggle('is-iced', !coffeeState.hot);
  }
  if (coffeeTotal) coffeeTotal.textContent = `NT$${item.price}`;
  if (coffeePayName) coffeePayName.textContent = coffeeDisplayName();
  if (coffeePayPrice) coffeePayPrice.textContent = `NT$${item.price}`;
  renderCoffeeDiscount();
}

function openCoffee() {
  if (!state.inside || state.entering || state.exiting || state.photoMode || state.coffeeOpen || state.shopOpen || state.walking) return;
  state.coffeeOpen = true;
  state.autoRotate = false;
  syncAutoRotateUI();
  document.body.classList.add('coffee-open');
  coffeeModal?.classList.add('is-open');
  coffeeModal?.setAttribute('aria-hidden', 'false');
  coffeeState.stage = 'order';
  coffeeState.method = null;
  coffeeState.discount = false;
  if (coffeeDiscountInput) coffeeDiscountInput.checked = false;
  setCoffeeStage('order');
  renderCoffee();
  setTimeout(() => document.getElementById('coffee-close')?.focus(), 60);
}

function closeCoffee() {
  if (!state.coffeeOpen) return;
  if (coffeeState.payTimer) {
    clearTimeout(coffeeState.payTimer);
    coffeeState.payTimer = null;
  }
  state.coffeeOpen = false;
  document.body.classList.remove('coffee-open');
  coffeeModal?.classList.remove('is-open');
  coffeeModal?.setAttribute('aria-hidden', 'true');
  setTimeout(() => coffeeCta?.focus(), 60);
}

function goCoffeePay() {
  coffeeState.method = null;
  coffeeState.discount = false;
  if (coffeeDiscountInput) coffeeDiscountInput.checked = false;
  setCoffeeStage('pay');
  renderCoffeeDiscount();
  coffeePayBtn.disabled = true;
  coffeePayBtn.textContent = '确认付款';
  document.querySelectorAll('.coffee-pay-method').forEach((el) => el.classList.remove('is-selected'));
  coffeeQrWrap?.classList.remove('has-qr');
  if (coffeeQrHint) coffeeQrHint.textContent = '选择支付方式后显示模拟扫码';
}

function selectCoffee(id) {
  if (!COFFEE_MENU[id]) return;
  coffeeState.type = id;
  renderCoffee();
}

function setCoffeeTemp(hot) {
  coffeeState.hot = hot;
  renderCoffee();
}

function drawPseudoQr(method, salt = '') {
  const canvas = document.createElement('canvas');
  canvas.width = 320;
  canvas.height = 320;
  const ctx = canvas.getContext('2d');
  const data = PAY_METHODS[method];
  const modules = 29;
  const pad = 22;
  const cell = (320 - pad * 2) / modules;
  ctx.fillStyle = '#fffdf6';
  ctx.fillRect(0, 0, 320, 320);
  let seed = 0;
  const key = `${method}-${Date.now()}-${salt}`;
  for (let i = 0; i < key.length; i++) seed = (seed * 31 + key.charCodeAt(i)) >>> 0;
  const rng = mulberry32(seed || 1);
  const isFinder = (x, y) => (x < 7 && y < 7) || (x >= modules - 7 && y < 7) || (x < 7 && y >= modules - 7);
  ctx.fillStyle = '#111b17';
  for (let y = 0; y < modules; y++) {
    for (let x = 0; x < modules; x++) {
      if (isFinder(x, y)) continue;
      if (rng() > 0.54) {
        ctx.fillRect(pad + x * cell, pad + y * cell, cell - .5, cell - .5);
      }
    }
  }
  // Finder patterns.
  for (const [fx, fy] of [[0, 0], [modules - 7, 0], [0, modules - 7]]) {
    ctx.fillStyle = '#111b17';
    ctx.fillRect(pad + fx * cell, pad + fy * cell, cell * 7, cell * 7);
    ctx.fillStyle = '#fffdf6';
    ctx.fillRect(pad + (fx + 1) * cell, pad + (fy + 1) * cell, cell * 5, cell * 5);
    ctx.fillStyle = '#111b17';
    ctx.fillRect(pad + (fx + 2) * cell, pad + (fy + 2) * cell, cell * 3, cell * 3);
  }
  // Colour stamp in the centre.
  ctx.fillStyle = data.color;
  ctx.beginPath();
  ctx.arc(160, 160, 27, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = '#fff';
  ctx.font = '600 26px "PingFang TC", "Noto Sans TC", sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(data.mark, 160, 163);
  return canvas.toDataURL('image/png');
}

function selectPayMethod(method) {
  if (!PAY_METHODS[method]) return;
  coffeeState.method = method;
  document.querySelectorAll('.coffee-pay-method').forEach((el) => {
    el.classList.toggle('is-selected', el.dataset.pay === method);
  });
  const data = PAY_METHODS[method];
  if (coffeeQrImg) coffeeQrImg.src = drawPseudoQr(method, coffeeState.type);
  coffeeQrWrap?.classList.add('has-qr');
  if (coffeeQrHint) coffeeQrHint.textContent = `${data.name} · 模拟扫码`;
  coffeePayBtn.disabled = false;
}

function pad2(v) { return String(v).padStart(2, '0'); }
function coffeeClock(date) {
  return `${date.getFullYear()}/${pad2(date.getMonth() + 1)}/${pad2(date.getDate())} ${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
}

function buildCoffeeOrder() {
  const item = COFFEE_MENU[coffeeState.type] || COFFEE_MENU.latte;
  const now = new Date();
  const method = PAY_METHODS[coffeeState.method] || PAY_METHODS.alipay;
  const orderNo = 'T7-' + now.getTime().toString(36).toUpperCase().slice(-6);
  const amounts = coffeeAmounts();
  return {
    no: orderNo, item, qty: 1, originalTotal: amounts.original, discount: amounts.discount,
    total: amounts.total, staff: amounts.discount > 0,
    hot: coffeeState.hot, name: coffeeDisplayName(),
    method, time: now, timeText: coffeeClock(now),
  };
}

function drawReceipt(order) {
  const W = 720, H = 1190;
  const canvas = document.createElement('canvas');
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');
  const serif = '"PingFang TC", "Noto Sans TC", "Helvetica Neue", sans-serif';
  const mono = '"SFMono-Regular", Menlo, Consolas, monospace';
  ctx.fillStyle = '#fffdf6';
  ctx.fillRect(0, 0, W, H);
  // Top brand strips.
  ctx.fillStyle = '#ef5b2a'; ctx.fillRect(0, 0, W / 3, 8);
  ctx.fillStyle = '#14a46d'; ctx.fillRect(W / 3, 0, W / 3, 8);
  ctx.fillStyle = '#e8323e'; ctx.fillRect((W / 3) * 2, 0, W / 3, 8);
  ctx.textAlign = 'left';
  ctx.fillStyle = '#1b2a23';
  ctx.font = `600 30px ${serif}`;
  ctx.fillText('7-ELEVEN 中山门店', 48, 65);
  ctx.font = `400 13px ${mono}`;
  ctx.fillStyle = 'rgba(27,42,35,.6)';
  ctx.fillText('ELECTRONIC RECEIPT / 电子消费明细', 48, 93);
  ctx.fillText('FICTIONAL STORE · DEMO', 48, 113);
  ctx.strokeStyle = 'rgba(27,42,35,.26)';
  ctx.setLineDash([3, 5]);
  ctx.beginPath(); ctx.moveTo(48, 140); ctx.lineTo(672, 140); ctx.stroke();
  ctx.setLineDash([]);
  ctx.font = `400 13px ${mono}`;
  ctx.fillStyle = '#26382d';
  ctx.fillText(`DATE  ${order.timeText}`, 48, 174);
  ctx.fillText(`ORDER ${order.no}`, 48, 198);
  ctx.fillText('TERMINAL  SELF-SERVICE 01', 48, 222);
  ctx.strokeStyle = 'rgba(27,42,35,.26)';
  ctx.setLineDash([3, 5]);
  ctx.beginPath(); ctx.moveTo(48, 250); ctx.lineTo(672, 250); ctx.stroke();
  ctx.setLineDash([]);
  ctx.font = `500 23px ${serif}`;
  ctx.fillText(order.name, 48, 300);
  ctx.textAlign = 'right';
  ctx.font = `400 15px ${mono}`;
  ctx.fillText(`x ${order.qty}`, 560, 300);
  ctx.fillText(`NT$${order.originalTotal ?? order.total}`, 672, 300);
  ctx.textAlign = 'left';
  ctx.fillStyle = 'rgba(27,42,35,.58)';
  ctx.font = `400 12px ${mono}`;
  ctx.fillText(`${order.item.en.toUpperCase()} · ${order.hot ? 'HOT' : 'ICED'}`, 48, 327);
  ctx.strokeStyle = 'rgba(27,42,35,.2)';
  ctx.beginPath(); ctx.moveTo(48, 360); ctx.lineTo(672, 360); ctx.stroke();
  ctx.fillStyle = '#26382d';
  ctx.font = `400 14px ${mono}`;
  let ty = 398;
  ctx.fillText('SUBTOTAL', 48, ty); ctx.textAlign = 'right'; ctx.fillText(`NT$${order.originalTotal ?? order.total}`, 672, ty);
  ctx.textAlign = 'left'; ty += 27;
  if (order.discount > 0) {
    ctx.fillStyle = '#9c3c2f';
    ctx.fillText('STAFF 8.8', 48, ty); ctx.textAlign = 'right'; ctx.fillText(`-NT$${order.discount}`, 672, ty);
    ctx.textAlign = 'left'; ctx.fillStyle = '#26382d'; ty += 27;
  }
  ctx.fillText('TAX', 48, ty); ctx.textAlign = 'right'; ctx.fillText('INCLUDED', 672, ty);
  ctx.textAlign = 'left'; ty += 38;
  ctx.font = `600 24px ${serif}`;
  ctx.fillText('TOTAL', 48, ty); ctx.textAlign = 'right'; ctx.font = `500 34px ${serif}`; ctx.fillText(`NT$${order.total}`, 672, ty); ty += 42;
  ctx.textAlign = 'left';
  ctx.font = `400 13px ${mono}`;
  ctx.fillText(`PAYMENT  ${order.method.name.toUpperCase()} / ${order.method.zh}`, 48, ty); ty += 36;
  ctx.strokeStyle = 'rgba(27,42,35,.26)';
  ctx.setLineDash([3, 5]); ctx.beginPath(); ctx.moveTo(48, ty); ctx.lineTo(672, ty); ctx.stroke(); ctx.setLineDash([]); ty += 30;
  ctx.strokeStyle = '#b23e37';
  ctx.lineWidth = 2;
  ctx.strokeRect(48, ty, 624, 74);
  ctx.fillStyle = '#b23e37';
  ctx.font = `600 17px ${mono}`;
  ctx.textAlign = 'center';
  ctx.fillText('SIMULATED TRANSACTION', 360, ty + 31);
  ctx.font = `400 13px ${mono}`;
  ctx.fillText('非实际交易 · 仅供互动展示', 360, ty + 56);
  ctx.textAlign = 'left';
  ctx.lineWidth = 1;
  ty += 112;
  // Barcode.
  let seed = 0;
  for (let i = 0; i < order.no.length; i++) seed = (seed * 33 + order.no.charCodeAt(i)) >>> 0;
  const rng = mulberry32(seed || 7);
  let bx = 70;
  for (let i = 0; i < 46; i++) {
    const w = 2 + Math.floor(rng() * 5);
    ctx.fillStyle = '#1b2a23';
    ctx.fillRect(bx, ty, w, 54);
    bx += w + 3 + Math.floor(rng() * 4);
  }
  ctx.font = `400 11px ${mono}`;
  ctx.textAlign = 'center';
  ctx.fillStyle = 'rgba(27,42,35,.52)';
  ctx.fillText(`*${order.no}*`, 360, ty + 78);
  ctx.font = `400 12px ${mono}`;
  ctx.fillText('THANK YOU · 谢谢光临', 360, ty + 118);
  ctx.fillStyle = 'rgba(27,42,35,.34)';
  ctx.font = `400 10px ${mono}`;
  ctx.fillText('7-ELEVEN 中山门店 · FICTIONAL STORE', 360, ty + 146);
  ctx.textAlign = 'left';
  ctx.fillStyle = '#ef5b2a'; ctx.fillRect(48, 1132, 202, 4);
  ctx.fillStyle = '#14a46d'; ctx.fillRect(250, 1132, 202, 4);
  ctx.fillStyle = '#e8323e'; ctx.fillRect(452, 1132, 220, 4);
  return canvas;
}


function drawCoffeeCard(order) {
  const W = 1080, H = 1350;
  const canvas = document.createElement('canvas');
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');
  const serif = '"PingFang TC", "Noto Sans TC", "Helvetica Neue", sans-serif';
  const mono = '"SFMono-Regular", Menlo, Consolas, monospace';
  ctx.fillStyle = '#f3eddc';
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = '#1d3b2e';
  ctx.fillRect(0, 0, W, 190);
  const stripeY = 158;
  const stripeW = W / 3;
  ctx.fillStyle = '#ef5b2a'; ctx.fillRect(0, stripeY, stripeW, 16);
  ctx.fillStyle = '#1ebc7b'; ctx.fillRect(stripeW, stripeY, stripeW, 16);
  ctx.fillStyle = '#e8323e'; ctx.fillRect(stripeW * 2, stripeY, stripeW, 16);
  ctx.fillStyle = '#f7f1df';
  ctx.font = `600 44px ${serif}`;
  ctx.fillText('7-ELEVEN', 58, 82);
  ctx.font = `400 15px ${mono}`;
  ctx.fillStyle = 'rgba(247,241,223,.62)';
  ctx.fillText('NIGHT COFFEE · SELF SERVICE', 60, 115);
  ctx.textAlign = 'right';
  ctx.fillStyle = 'rgba(247,241,223,.72)';
  ctx.fillText('DIGITAL COFFEE CARD', W - 58, 82);
  ctx.fillText(order.timeText, W - 58, 115);
  ctx.textAlign = 'left';
  // Large title.
  ctx.fillStyle = '#20362a';
  ctx.font = `600 70px ${serif}`;
  ctx.fillText('深夜咖啡', 58, 292);
  ctx.fillStyle = 'rgba(35,55,43,.5)';
  ctx.font = `400 22px ${mono}`;
  ctx.fillText('NIGHT EDITION / 01', 60, 330);
  // Warm halo.
  const halo = ctx.createRadialGradient(540, 620, 50, 540, 620, 380);
  halo.addColorStop(0, 'rgba(239,172,102,.18)');
  halo.addColorStop(1, 'rgba(239,172,102,0)');
  ctx.fillStyle = halo; ctx.fillRect(0, 300, W, 660);
  // Cup illustration.
  const cupX = 540, cupTop = 475, cupW = 250, cupH = 300;
  ctx.save();
  ctx.translate(cupX, cupTop);
  // shadow
  const sh = ctx.createRadialGradient(0, cupH + 25, 10, 0, cupH + 25, 130);
  sh.addColorStop(0, 'rgba(32,47,39,.24)'); sh.addColorStop(1, 'rgba(32,47,39,0)');
  ctx.fillStyle = sh; ctx.beginPath(); ctx.ellipse(0, cupH + 22, 160, 39, 0, 0, Math.PI * 2); ctx.fill();
  // steam for hot
  if (order.hot) {
    ctx.strokeStyle = 'rgba(64,83,69,.3)'; ctx.lineWidth = 4; ctx.lineCap = 'round';
    for (const [sx, sy, len] of [[-50, -70, 78], [0, -86, 105], [52, -66, 66]]) {
      ctx.beginPath(); ctx.moveTo(sx, sy + len); ctx.bezierCurveTo(sx - 28, sy + len * .5, sx + 25, sy + len * .25, sx, sy); ctx.stroke();
    }
  }
  // cup body
  ctx.fillStyle = '#f8f1e2';
  ctx.beginPath();
  ctx.moveTo(-cupW / 2, 30); ctx.lineTo(cupW / 2, 30); ctx.lineTo(cupW * .36, cupH); ctx.lineTo(-cupW * .36, cupH); ctx.closePath(); ctx.fill();
  // liquid
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(-cupW / 2, 30); ctx.lineTo(cupW / 2, 30); ctx.lineTo(cupW * .36, cupH); ctx.lineTo(-cupW * .36, cupH); ctx.closePath(); ctx.clip();
  ctx.fillStyle = order.item.color;
  ctx.fillRect(-cupW / 2, cupH * .34, cupW, cupH * .66);
  ctx.fillStyle = 'rgba(255,247,225,.24)';
  ctx.beginPath(); ctx.ellipse(0, cupH * .34, cupW * .5, 15, 0, 0, Math.PI * 2); ctx.fill();
  ctx.restore();
  // sleeve
  ctx.fillStyle = '#f2e7d0';
  ctx.fillRect(-cupW * .45, 135, cupW * .9, 76);
  ctx.fillStyle = '#e9502c';
  ctx.font = `800 58px ${serif}`; ctx.textAlign = 'center'; ctx.fillText('7', 0, 195);
  ctx.fillStyle = '#ef5b2a'; ctx.fillRect(-cupW * .38, 222, 28, 36);
  ctx.fillStyle = '#1ebc7b'; ctx.fillRect(-14, 222, 28, 36);
  ctx.fillStyle = '#e8323e'; ctx.fillRect(10, 222, 28, 36);
  // lid
  ctx.fillStyle = '#28453a'; ctx.fillRect(-cupW / 2 - 12, 10, cupW + 24, 34);
  ctx.fillStyle = '#395b4b'; ctx.fillRect(-52, -7, 104, 22);
  // iced cubes
  if (!order.hot) {
    ctx.strokeStyle = 'rgba(255,255,255,.55)'; ctx.lineWidth = 3;
    for (const [ix, iy, r] of [[-67, 195, -14], [32, 170, 11], [50, 255, 18]]) {
      ctx.save(); ctx.translate(ix, iy); ctx.rotate(r * Math.PI / 180);
      ctx.fillStyle = 'rgba(226,249,243,.25)'; ctx.strokeRect(-19, -13, 38, 26); ctx.restore();
    }
  }
  ctx.restore();
  // Text block.
  ctx.fillStyle = '#20382b';
  ctx.font = `500 40px ${serif}`;
  ctx.textAlign = 'left';
  ctx.fillText(order.name, 58, 950);
  ctx.fillStyle = 'rgba(35,55,43,.48)';
  ctx.font = `400 18px ${mono}`;
  ctx.fillText(`${order.item.en.toUpperCase()} / ${order.hot ? 'HOT' : 'ICED'}`, 60, 982);
  ctx.strokeStyle = 'rgba(35,55,43,.18)'; ctx.beginPath(); ctx.moveTo(58, 1025); ctx.lineTo(W - 58, 1025); ctx.stroke();
  ctx.font = `400 15px ${mono}`;
  ctx.fillStyle = 'rgba(35,55,43,.55)';
  ctx.fillText(`ORDER ${order.no}`, 58, 1063);
  ctx.fillText(`PAYMENT ${order.method.name.toUpperCase()}`, 58, 1090);
  if (order.discount > 0) {
    ctx.fillStyle = '#9c3c2f';
    ctx.font = `400 13px ${mono}`;
    ctx.fillText(`STAFF 8.8 · -NT$${order.discount}`, 58, 1118);
    ctx.fillStyle = 'rgba(35,55,43,.55)';
  }
  ctx.textAlign = 'right';
  ctx.fillText('中山门店 · TAIPEI', W - 58, 1063);
  ctx.font = `600 20px ${serif}`;
  ctx.fillStyle = '#20382b';
  ctx.fillText('NT$' + order.total, W - 58, 1092);
  ctx.textAlign = 'left';
  // Barcode / demo footer.
  let seed = 0;
  for (let i = 0; i < order.no.length; i++) seed = (seed * 37 + order.no.charCodeAt(i)) >>> 0;
  const rng = mulberry32(seed || 11);
  let bx = 58;
  for (let i = 0; i < 44; i++) {
    const w = 2 + Math.floor(rng() * 5);
    ctx.fillStyle = '#20382b'; ctx.fillRect(bx, 1150, w, 40);
    bx += w + 3 + Math.floor(rng() * 4);
  }
  ctx.font = `400 13px ${mono}`;
  ctx.fillStyle = 'rgba(35,55,43,.42)';
  ctx.fillText('DIGITAL COFFEE CARD · SIMULATED · 非实际交易', 58, 1232);
  ctx.textAlign = 'right';
  ctx.fillText(`*${order.no}*`, W - 58, 1232);
  ctx.textAlign = 'left';
  ctx.fillStyle = '#ef5b2a'; ctx.fillRect(58, 1272, 200, 5);
  ctx.fillStyle = '#14a46d'; ctx.fillRect(258, 1272, 200, 5);
  ctx.fillStyle = '#e8323e'; ctx.fillRect(458, 1272, W - 516, 5);
  return canvas;
}

function downloadCanvas(canvas, filename) {
  if (!canvas) return;
  const finish = () => showToast('已下载 · DOWNLOADED');
  if (canvas.toBlob) {
    canvas.toBlob((blob) => {
      if (!blob) { finish(); return; }
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 3000);
      finish();
    }, 'image/png');
  } else {
    const a = document.createElement('a');
    a.href = canvas.toDataURL('image/png');
    a.download = filename;
    a.click();
    finish();
  }
}

function finishCoffeePayment() {
  const order = buildCoffeeOrder();
  coffeeState.order = order;
  const receipt = drawReceipt(order);
  const card = drawCoffeeCard(order);
  coffeeState.receiptCanvas = receipt;
  coffeeState.cardCanvas = card;
  if (coffeeReceiptImg) coffeeReceiptImg.src = receipt.toDataURL('image/png');
  if (coffeeCardImg) coffeeCardImg.src = card.toDataURL('image/png');
  setCoffeeStage('success');
  coffeePayBtn.textContent = '确认付款';
  coffeePayBtn.disabled = false;
}

function confirmCoffeePayment() {
  if (!coffeeState.method || !coffeePayBtn) return;
  coffeePayBtn.disabled = true;
  coffeePayBtn.textContent = '处理中…';
  if (coffeeState.payTimer) clearTimeout(coffeeState.payTimer);
  coffeeState.payTimer = setTimeout(() => {
    coffeeState.payTimer = null;
    if (!state.coffeeOpen) return;
    finishCoffeePayment();
  }, 1250);
}

if (coffeeCta) coffeeCta.addEventListener('click', openCoffee);
document.getElementById('coffee-close')?.addEventListener('click', closeCoffee);
document.querySelector('.coffee-backdrop')?.addEventListener('click', closeCoffee);
document.getElementById('coffee-next')?.addEventListener('click', goCoffeePay);
document.getElementById('coffee-back')?.addEventListener('click', () => setCoffeeStage('order'));
document.querySelectorAll('.coffee-option').forEach((el) => {
  el.addEventListener('click', () => selectCoffee(el.dataset.coffee));
});
document.querySelectorAll('.coffee-temp button').forEach((el) => {
  el.addEventListener('click', () => setCoffeeTemp(el.dataset.temp === 'hot'));
});
document.querySelectorAll('.coffee-pay-method').forEach((el) => {
  el.addEventListener('click', () => selectPayMethod(el.dataset.pay));
});
coffeePayBtn?.addEventListener('click', confirmCoffeePayment);
coffeeDiscountInput?.addEventListener('change', (e) => {
  coffeeState.discount = e.target.checked;
  renderCoffeeDiscount();
});
document.getElementById('coffee-download-receipt')?.addEventListener('click', () => {
  const o = coffeeState.order;
  downloadCanvas(coffeeState.receiptCanvas, `7-eleven-receipt-${o?.no || 'demo'}.png`);
});
document.getElementById('coffee-download-card')?.addEventListener('click', () => {
  const o = coffeeState.order;
  downloadCanvas(coffeeState.cardCanvas, `7-eleven-coffee-card-${o?.no || 'demo'}.png`);
});
document.getElementById('coffee-again')?.addEventListener('click', () => {
  coffeeState.method = null;
  setCoffeeStage('order');
  renderCoffee();
});
document.getElementById('coffee-done')?.addEventListener('click', () => {
  closeCoffee();
  showToast('NIGHT COFFEE · 完成');
});

// ---------------------------------------------------------------------------
// Rail shop: shelf categories, bag, checkout and shopping receipt
// ---------------------------------------------------------------------------
const SHOP_CATEGORIES = {
  drinks: { label: '冷藏饮料', en: 'COLD DRINKS' },
  snacks: { label: '零食', en: 'SNACKS' },
  daily: { label: '日用品', en: 'DAILY GOODS' },
};
const SHOP_PRODUCTS = {
  tea: { id: 'tea', category: 'drinks', name: '冷萃绿茶', en: 'COLD BREW TEA', price: 25, color: '#3f6f51', art: 'bottle' },
  cola: { id: 'cola', category: 'drinks', name: '深夜可乐', en: 'NIGHT COLA', price: 35, color: '#8e2d2d', art: 'can' },
  water: { id: 'water', category: 'drinks', name: '矿泉水', en: 'MINERAL WATER', price: 20, color: '#4f8096', art: 'bottle' },
  chips: { id: 'chips', category: 'snacks', name: '海盐洋芋片', en: 'SEA SALT CHIPS', price: 35, color: '#c49435', art: 'chips' },
  chocolate: { id: 'chocolate', category: 'snacks', name: '黑巧克力', en: 'DARK CHOCOLATE', price: 45, color: '#4a2c20', art: 'bar' },
  crackers: { id: 'crackers', category: 'snacks', name: '起司苏打饼', en: 'CHEESE CRACKERS', price: 30, color: '#b9834e', art: 'crackers' },
  condom: { id: 'condom', category: 'daily', name: '安全套', en: 'CONDOMS', price: 39, color: '#9d5a73', art: 'foil' },
  wipes: { id: 'wipes', category: 'daily', name: '湿纸巾', en: 'WET WIPES', price: 35, color: '#567b83', art: 'pack' },
  lighter: { id: 'lighter', category: 'daily', name: '打火机', en: 'LIGHTER', price: 25, color: '#a9503d', art: 'lighter' },
};
const shopState = {
  open: false, stage: 'browse', category: 'drinks', cart: {}, method: null, discount: false,
  payTimer: null, order: null, receiptCanvas: null,
};
const shopModal = document.getElementById('shop-modal');
const shopProductsEl = document.getElementById('shop-products');
const shopCartLinesEl = document.getElementById('shop-cart-lines');
const shopCartCountEl = document.getElementById('shop-cart-count');
const shopTotalEl = document.getElementById('shop-total');
const shopCheckoutBtn = document.getElementById('shop-checkout');
const shopPayLinesEl = document.getElementById('shop-pay-lines');
const shopPayTotalEl = document.getElementById('shop-pay-total');
const shopDiscountInput = document.getElementById('shop-discount');
const shopDiscountLine = document.getElementById('shop-discount-line');
const shopDiscountValue = document.getElementById('shop-discount-value');
const shopQrWrap = document.getElementById('shop-qr-wrap');
const shopQrImg = document.getElementById('shop-qr');
const shopQrHint = document.getElementById('shop-qr-hint');
const shopPayBtn = document.getElementById('shop-pay');
const shopReceiptImg = document.getElementById('shop-receipt-img');
const btnShop = document.getElementById('btn-shop');
const btnBag = document.getElementById('btn-bag');
const bagCountEl = document.getElementById('bag-count');

function shopItems() {
  return Object.entries(shopState.cart)
    .filter(([, qty]) => qty > 0)
    .map(([id, qty]) => ({ ...SHOP_PRODUCTS[id], qty, lineTotal: SHOP_PRODUCTS[id].price * qty }));
}

function shopCount() { return shopItems().reduce((sum, item) => sum + item.qty, 0); }
function shopTotal() { return shopItems().reduce((sum, item) => sum + item.lineTotal, 0); }
function shopAmounts() {
  const original = shopTotal();
  const total = shopState.discount ? Math.round(original * 0.88) : original;
  return { original, total, discount: original - total };
}
function renderShopDiscount() {
  const amounts = shopAmounts();
  if (shopPayTotalEl) shopPayTotalEl.textContent = `NT$${amounts.total}`;
  if (shopDiscountLine) shopDiscountLine.hidden = amounts.discount <= 0;
  if (shopDiscountValue) shopDiscountValue.textContent = `-NT$${amounts.discount}`;
}

function productArtSvg(type, color) {
  const dark = '#1a3025';
  const cream = '#f5edda';
  switch (type) {
    case 'bottle':
      return `<svg viewBox="0 0 100 120" aria-hidden="true"><rect x="43" y="6" width="14" height="12" rx="3" fill="${dark}"/><path d="M36 18h28v14l8 12v58c0 8-5 12-12 12H40c-8 0-13-4-13-12V44l9-12V18Z" fill="${color}"/><rect x="31" y="54" width="38" height="34" rx="3" fill="${cream}"/><rect x="37" y="61" width="24" height="3" rx="2" fill="${dark}" opacity=".7"/><rect x="37" y="70" width="17" height="2" rx="1" fill="${dark}" opacity=".45"/><path d="M37 29h26" stroke="${dark}" stroke-width="2" opacity=".25"/></svg>`;
    case 'can':
      return `<svg viewBox="0 0 100 120" aria-hidden="true"><ellipse cx="50" cy="24" rx="25" ry="7" fill="${dark}"/><path d="M25 24v66c0 8 11 13 25 13s25-5 25-13V24" fill="${color}"/><ellipse cx="50" cy="24" rx="25" ry="7" fill="${color}"/><rect x="27" y="47" width="46" height="25" fill="${cream}" opacity=".94"/><path d="M35 57h30M35 63h21" stroke="${dark}" stroke-width="3" stroke-linecap="round" opacity=".7"/><path d="M35 90c10 5 20 5 30 0" stroke="${cream}" stroke-width="2" fill="none" opacity=".35"/></svg>`;
    case 'bag':
      return `<svg viewBox="0 0 100 120" aria-hidden="true"><path d="M22 31h56l7 74H15l7-74Z" fill="${color}"/><path d="M22 31h56l-2 10H24l-2-10Z" fill="${dark}" opacity=".22"/><path d="M30 31V22l8-7 12 8 12-8 8 7v9" fill="none" stroke="${dark}" stroke-width="4" stroke-linejoin="round"/><ellipse cx="50" cy="67" rx="24" ry="19" fill="${cream}" opacity=".9"/><path d="M38 65c8-8 16-8 24 0" stroke="${dark}" stroke-width="3" fill="none" opacity=".55"/><circle cx="50" cy="69" r="5" fill="${dark}" opacity=".55"/></svg>`;
    case 'bar':
      return `<svg viewBox="0 0 100 120" aria-hidden="true"><rect x="26" y="17" width="48" height="87" rx="5" fill="${color}" transform="rotate(-5 50 60)"/><rect x="32" y="26" width="36" height="50" rx="2" fill="${cream}" transform="rotate(-5 50 60)"/><path d="M38 40h24M38 50h17M38 60h21" stroke="${dark}" stroke-width="3" stroke-linecap="round" opacity=".55" transform="rotate(-5 50 60)"/><path d="M35 88h32" stroke="${cream}" stroke-width="4" stroke-linecap="round" opacity=".55" transform="rotate(-5 50 60)"/></svg>`;
    case 'egg':
      return `<svg viewBox="0 0 100 120" aria-hidden="true"><ellipse cx="50" cy="66" rx="29" ry="37" fill="${color}"/><ellipse cx="41" cy="51" rx="10" ry="17" fill="${cream}" opacity=".16" transform="rotate(-20 41 51)"/><path d="M33 82c10 8 24 9 34 2" stroke="${cream}" stroke-width="2" fill="none" opacity=".3"/><circle cx="61" cy="83" r="2" fill="${cream}" opacity=".4"/></svg>`;
    case 'rice':
      return `<svg viewBox="0 0 100 120" aria-hidden="true"><path d="M50 13 88 103H12L50 13Z" fill="${cream}"/><path d="M50 13 88 103H12L50 13Z" fill="none" stroke="${dark}" stroke-width="2" opacity=".12"/><rect x="39" y="60" width="22" height="38" rx="2" fill="${dark}" opacity=".85"/><circle cx="39" cy="44" r="3" fill="${color}" opacity=".8"/><circle cx="58" cy="48" r="2" fill="${color}" opacity=".65"/></svg>`;
    case 'chips':
      return `<svg viewBox="0 0 100 120" aria-hidden="true"><path d="M20 24h60l8 22-7 56H17l-6-56 9-22Z" fill="${color}"/><path d="M20 24 12 11l12 3 7-8 9 8 10-8 9 8 10-8 8 8 11-3-7 13H20Z" fill="${cream}" opacity=".9"/><ellipse cx="50" cy="65" rx="22" ry="27" fill="${cream}" opacity=".22" stroke="${cream}" stroke-width="2"/><path d="M35 61c6-9 15-9 21 0-2 12-18 12-21 0Z" fill="#f4d27a"/><path d="M43 74c7-7 14-6 19 3-6 8-14 6-19-3Z" fill="#efc463"/><path d="M56 50c6-4 11-1 12 5-6 4-11 1-12-5Z" fill="#f7df9b"/><circle cx="33" cy="86" r="2" fill="${cream}" opacity=".7"/><circle cx="67" cy="88" r="1.5" fill="${cream}" opacity=".6"/></svg>`;
    case 'crackers':
      return `<svg viewBox="0 0 100 120" aria-hidden="true"><path d="M24 18h52l6 68-8 22H26l-8-22 6-68Z" fill="${color}"/><rect x="30" y="28" width="40" height="46" rx="3" fill="${cream}" opacity=".95"/><g fill="#e6c385" stroke="${dark}" stroke-width="1.4" opacity=".9"><rect x="36" y="36" width="13" height="13" rx="1"/><rect x="51" y="36" width="13" height="13" rx="1"/><rect x="36" y="51" width="13" height="13" rx="1"/><rect x="51" y="51" width="13" height="13" rx="1"/></g><g fill="${cream}" opacity=".8"><circle cx="40" cy="40" r="1"/><circle cx="44" cy="45" r="1"/><circle cx="55" cy="40" r="1"/><circle cx="59" cy="45" r="1"/><circle cx="40" cy="55" r="1"/><circle cx="44" cy="60" r="1"/><circle cx="55" cy="55" r="1"/><circle cx="59" cy="60" r="1"/></g><path d="M32 88h36" stroke="${cream}" stroke-width="3" stroke-linecap="round" opacity=".6"/><path d="M27 102h46" stroke="${cream}" stroke-width="2" opacity=".35"/></svg>`;
    case 'foil':
      return `<svg viewBox="0 0 100 120" aria-hidden="true"><g transform="rotate(-8 50 60)"><path d="M25 25 35 17l15 5 15-5 10 8-3 68-10 7-15-5-15 5-10-7 3-68Z" fill="${color}" stroke="${cream}" stroke-width="2"/><path d="M25 25 35 17l15 5 15-5 10 8" fill="none" stroke="${dark}" stroke-width="3" opacity=".45"/><rect x="32" y="42" width="36" height="38" rx="5" fill="${cream}" opacity=".93"/><circle cx="50" cy="57" r="9" fill="${color}" opacity=".45"/><circle cx="50" cy="57" r="5" fill="none" stroke="${color}" stroke-width="2"/><path d="M41 72h18" stroke="${dark}" stroke-width="2" stroke-linecap="round" opacity=".4"/><path d="M30 100h40" stroke="${cream}" stroke-width="2" opacity=".5"/></g></svg>`;
    case 'pack':
      return `<svg viewBox="0 0 100 120" aria-hidden="true"><path d="M21 33h58l5 60c0 8-6 13-14 13H31c-9 0-15-5-15-13l5-60Z" fill="${color}"/><path d="M21 33h58l1 12H20l1-12Z" fill="${cream}" opacity=".9"/><ellipse cx="50" cy="68" rx="21" ry="15" fill="${cream}" stroke="${dark}" stroke-width="2" opacity=".95"/><path d="M40 68h20" stroke="${color}" stroke-width="3" stroke-linecap="round"/><path d="M48 38c2-7 9-9 14-5-2 7-9 9-14 5Z" fill="${cream}" opacity=".92"/><path d="M29 95h42" stroke="${cream}" stroke-width="2" opacity=".4"/></svg>`;
    case 'lighter':
      return `<svg viewBox="0 0 100 120" aria-hidden="true"><rect x="31" y="38" width="38" height="64" rx="7" fill="${color}"/><rect x="35" y="47" width="30" height="43" rx="3" fill="${cream}" opacity=".15"/><rect x="35" y="25" width="30" height="17" rx="4" fill="#7d8587"/><rect x="40" y="20" width="20" height="8" rx="2" fill="${dark}"/><path d="M58 20c8-10 3-16-4-20-1 8-9 10-9 17 0 5 4 8 8 8 3 0 5-1 5-5Z" fill="#f2a23b" opacity=".9"/><path d="M55 20c3-5 0-8-3-11 0 4-4 6-4 9 0 3 2 4 4 4 2 0 3-1 3-2Z" fill="#ffe0a0"/><path d="M34 108h32" stroke="${dark}" stroke-width="3" opacity=".3"/></svg>`;
    default:
      return `<svg viewBox="0 0 100 120" aria-hidden="true"><rect x="19" y="21" width="62" height="82" rx="8" fill="${color}"/><rect x="26" y="26" width="48" height="54" rx="4" fill="${cream}" opacity=".82"/><ellipse cx="50" cy="53" rx="14" ry="11" fill="${color}" opacity=".4"/><path d="M30 92h40" stroke="${cream}" stroke-width="3" stroke-linecap="round" opacity=".5"/></svg>`;
  }
}

function syncBagBadge() {
  const count = shopCount();
  if (bagCountEl) bagCountEl.textContent = String(count);
  if (shopCartCountEl) shopCartCountEl.textContent = `${count} 件`;
  if (btnBag) btnBag.setAttribute('aria-label', `查看购物袋，共 ${count} 件`);
}

function setShopStage(stage) {
  shopState.stage = stage;
  document.querySelectorAll('.shop-stage').forEach((el) => {
    const active = el.dataset.shopStage === stage;
    el.classList.toggle('is-active', active);
    el.setAttribute('aria-hidden', active ? 'false' : 'true');
  });
}

function renderShopProducts() {
  if (!shopProductsEl) return;
  const category = shopState.category;
  const items = Object.values(SHOP_PRODUCTS).filter((item) => item.category === category);
  shopProductsEl.innerHTML = items.map((item) => {
    const qty = shopState.cart[item.id] || 0;
    return `<article class="shop-product">
      <div class="shop-product-art" style="--product-color:${item.color}">
        ${productArtSvg(item.art, item.color)}
        ${qty ? `<span class="shop-product-qty">${qty}</span>` : ''}
      </div>
      <div class="shop-product-info">
        <div class="shop-product-name">${item.name}</div>
        <div class="shop-product-en">${item.en}</div>
        <div class="shop-product-bottom"><span class="shop-price">NT$${item.price}</span>
          <button class="shop-add" type="button" data-shop-add="${item.id}" aria-label="加入${item.name}">+</button>
        </div>
      </div>
    </article>`;
  }).join('');
}

function renderShopCart() {
  if (!shopCartLinesEl) return;
  const items = shopItems();
  if (!items.length) {
    shopCartLinesEl.innerHTML = '<p class="shop-cart-empty">购物袋还是空的。<br>挑一件深夜补给吧。</p>';
  } else {
    shopCartLinesEl.innerHTML = items.map((item) => `<div class="shop-cart-line">
      <div><div class="shop-cart-line-name">${item.name}</div><div class="shop-cart-line-price">NT$${item.price} × ${item.qty}</div></div>
      <div class="shop-cart-line-total">NT$${item.lineTotal}</div>
      <div class="shop-qty"><button type="button" data-shop-dec="${item.id}" aria-label="减少${item.name}">−</button><span>${item.qty}</span><button type="button" data-shop-inc="${item.id}" aria-label="增加${item.name}">+</button><button type="button" data-shop-del="${item.id}" aria-label="移除${item.name}">×</button></div>
    </div>`).join('');
  }
  if (shopTotalEl) shopTotalEl.textContent = `NT$${shopTotal()}`;
  if (shopCheckoutBtn) shopCheckoutBtn.disabled = items.length === 0;
  syncBagBadge();
}

function renderShopPay() {
  const items = shopItems();
  if (shopPayLinesEl) {
    shopPayLinesEl.innerHTML = items.map((item) => `<div class="shop-pay-line"><span>${item.name}<small> × ${item.qty}</small></span><b>NT$${item.lineTotal}</b></div>`).join('');
  }
  renderShopDiscount();
}

function renderShopAll() {
  renderShopProducts();
  renderShopCart();
  renderShopPay();
}

function setShopCategory(category) {
  if (!SHOP_CATEGORIES[category]) return;
  shopState.category = category;
  document.querySelectorAll('[data-shop-cat]').forEach((el) => {
    const active = el.dataset.shopCat === category;
    el.classList.toggle('is-active', active);
    el.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  renderShopProducts();
}

function addShopItem(id, delta = 1) {
  if (!SHOP_PRODUCTS[id]) return;
  const next = (shopState.cart[id] || 0) + delta;
  if (next <= 0) delete shopState.cart[id];
  else shopState.cart[id] = next;
  renderShopAll();
}

function openShop(category = null, options = {}) {
  if (!state.ready || !state.inside || state.entering || state.exiting || state.photoMode ||
      state.coffeeOpen || state.shopOpen || state.walking) return;
  if (state.modalOpen) closeModal();
  const fallback = WALK_STOPS[state.insideStop]?.category || shopState.category || 'drinks';
  shopState.category = SHOP_CATEGORIES[category] ? category : fallback;
  shopState.open = true;
  state.shopOpen = true;
  state.autoRotate = false;
  syncAutoRotateUI();
  document.body.classList.add('shop-open');
  shopModal?.classList.add('is-open');
  shopModal?.setAttribute('aria-hidden', 'false');
  setShopStage('browse');
  setShopCategory(shopState.category);
  renderShopAll();
  if (options.bag) {
    setTimeout(() => document.getElementById('shop-cart')?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }), 120);
  }
  setTimeout(() => document.getElementById('shop-close')?.focus(), 60);
}

function closeShop() {
  if (!state.shopOpen) return;
  if (shopState.payTimer) {
    clearTimeout(shopState.payTimer);
    shopState.payTimer = null;
  }
  state.shopOpen = false;
  document.body.classList.remove('shop-open');
  shopModal?.classList.remove('is-open');
  shopModal?.setAttribute('aria-hidden', 'true');
  setTimeout(() => document.getElementById('btn-shop')?.focus(), 60);
}

function goShopCheckout() {
  if (!shopCount()) return;
  shopState.method = null;
  shopState.discount = false;
  if (shopDiscountInput) shopDiscountInput.checked = false;
  shopState.stage = 'pay';
  setShopStage('pay');
  renderShopPay();
  if (shopPayBtn) {
    shopPayBtn.disabled = true;
    shopPayBtn.textContent = '确认付款';
  }
  document.querySelectorAll('.shop-pay-method').forEach((el) => el.classList.remove('is-selected'));
  shopQrWrap?.classList.remove('has-qr');
  if (shopQrHint) shopQrHint.textContent = '选择支付方式后显示模拟扫码';
}

function selectShopPay(method) {
  if (!PAY_METHODS[method]) return;
  shopState.method = method;
  document.querySelectorAll('.shop-pay-method').forEach((el) => {
    el.classList.toggle('is-selected', el.dataset.shopPay === method);
  });
  const signature = shopItems().map((i) => `${i.id}:${i.qty}`).join('|');
  const data = PAY_METHODS[method];
  if (shopQrImg) shopQrImg.src = drawPseudoQr(method, `shop-${signature}`);
  shopQrWrap?.classList.add('has-qr');
  if (shopQrHint) shopQrHint.textContent = `${data.name} · 模拟扫码`;
  if (shopPayBtn) shopPayBtn.disabled = false;
}

function buildShopOrder() {
  const items = shopItems();
  const method = PAY_METHODS[shopState.method] || PAY_METHODS.alipay;
  const now = new Date();
  const amounts = shopAmounts();
  return {
    no: 'T7S-' + now.getTime().toString(36).toUpperCase().slice(-6),
    items, originalTotal: amounts.original, discount: amounts.discount,
    total: amounts.total, staff: amounts.discount > 0,
    method, time: now, timeText: coffeeClock(now),
  };
}

function drawShopReceipt(order) {
  const W = 720;
  const lineH = 48;
  const H = 940 + order.items.length * lineH + (order.discount > 0 ? 28 : 0);
  const canvas = document.createElement('canvas');
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');
  const serif = '"PingFang TC", "Noto Sans TC", "Helvetica Neue", sans-serif';
  const mono = '"SFMono-Regular", Menlo, Consolas, monospace';
  ctx.fillStyle = '#fffdf6'; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = '#ef5b2a'; ctx.fillRect(0, 0, W / 3, 8);
  ctx.fillStyle = '#14a46d'; ctx.fillRect(W / 3, 0, W / 3, 8);
  ctx.fillStyle = '#e8323e'; ctx.fillRect((W / 3) * 2, 0, W / 3, 8);
  ctx.textAlign = 'left'; ctx.fillStyle = '#1b2a23';
  ctx.font = `600 30px ${serif}`; ctx.fillText('7-ELEVEN 中山门店', 48, 65);
  ctx.font = `400 13px ${mono}`; ctx.fillStyle = 'rgba(27,42,35,.6)';
  ctx.fillText('SHOPPING RECEIPT / 电子购物明细', 48, 93);
  ctx.fillText('FICTIONAL STORE · DEMO', 48, 113);
  ctx.strokeStyle = 'rgba(27,42,35,.26)'; ctx.setLineDash([3, 5]);
  ctx.beginPath(); ctx.moveTo(48, 140); ctx.lineTo(672, 140); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = '#26382d'; ctx.font = `400 13px ${mono}`;
  ctx.fillText(`DATE  ${order.timeText}`, 48, 174);
  ctx.fillText(`ORDER ${order.no}`, 48, 198);
  ctx.fillText(`ITEMS  ${order.items.reduce((n, i) => n + i.qty, 0)}`, 48, 222);
  ctx.strokeStyle = 'rgba(27,42,35,.26)'; ctx.setLineDash([3, 5]);
  ctx.beginPath(); ctx.moveTo(48, 250); ctx.lineTo(672, 250); ctx.stroke(); ctx.setLineDash([]);
  let y = 294;
  for (const item of order.items) {
    ctx.fillStyle = '#26382d'; ctx.font = `500 20px ${serif}`; ctx.fillText(item.name, 48, y);
    ctx.fillStyle = 'rgba(38,56,45,.5)'; ctx.font = `400 12px ${mono}`; ctx.fillText(`x${item.qty}  NT$${item.price}`, 48, y + 22);
    ctx.textAlign = 'right'; ctx.fillStyle = '#26382d'; ctx.font = `400 14px ${mono}`; ctx.fillText(`NT$${item.lineTotal}`, 672, y);
    ctx.textAlign = 'left';
    y += lineH;
  }
  ctx.strokeStyle = 'rgba(27,42,35,.2)'; ctx.beginPath(); ctx.moveTo(48, y + 2); ctx.lineTo(672, y + 2); ctx.stroke(); y += 40;
  ctx.fillStyle = '#26382d'; ctx.font = `400 14px ${mono}`;
  ctx.textAlign = 'left'; ctx.fillText('SUBTOTAL', 48, y); ctx.textAlign = 'right'; ctx.fillText(`NT$${order.originalTotal ?? order.total}`, 672, y); y += 28;
  ctx.textAlign = 'left';
  if (order.discount > 0) {
    ctx.fillStyle = '#9c3c2f'; ctx.fillText('STAFF 8.8', 48, y); ctx.textAlign = 'right'; ctx.fillText(`-NT$${order.discount}`, 672, y);
    ctx.textAlign = 'left'; ctx.fillStyle = '#26382d'; y += 28;
  }
  ctx.fillText('TAX', 48, y); ctx.textAlign = 'right'; ctx.fillText('INCLUDED', 672, y); y += 38;
  ctx.textAlign = 'left'; ctx.font = `600 24px ${serif}`; ctx.fillText('TOTAL', 48, y); ctx.textAlign = 'right'; ctx.font = `500 34px ${serif}`; ctx.fillText(`NT$${order.total}`, 672, y); y += 42;
  ctx.textAlign = 'left'; ctx.fillStyle = '#26382d'; ctx.font = `400 13px ${mono}`;
  ctx.fillText(`PAYMENT  ${order.method.name.toUpperCase()} / ${order.method.zh}`, 48, y); y += 36;
  ctx.strokeStyle = 'rgba(27,42,35,.26)'; ctx.setLineDash([3, 5]); ctx.beginPath(); ctx.moveTo(48, y); ctx.lineTo(672, y); ctx.stroke(); ctx.setLineDash([]); y += 32;
  ctx.strokeStyle = '#b23e37'; ctx.lineWidth = 2; ctx.strokeRect(48, y, 624, 74);
  ctx.fillStyle = '#b23e37'; ctx.font = `600 17px ${mono}`; ctx.textAlign = 'center';
  ctx.fillText('SIMULATED TRANSACTION', 360, y + 31); ctx.font = `400 13px ${mono}`; ctx.fillText('非实际交易 · 仅供互动展示', 360, y + 56);
  ctx.textAlign = 'left'; ctx.lineWidth = 1; y += 112;
  let seed = 0;
  for (let i = 0; i < order.no.length; i++) seed = (seed * 33 + order.no.charCodeAt(i)) >>> 0;
  const rng = mulberry32(seed || 7);
  let bx = 70;
  for (let i = 0; i < 46; i++) { const w = 2 + Math.floor(rng() * 5); ctx.fillStyle = '#1b2a23'; ctx.fillRect(bx, y, w, 50); bx += w + 3 + Math.floor(rng() * 4); }
  ctx.fillStyle = 'rgba(27,42,35,.52)'; ctx.font = `400 11px ${mono}`; ctx.textAlign = 'center'; ctx.fillText(`*${order.no}*`, 360, y + 76);
  ctx.font = `400 12px ${mono}`; ctx.fillText('THANK YOU · 谢谢光临', 360, y + 116);
  ctx.font = `400 10px ${mono}`; ctx.fillStyle = 'rgba(27,42,35,.34)'; ctx.fillText('7-ELEVEN 中山门店 · FICTIONAL STORE', 360, y + 144);
  ctx.textAlign = 'left';
  ctx.fillStyle = '#ef5b2a'; ctx.fillRect(48, H - 58, 202, 4);
  ctx.fillStyle = '#14a46d'; ctx.fillRect(250, H - 58, 202, 4);
  ctx.fillStyle = '#e8323e'; ctx.fillRect(452, H - 58, 220, 4);
  return canvas;
}

function finishShopPayment() {
  shopState.order = buildShopOrder();
  const receipt = drawShopReceipt(shopState.order);
  shopState.receiptCanvas = receipt;
  if (shopReceiptImg) shopReceiptImg.src = receipt.toDataURL('image/png');
  setShopStage('success');
  shopState.cart = {};
  renderShopAll();
  if (shopPayBtn) { shopPayBtn.textContent = '确认付款'; shopPayBtn.disabled = false; }
}

function confirmShopPayment() {
  if (!shopState.method || !shopPayBtn) return;
  shopPayBtn.disabled = true;
  shopPayBtn.textContent = '处理中…';
  if (shopState.payTimer) clearTimeout(shopState.payTimer);
  shopState.payTimer = setTimeout(() => {
    shopState.payTimer = null;
    if (!state.shopOpen) return;
    finishShopPayment();
  }, 1250);
}

if (btnShop) btnShop.addEventListener('click', () => openShop());
if (btnBag) btnBag.addEventListener('click', () => openShop(null, { bag: true }));
document.getElementById('shop-close')?.addEventListener('click', closeShop);
document.querySelector('.shop-backdrop')?.addEventListener('click', closeShop);
document.querySelectorAll('[data-shop-cat]').forEach((el) => {
  el.addEventListener('click', () => setShopCategory(el.dataset.shopCat));
});
shopProductsEl?.addEventListener('click', (e) => {
  const add = e.target.closest('[data-shop-add]');
  if (add) addShopItem(add.dataset.shopAdd, 1);
});
shopCartLinesEl?.addEventListener('click', (e) => {
  const inc = e.target.closest('[data-shop-inc]');
  const dec = e.target.closest('[data-shop-dec]');
  const del = e.target.closest('[data-shop-del]');
  if (inc) addShopItem(inc.dataset.shopInc, 1);
  else if (dec) addShopItem(dec.dataset.shopDec, -1);
  else if (del) addShopItem(del.dataset.shopDel, -99);
});
shopCheckoutBtn?.addEventListener('click', goShopCheckout);
document.querySelectorAll('.shop-pay-method').forEach((el) => {
  el.addEventListener('click', () => selectShopPay(el.dataset.shopPay));
});
shopPayBtn?.addEventListener('click', confirmShopPayment);
shopDiscountInput?.addEventListener('change', (e) => {
  shopState.discount = e.target.checked;
  renderShopDiscount();
});
document.getElementById('shop-back')?.addEventListener('click', () => {
  setShopStage('browse');
  renderShopAll();
});
document.getElementById('shop-download')?.addEventListener('click', () => {
  downloadCanvas(shopState.receiptCanvas, `7-eleven-shopping-receipt-${shopState.order?.no || 'demo'}.png`);
});
document.getElementById('shop-again')?.addEventListener('click', () => {
  shopState.method = null;
  setShopStage('browse');
  renderShopAll();
});
document.getElementById('shop-done')?.addEventListener('click', () => {
  closeShop();
  showToast('NIGHT SHOP · 完成');
});

function updateWalkMarkers() {
  routeBtns.forEach((btn) => {
    btn.classList.toggle('is-current', state.insideStop === btn.dataset.routeStop);
  });
  if (!walkLayer) return;
  const visible = state.ready && state.inside && !state.entering && !state.exiting &&
    !state.walking && !state.photoMode && !state.coffeeOpen && !state.shopOpen && !CAPTURE;
  if (!visible) {
    walkLayer.classList.remove('is-visible');
    return;
  }
  walkLayer.classList.add('is-visible');
  const forward = new THREE.Vector3();
  camera.getWorldDirection(forward);
  const projected = new THREE.Vector3();
  for (const el of walkMarkerEls) {
    const stop = WALK_STOPS[el.dataset.stop];
    if (!stop) { el.hidden = true; continue; }
    projected.copy(stop.anchor).project(camera);
    const toAnchor = stop.anchor.clone().sub(camera.position).normalize();
    const inFront = forward.dot(toAnchor) > 0.12;
    const x = (projected.x * 0.5 + 0.5) * innerWidth;
    const y = (-projected.y * 0.5 + 0.5) * innerHeight;
    const inBounds = x > 24 && x < innerWidth - 24 && y > 90 && y < innerHeight - 140;
    const onScreen = inFront && projected.z > -1 && projected.z < 1 && inBounds;
    el.hidden = !onScreen;
    if (onScreen) {
      el.style.left = `${x.toFixed(1)}px`;
      el.style.top = `${y.toFixed(1)}px`;
      el.classList.toggle('is-current', state.insideStop === el.dataset.stop);
    }
  }
}

function walkToStop(id, options = {}) {
  if (!state.inside || state.entering || state.exiting || state.walking ||
      state.photoMode || state.coffeeOpen || state.shopOpen) return;
  const stop = WALK_STOPS[id];
  if (!stop) return;
  if (state.insideStop === id && !state.tour) {
    if (options.openShop && stop.category) openShop(stop.category);
    else if (id === 'entrance') resetInteriorLook();
    return;
  }
  if (state.tour) return;
  const fromPos = camera.position.clone();
  const dir = new THREE.Vector3();
  camera.getWorldDirection(dir);
  const fromTarget = fromPos.clone().addScaledVector(dir, 4);
  const distance = fromPos.distanceTo(stop.pos);
  state.walking = true;
  document.body.classList.add('walking');
  state.autoRotate = false;
  syncAutoRotateUI();
  state.tour = {
    start: performance.now(),
    duration: clamp(900 + distance * 80, 1000, 1600),
    fromPos,
    toPos: stop.pos.clone(),
    fromTarget,
    toTarget: stop.target.clone(),
    fromFov: camera.fov,
    toFov: 50,
    onDone: () => {
      state.walking = false;
      state.insideStop = id;
      document.body.classList.remove('walking');
      orbit.target.copy(stop.target);
      setInteriorLookFrom(stop.pos, stop.target);
      updateWalkMarkers();
      if (options.openShop && stop.category) {
        setTimeout(() => openShop(stop.category), 180);
      } else {
        showToast(stop.en);
      }
    },
  };
}

walkMarkerEls.forEach((el) => {
  el.addEventListener('click', () => {
    const stop = WALK_STOPS[el.dataset.stop];
    if (!stop) return;
    if (state.insideStop === el.dataset.stop && !state.walking) {
      if (stop.category) openShop(stop.category);
      else resetInteriorLook();
      return;
    }
    walkToStop(el.dataset.stop, { openShop: Boolean(stop.category) });
  });
});

routeBtns.forEach((el) => {
  el.addEventListener('click', () => {
    const stop = WALK_STOPS[el.dataset.routeStop];
    if (!stop) return;
    if (state.insideStop === el.dataset.routeStop && !state.walking) {
      if (stop.category) openShop(stop.category);
      else resetInteriorLook();
      return;
    }
    walkToStop(el.dataset.routeStop, { openShop: Boolean(stop.category) });
  });
});

if (btnEnter) btnEnter.addEventListener('click', () => {
  if (state.inside) exitStore();
  else enterStore();
});

let doorClickStart = null;
canvas.addEventListener('pointerdown', (e) => {
  if (state.inside || state.entering || state.exiting || state.photoMode || state.coffeeOpen || state.shopOpen || state.walking) return;
  if (e.pointerType === 'mouse' && e.button !== 0) return;
  doorClickStart = { x: e.clientX, y: e.clientY, id: e.pointerId };
});
canvas.addEventListener('pointerup', (e) => {
  if (!doorClickStart || e.pointerId !== doorClickStart.id) return;
  const start = doorClickStart;
  doorClickStart = null;
  if (state.inside || state.entering || state.exiting || state.photoMode || state.coffeeOpen || state.shopOpen || state.walking || !modelRoot) return;
  if (Math.hypot(e.clientX - start.x, e.clientY - start.y) > 8) return;
  const ndc = new THREE.Vector2(
    (e.clientX / innerWidth) * 2 - 1,
    -(e.clientY / innerHeight) * 2 + 1,
  );
  const rc = new THREE.Raycaster();
  rc.setFromCamera(ndc, camera);
  const hit = rc.intersectObject(modelRoot, true)[0];
  if (hit && hit.point.x > -0.95 && hit.point.x < 1.75 &&
      hit.point.y > 0.05 && hit.point.y < 3.45 &&
      hit.point.z > 4.25 && hit.point.z < 5.15) {
    enterStore();
  }
});

canvas.addEventListener('pointerdown', (e) => {
  if (!state.inside || state.entering || state.exiting || state.coffeeOpen || state.shopOpen || state.walking) return;
  if (e.pointerType === 'mouse' && e.button !== 0) return;
  state.look.dragging = true;
  state.look.lastX = e.clientX;
  state.look.lastY = e.clientY;
  state.hasInteracted = true;
  canvas.setPointerCapture?.(e.pointerId);
  e.preventDefault();
});
canvas.addEventListener('pointermove', (e) => {
  if (!state.look.dragging || !state.inside || state.entering || state.exiting) return;
  const dx = e.clientX - state.look.lastX;
  const dy = e.clientY - state.look.lastY;
  state.look.lastX = e.clientX;
  state.look.lastY = e.clientY;
  state.look.yaw += dx * 0.0032;
  state.look.pitch = clamp(state.look.pitch + dy * 0.0028, -0.58, 0.58);
  applyInteriorLook();
  e.preventDefault();
});
function endInteriorLook(e) {
  if (!state.look.dragging) return;
  state.look.dragging = false;
  canvas.releasePointerCapture?.(e.pointerId);
}
canvas.addEventListener('pointerup', endInteriorLook);
canvas.addEventListener('pointercancel', endInteriorLook);

orbit.addEventListener('start', () => {
  if (state.intro) skipIntro();
  if (state.autoRotate) {
    state.autoRotate = false;
    orbit.autoRotate = false;
    syncAutoRotateUI();
  }
  state.hasInteracted = true;
  hideHintSoon();
});

canvas.addEventListener('dblclick', () => resetView(true));
addEventListener('pointerdown', (e) => {
  if (!e.target.closest('.ui')) {
    // Any direct interaction with the scene skips the entry move.
    if (state.intro) skipIntro();
  }
}, { passive: true });

// ---------------------------------------------------------------------------
// Mode switching and continuous palette blending
// ---------------------------------------------------------------------------
const current = {
  skyTop: color(MODE_PARAMS.night.skyTop),
  skyHorizon: color(MODE_PARAMS.night.skyHorizon),
  skyGround: color(MODE_PARAMS.night.skyGround),
  sunColor: color(MODE_PARAMS.night.sunColor),
  sunDir: MODE_PARAMS.night.sunDir.clone(),
  skyGlow: color(MODE_PARAMS.night.skyGlow),
  cloudColor: color(MODE_PARAMS.night.cloudColor),
  fogColor: color(MODE_PARAMS.night.fogColor),
  hemiSky: color(MODE_PARAMS.night.hemiSky),
  hemiGround: color(MODE_PARAMS.night.hemiGround),
  ambientColor: color(MODE_PARAMS.night.ambientColor),
  sunI: MODE_PARAMS.night.sunI,
  glowStrength: MODE_PARAMS.night.glowStrength,
  cloudiness: MODE_PARAMS.night.cloudiness,
  fogNear: MODE_PARAMS.night.fogNear,
  fogFar: MODE_PARAMS.night.fogFar,
  hemiI: MODE_PARAMS.night.hemiI,
  ambientI: MODE_PARAMS.night.ambientI,
  exposure: MODE_PARAMS.night.exposure,
  bloom: MODE_PARAMS.night.bloom,
  bloomThreshold: MODE_PARAMS.night.bloomThreshold,
  sign: MODE_PARAMS.night.sign,
  led: MODE_PARAMS.night.led,
  fridge: MODE_PARAMS.night.fridge,
  warm: MODE_PARAMS.night.warm,
  street: MODE_PARAMS.night.street,
  neon: MODE_PARAMS.night.neon,
  screen: MODE_PARAMS.night.screen,
  decal: MODE_PARAMS.night.decal,
  star: MODE_PARAMS.night.star,
  moon: MODE_PARAMS.night.moon,
  spill: MODE_PARAMS.night.spill,
  glassReflect: MODE_PARAMS.night.glassReflect,
  interior: MODE_PARAMS.night.interior,
  streetLight: MODE_PARAMS.night.streetLight,
  canopy: MODE_PARAMS.night.canopy,
  pylonLight: MODE_PARAMS.night.pylonLight,
};
const target = { ...current };
for (const key of ['skyTop', 'skyHorizon', 'skyGround', 'sunColor', 'skyGlow', 'cloudColor', 'fogColor', 'hemiSky', 'hemiGround', 'ambientColor']) {
  target[key] = current[key].clone();
}
const vectorTarget = current.sunDir.clone();

const COLOR_KEYS = new Set([
  'skyTop', 'skyHorizon', 'skyGround', 'sunColor', 'skyGlow',
  'cloudColor', 'fogColor', 'hemiSky', 'hemiGround', 'ambientColor',
]);
function copyModeParams(mode) {
  const p = MODE_PARAMS[mode];
  for (const k of Object.keys(p)) {
    if (COLOR_KEYS.has(k)) target[k].set(p[k]);
    else if (p[k] instanceof THREE.Vector3 || k === 'sunDir') vectorTarget.copy(p[k]);
    else if (typeof p[k] === 'number') target[k] = p[k];
  }
}

function timeLabel(hour) {
  if (hour >= 24) return '24:00';
  const total = Math.round(clamp(hour, 0, 24) * 60);
  return `${pad2(Math.floor(total / 60) % 24)}:${pad2(total % 60)}`;
}

function lightingParamForHour(hour) {
  if (hour >= 8 && hour < 16) return 0;
  if (hour >= 16 && hour < 18.5) return 0.5 * (hour - 16) / 2.5;
  if (hour >= 18.5 && hour < 20.5) return 0.5 + 0.5 * (hour - 18.5) / 2;
  if (hour >= 20.5 || hour < 4.5) return 1;
  if (hour >= 4.5 && hour < 6.5) return 1 - 0.5 * (hour - 4.5) / 2;
  if (hour >= 6.5 && hour < 8) return 0.5 - 0.5 * (hour - 6.5) / 1.5;
  return 0;
}

function modeForHour(hour) {
  if (hour >= 4.5 && hour < 8) return 'dawn';
  if (hour >= 8 && hour < 16.5) return 'day';
  if (hour >= 16.5 && hour < 20.5) return 'dusk';
  return 'night';
}

function setHour(hour, options = {}) {
  const h = clamp(hour, 0, 24);
  state.hour = h;
  const tt = lightingParamForHour(h);
  state.time = tt;
  const firstHalf = tt <= 0.5;
  const a = firstHalf ? 'day' : 'dusk';
  const b = firstHalf ? 'dusk' : 'night';
  const s = firstHalf ? tt / 0.5 : (tt - 0.5) / 0.5;
  const A = MODE_PARAMS[a];
  const B = MODE_PARAMS[b];
  for (const k of Object.keys(A)) {
    if (COLOR_KEYS.has(k)) {
      target[k].copy(color(A[k])).lerp(color(B[k]), s);
    } else if (k === 'sunDir') {
      vectorTarget.copy(A[k]).lerp(B[k], s).normalize();
    } else if (typeof A[k] === 'number') {
      target[k] = lerp(A[k], B[k], s);
    }
  }
  const timeField = document.getElementById('time-range');
  if (timeField) {
    timeField.value = String(Math.round(h * 60));
    timeField.setAttribute('aria-valuetext', timeLabel(h));
  }
  const timeNow = document.getElementById('time-now');
  if (timeNow) timeNow.textContent = timeLabel(h);
  const mode = modeForHour(h);
  const modeChanged = mode !== state.mode || options.forceMode;
  if (modeChanged) {
    state.mode = mode;
    document.body.dataset.mode = mode;
    document.querySelectorAll('.mode-btn').forEach((btn) => {
      const active = btn.dataset.mode === mode;
      btn.classList.toggle('is-active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    const num = document.getElementById('mode-number');
    if (num) num.textContent = mode === 'day' || mode === 'night' ? MODE_INDEX[mode] : '··';
    updateModeCopy(mode, Boolean(options.instant));
    if (options.toast) showToast(MODE_COPY[mode].toast);
  }
  if (options.instant) {
    for (const k of Object.keys(target)) {
      if (typeof target[k] === 'number') current[k] = target[k];
      else if (target[k]?.isColor) current[k].copy(target[k]);
    }
    current.sunDir.copy(vectorTarget);
    applyEnvironment(mode);
    applyCurrentToScene(0, 1);
  } else if (modeChanged) {
    applyEnvironment(mode);
  }
  hideHintSoon();
}

function setMode(mode, options = {}) {
  if (!MODE_PARAMS[mode]) return;
  const hour = mode === 'night' ? 22 : 12;
  setHour(hour, { ...options, forceMode: true, toast: options.toast !== false });
}

// Kept as a normalized API for older capture/test callers: 0 = day, .5 = dusk, 1 = night.
function setTime(t, options = {}) {
  const tt = clamp(t, 0, 1);
  const hour = tt <= 0.5 ? 16 + (tt / 0.5) * 2.5 : 18.5 + ((tt - 0.5) / 0.5) * 2;
  setHour(hour, options);
}

function updateModeCopy(mode, instant = false) {
  const capt = document.querySelector('.caption');
  const kicker = document.getElementById('caption-kicker');
  const title = document.getElementById('caption-title');
  const copy = document.getElementById('caption-copy');
  if (!capt || !kicker || !title || !copy) return;
  const apply = () => {
    kicker.textContent = MODE_COPY[mode].kicker;
    title.textContent = MODE_COPY[mode].title;
    copy.textContent = MODE_COPY[mode].copy;
    capt.classList.remove('is-switching');
  };
  if (instant) { apply(); return; }
  capt.classList.add('is-switching');
  setTimeout(apply, 320);
}

function applyEnvironment(mode) {
  const envMode = mode === 'dawn' ? 'dusk' : mode;
  const tex = envTextures[envMode];
  if (!tex) return;
  scene.environment = tex;
  scene.environmentIntensity = envMode === 'day' ? 0.45 : envMode === 'dusk' ? 0.56 : 0.70;
}

function showToast(text) {
  const toast = document.getElementById('mode-toast');
  if (!toast) return;
  const label = document.getElementById('toast-text');
  if (label && text) label.textContent = text;
  toast.classList.add('is-visible');
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => toast.classList.remove('is-visible'), 1500);
}

function syncAutoRotateUI() {
  const btn = document.getElementById('btn-rotate');
  if (!btn) return;
  btn.classList.toggle('is-on', state.autoRotate);
  btn.setAttribute('aria-pressed', state.autoRotate ? 'true' : 'false');
  orbit.autoRotate = state.autoRotate && state.ready && !state.intro && !state.tween && !state.modalOpen && !CAPTURE && !state.inside && !state.entering && !state.exiting && !state.tour && !state.photoMode && !state.coffeeOpen && !state.shopOpen && !state.walking;
}

// ---------------------------------------------------------------------------
// Apply blended parameters to lights/materials
// ---------------------------------------------------------------------------
const materialGroups = {
  sign: [], led: [], fridge: [], warm: [], street: [], neon: [], screen: [], decal: [],
};

function initMaterialGroups() {
  for (const list of Object.values(materialGroups)) list.length = 0;
  for (const item of EMISSIVE_MATERIALS) {
    if (materialGroups[item.group]) materialGroups[item.group].push(item);
  }
}
let elapsed = 0;

function applyCurrentToScene(dt, factor = null) {
  const f = factor ?? (1 - Math.exp(-3.2 * Math.max(dt, 0.0001)));
  // Continuous values.
  for (const k of Object.keys(target)) {
    if (typeof current[k] === 'number') {
      current[k] = damp(current[k], target[k], 3.2, dt);
    } else if (current[k]?.isColor) {
      current[k].lerp(target[k], f);
    }
  }
  current.sunDir.lerp(vectorTarget, f).normalize();

  renderer.toneMappingExposure = current.exposure;
  bloomPass.strength = current.bloom;
  bloomPass.threshold = current.bloomThreshold;

  // Sky.
  skyUniforms.topColor.value.copy(current.skyTop);
  skyUniforms.horizonColor.value.copy(current.skyHorizon);
  skyUniforms.groundColor.value.copy(current.skyGround);
  skyUniforms.glowColor.value.copy(current.skyGlow);
  skyUniforms.sunColor.value.copy(current.sunColor);
  skyUniforms.cloudColor.value.copy(current.cloudColor);
  skyUniforms.sunDir.value.copy(current.sunDir);
  skyUniforms.sunI.value = current.sunI;
  skyUniforms.glowStrength.value = current.glowStrength;
  skyUniforms.cloudiness.value = current.cloudiness;
  skyUniforms.time.value = elapsed;

  // Lighting.
  hemi.color.copy(current.hemiSky);
  hemi.groundColor.copy(current.hemiGround);
  hemi.intensity = current.hemiI;
  ambient.color.copy(current.ambientColor);
  ambient.intensity = current.ambientI;
  keyLight.color.copy(current.sunColor);
  keyLight.intensity = current.sunI;
  keyLight.position.copy(current.sunDir).multiplyScalar(28).add(new THREE.Vector3(0, 0, 0));
  keyLight.target.position.set(1.0, 0.4, 0.3);

  interiorLights.forEach((l, i) => {
    l.intensity = [14, 11, 14, 10][i] * current.interior;
  });
  fridgeLight.intensity = 4.4 * current.interior;
  canopyLights.forEach((l) => { l.intensity = 13 * current.canopy; });
  streetLamp.intensity = 150 * current.streetLight;
  pedLamp.intensity = 72 * current.streetLight;
  displaySpots.forEach((l) => { l.intensity = (l.userData.power ?? 14) * current.interior; });
  pylonLight.intensity = 1.2 * current.pylonLight;
  spillLight.intensity = 6.5 * Math.max(current.spill, 0.05);

  // Fog.
  if (scene.fog) {
    scene.fog.color.copy(current.fogColor);
    scene.fog.near = current.fogNear;
    scene.fog.far = current.fogFar;
    scene.fog.near = Math.min(scene.fog.near, scene.fog.far - 5);
  }
  scene.background.copy(current.fogColor);

  // Emissive material groups. Group values are relative multipliers; preserve
  // the authored strength exported from Blender.
  for (const [group, items] of Object.entries(materialGroups)) {
    const factorValue = current[group] ?? 0;
    for (const item of items) {
      // The main fascia returns to its original night brightness; the taller
      // pylon lightbox stays on the quieter level and avoids a hotspot.
      const materialScale = item.name === 'M_Sign_Pylon' ? 0.72 : 1;
      item.mat.emissiveIntensity = item.base * factorValue * materialScale;
    }
  }

  // Stars / moon.
  if (STARS.mat) {
    STARS.mat.uniforms.uOpacity.value = current.star;
    STARS.mat.uniforms.uTime.value = elapsed;
  }
  moon.material.opacity = current.moon;

  for (const item of LIGHT_POOL_MATS) {
    item.mat.opacity = (item.kind === 'street' ? 0.22 : 0.25) * (item.kind === 'street' ? (0.35 + current.streetLight * 0.65) : (0.4 + current.spill * 0.6));
  }
  pedPoolMat.opacity = 0.22 * current.streetLight;
  glassReflectionMat.opacity = current.glassReflect;
}

let wasViewKey = initialViewKey;
function syncCameraOnResize() {
  const view = getView();
  const viewKey = getViewKey();
  // Keep whatever orbit the viewer is on; only reframe automatically when the
  // aspect ratio crosses a composition breakpoint before the user touches it.
  if (!state.hasInteracted && !state.intro && !state.tween) {
    camera.fov = view.fov;
    if (viewKey !== wasViewKey) {
      camera.position.copy(view.pos);
      orbit.target.copy(view.target);
      orbit.update();
    }
    camera.updateProjectionMatrix();
  }
  wasViewKey = viewKey;
}

addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, IS_TOUCH ? 1.5 : 2));
  renderer.setSize(innerWidth, innerHeight);
  composer.setPixelRatio(Math.min(devicePixelRatio || 1, IS_TOUCH ? 1.5 : 2));
  composer.setSize(innerWidth, innerHeight);
  bloomPass.setSize(innerWidth, innerHeight);
  if (STARS.mat) STARS.mat.uniforms.uPixelRatio.value = Math.min(devicePixelRatio || 1, IS_TOUCH ? 1.5 : 2);
  syncCameraOnResize();
});

// ---------------------------------------------------------------------------
// UI wiring
// ---------------------------------------------------------------------------
document.querySelectorAll('.mode-btn').forEach((btn) => {
  btn.addEventListener('click', () => setMode(btn.dataset.mode));
});
document.getElementById('time-range')?.addEventListener('input', (e) => {
  setHour(Number(e.target.value) / 60);
});

const btnRotate = document.getElementById('btn-rotate');
btnRotate?.addEventListener('click', () => {
  if (state.inside) { showToast('INTERIOR LOOK / 店内环顾'); return; }
  state.autoRotate = !state.autoRotate;
  if (state.autoRotate && state.intro) skipIntro();
  syncAutoRotateUI();
  showToast(state.autoRotate ? 'AUTO ORBIT ON' : 'AUTO ORBIT PAUSED');
});
document.getElementById('btn-reset')?.addEventListener('click', () => {
  resetView(true);
  showToast('VIEW RESET');
});
document.getElementById('btn-info')?.addEventListener('click', openModal);
document.getElementById('info-close')?.addEventListener('click', closeModal);
document.querySelector('.modal-backdrop')?.addEventListener('click', closeModal);

function openModal() {
  const modal = document.getElementById('info-modal');
  if (!modal) return;
  state.modalOpen = true;
  orbit.autoRotate = false;
  modal.classList.add('is-open');
  modal.setAttribute('aria-hidden', 'false');
  setTimeout(() => document.getElementById('info-close')?.focus(), 80);
}
function closeModal() {
  const modal = document.getElementById('info-modal');
  if (!modal) return;
  state.modalOpen = false;
  modal.classList.remove('is-open');
  modal.setAttribute('aria-hidden', 'true');
  document.getElementById('btn-info')?.focus();
  syncAutoRotateUI();
}

addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if (state.coffeeOpen) closeCoffee();
    else if (state.shopOpen) closeShop();
    else if (state.photoMode) exitPhotoMode();
    else if (state.modalOpen) closeModal();
    else if (state.inside) exitStore();
    return;
  }
  if (state.coffeeOpen || state.shopOpen) return;
  if (state.modalOpen) return;
  if (e.key.toLowerCase() === 'c') {
    if (state.inside) openCoffee();
    return;
  }
  if (e.key.toLowerCase() === 's') {
    if (state.inside) openShop();
    return;
  }
  if (e.key.toLowerCase() === 'b') {
    if (state.inside) openShop(null, { bag: true });
    return;
  }
  if (e.key.toLowerCase() === 'p') {
    if (state.photoMode) exitPhotoMode();
    else enterPhotoMode();
  }
  if (state.photoMode) return;
  if (e.key === '1') setMode('day');
  if (e.key === '2') setMode('night');
  if (e.key.toLowerCase() === 'e') {
    if (state.inside) exitStore();
    else enterStore();
  }
  if (e.key.toLowerCase() === 'r') { resetView(true); showToast('VIEW RESET'); }
  if (e.key === 'i' || e.key === 'I') openModal();
  if (e.code === 'Space') {
    e.preventDefault();
    if (state.inside) { showToast('INTERIOR LOOK / 店内环顾'); return; }
    state.autoRotate = !state.autoRotate;
    syncAutoRotateUI();
    showToast(state.autoRotate ? 'AUTO ORBIT ON' : 'AUTO ORBIT PAUSED');
  }
});

let hintTimer = null;
function hideHintSoon() {
  const hint = document.getElementById('hint');
  if (!hint) return;
  clearTimeout(hintTimer);
  hintTimer = setTimeout(() => { hint.style.opacity = '0'; }, 5500);
}
setTimeout(hideHintSoon, 9000);

// ---------------------------------------------------------------------------
// Render loop
// ---------------------------------------------------------------------------
const clock = new THREE.Clock();
let frameCount = 0;
let fpsTime = 0;
let frameAccum = 0;
let fps = 0;

function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.05);
  const now = performance.now();
  elapsed += dt;
  handleTween(now);
  updateInteriorTour(now);
  updateDoor(dt, now);
  updateWalkMarkers();
  applyCurrentToScene(dt);

  const canOrbit = !state.inside && !state.entering && !state.exiting && !state.tour;
  if (state.ready && !state.intro) {
    orbit.autoRotate = state.autoRotate && !CAPTURE && !state.dragging && !state.modalOpen && !state.tween && canOrbit;
    if (canOrbit) orbit.update();
  } else if (canOrbit) {
    orbit.update();
  }

  composer.render();
  frameCount++;
  state.frame = frameCount;
  if (frameCount % 30 === 0 && !state.captureReady && state.ready) {
    state.captureReady = true;
    window.__SEVEN_CAPTURE_READY__ = true;
  }
}
animate();

// For deterministic screenshots and lightweight scene QA.
window.__SEVEN__ = {
  get ready() { return state.ready; },
  get mode() { return state.mode; },
  setMode: (m, instant = true) => { setMode(m, { instant, toast: false }); },
  resetView,
  freeze() { state.autoRotate = false; syncAutoRotateUI(); },
  tune(values = {}) {
    for (const [k, v] of Object.entries(values)) {
      if (typeof v === 'number' && typeof target[k] === 'number') {
        target[k] = v;
        current[k] = v;
      }
    }
    applyCurrentToScene(0, 1);
  },
  setView(pos, targetPos, fov) {
    camera.position.set(pos[0], pos[1], pos[2]);
    orbit.target.set(targetPos[0], targetPos[1], targetPos[2]);
    if (fov) { camera.fov = fov; camera.updateProjectionMatrix(); }
    orbit.update();
  },
  enterStore,
  exitStore,
  setTime,
  setHour,
  enterPhotoMode,
  exitPhotoMode,
  scene, camera, renderer, composer, orbit, materialGroups,
  stats() {
    return {
      mode: state.mode,
      calls: renderer.info.render.calls,
      triangles: renderer.info.render.triangles,
      fps,
      dpr: renderer.getPixelRatio(),
    };
  },
};

// Apply the current local time by default, or an explicit capture mode.
const initialDate = new Date();
const initialHour = FORCE_MODE
  ? (FORCE_MODE === 'night' ? 22 : 12)
  : initialDate.getHours() + initialDate.getMinutes() / 60;
state.hour = initialHour;
setHour(initialHour, { instant: true, toast: false, forceMode: true });
syncAutoRotateUI();
setProgress(1, '正在点亮店招');
