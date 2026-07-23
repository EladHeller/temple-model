import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const EYE_HEIGHT = 1.6;
const WALK_SPEED = 3.2;
const RUN_SPEED = 6.0;
const TURN_SPEED = 1.9;
const PLAYER_RADIUS = 0.18;
const MAX_MOVE_SUBSTEP = 0.10;
// The rise between the Israel and Priests' Courts is one cubit (0.5 m).
// Keep a small tolerance for bevelled/exported geometry at its edges.
const MAX_STEP = 0.52;
const STEP_TOLERANCE = 0.03;
const MAX_DROP = 1.25;
const UP = new THREE.Vector3(0, 1, 0);
const DOWN = new THREE.Vector3(0, -1, 0);

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function disposeObject(root) {
  if (!root) return;
  root.traverse(object => {
    if (!object.isMesh) return;
    object.geometry?.dispose();
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    materials.forEach(material => {
      if (!material) return;
      Object.values(material).forEach(value => {
        if (value?.isTexture) value.dispose();
      });
      material.dispose();
    });
  });
}

export function createWalkTour({
  stage,
  canvas,
  intro,
  startButton,
  closeButton,
  joystick,
  joystickKnob,
  onProgress = () => {},
  onReady = () => {},
  onError = () => {},
  onPointerLockChange = () => {},
}) {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(68, 1, 0.04, 700);
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  } catch (error) {
    let unsupportedActive = false;
    return {
      enter() { unsupportedActive = true; onError(error); },
      exit() { unsupportedActive = false; canvas.hidden = true; },
      load() { onError(error); return Promise.resolve(); },
      jumpTo() {},
      reset() {},
      showHelp() {},
      get active() { return unsupportedActive; },
      get source() { return ''; },
      get variant() { return 'exterior'; },
    };
  }
  const loader = new GLTFLoader();
  const clock = new THREE.Clock();
  const raycaster = new THREE.Raycaster();
  const normalMatrix = new THREE.Matrix3();
  const moveInput = new THREE.Vector2();
  const touchInput = new THREE.Vector2();
  const forward = new THREE.Vector3();
  const right = new THREE.Vector3();
  const movement = new THREE.Vector3();
  const rayOrigin = new THREE.Vector3();
  const candidate = new THREE.Vector3();
  const keys = new Set();

  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.18;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));

  scene.add(new THREE.HemisphereLight(0xcbd8ee, 0x5e4932, 2.2));
  const sunlight = new THREE.DirectionalLight(0xffe0aa, 3.4);
  sunlight.position.set(-45, 80, 30);
  scene.add(sunlight);

  let model = null;
  let groundMeshes = [];
  let obstacleBoxes = [];
  let active = false;
  let loadingToken = 0;
  let animationFrame = 0;
  let yaw = 0;
  let pitch = 0;
  let spawn = { position: [0, 0, 0], yaw: 0, pitch: 0 };
  let currentSource = '';
  let currentVariant = 'exterior';
  let pendingWaypoint = null;
  let lastTouchLook = null;
  let joystickPointer = null;
  let joystickCenter = { x: 0, y: 0 };

  function setSceneMood(variant) {
    const interior = variant === 'interior';
    scene.background = new THREE.Color(interior ? 0x14171d : 0x4a5664);
    scene.fog = new THREE.Fog(interior ? 0x14171d : 0x4a5664, interior ? 70 : 220, interior ? 230 : 640);
    renderer.toneMappingExposure = interior ? 1.34 : 1.12;
  }

  function resize() {
    if (!active) return;
    const width = Math.max(1, stage.clientWidth);
    const height = Math.max(1, stage.clientHeight);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }

  function worldNormal(hit) {
    if (!hit.face) return UP;
    normalMatrix.getNormalMatrix(hit.object.matrixWorld);
    return hit.face.normal.clone().applyMatrix3(normalMatrix).normalize();
  }

  function groundAt(x, z, referenceFootY, generous = false) {
    if (!model) return null;
    const rise = generous ? 120 : MAX_STEP + 0.08;
    const drop = generous ? 240 : MAX_DROP;
    rayOrigin.set(x, referenceFootY + rise, z);
    raycaster.set(rayOrigin, DOWN);
    raycaster.near = 0;
    raycaster.far = rise + drop;
    const hits = raycaster.intersectObjects(groundMeshes, false);
    for (const hit of hits) {
      if (Math.abs(worldNormal(hit).dot(UP)) < 0.58) continue;
      const height = hit.point.y;
      if (!generous && height - referenceFootY > MAX_STEP + STEP_TOLERANCE) continue;
      return height;
    }
    return null;
  }

  function horizontalBlocked(to, footY, nextGround) {
    const standingY = Math.max(footY, nextGround);
    for (const obstacle of obstacleBoxes) {
      const { box } = obstacle;
      // Low details such as the Tabernacle sockets can be stepped over. Using
      // the box top here also prevents thin thresholds and paving bevels from
      // becoming invisible walls when they are not tagged as ground meshes.
      if (box.max.y <= standingY + MAX_STEP + STEP_TOLERANCE) continue;
      if (box.min.y >= standingY + EYE_HEIGHT - 0.05) continue;
      const insideX = to.x >= box.min.x - PLAYER_RADIUS && to.x <= box.max.x + PLAYER_RADIUS;
      const insideZ = to.z >= box.min.z - PLAYER_RADIUS && to.z <= box.max.z + PLAYER_RADIUS;
      if (insideX && insideZ) return true;
    }
    return false;
  }

  function tryAxisMove(dx, dz) {
    if (!model || (dx === 0 && dz === 0)) return;
    const footY = camera.position.y - EYE_HEIGHT;
    candidate.copy(camera.position);
    candidate.x += dx;
    candidate.z += dz;
    let nextGround = groundAt(candidate.x, candidate.z, footY);
    if (nextGround === null) {
      // Bevels and independently modelled parts can leave centimetre-sized
      // seams between otherwise continuous stairs, ramps and thresholds.
      // Probe within the player's footprint so those seams do not trap the
      // camera at the same rejected movement point forever.
      const probeX = candidate.x + Math.sign(dx) * PLAYER_RADIUS;
      const probeZ = candidate.z + Math.sign(dz) * PLAYER_RADIUS;
      nextGround = groundAt(probeX, probeZ, footY);
    }
    if (nextGround === null) return;
    if (horizontalBlocked(candidate, footY, nextGround)) return;
    candidate.y = nextGround + EYE_HEIGHT;
    camera.position.copy(candidate);
    canvas.dataset.cameraPosition = camera.position.toArray().map(value => value.toFixed(3)).join(',');
  }

  function updateMovement(delta) {
    if (keys.has('ArrowLeft')) yaw += TURN_SPEED * delta;
    if (keys.has('ArrowRight')) yaw -= TURN_SPEED * delta;

    moveInput.set(0, 0);
    if (keys.has('KeyW') || keys.has('ArrowUp')) moveInput.y += 1;
    if (keys.has('KeyS') || keys.has('ArrowDown')) moveInput.y -= 1;
    if (keys.has('KeyA')) moveInput.x -= 1;
    if (keys.has('KeyD')) moveInput.x += 1;
    moveInput.add(touchInput);
    if (moveInput.lengthSq() > 1) moveInput.normalize();
    if (moveInput.lengthSq() === 0) return;

    forward.set(-Math.sin(yaw), 0, -Math.cos(yaw));
    right.set(Math.cos(yaw), 0, -Math.sin(yaw));
    movement.copy(forward).multiplyScalar(moveInput.y).addScaledVector(right, moveInput.x);
    if (movement.lengthSq() > 1) movement.normalize();
    const speed = keys.has('ShiftLeft') || keys.has('ShiftRight') ? RUN_SPEED : WALK_SPEED;
    movement.multiplyScalar(speed * delta);
    const substeps = Math.max(1, Math.ceil(Math.max(Math.abs(movement.x), Math.abs(movement.z)) / MAX_MOVE_SUBSTEP));
    const stepX = movement.x / substeps;
    const stepZ = movement.z / substeps;
    for (let index = 0; index < substeps; index += 1) {
      tryAxisMove(stepX, 0);
      tryAxisMove(0, stepZ);
    }
  }

  function updateCameraRotation() {
    camera.rotation.order = 'YXZ';
    camera.rotation.y = yaw;
    camera.rotation.x = pitch;
  }

  function frame() {
    if (!active) return;
    const delta = Math.min(clock.getDelta(), 0.05);
    updateMovement(delta);
    updateCameraRotation();
    renderer.render(scene, camera);
    animationFrame = requestAnimationFrame(frame);
  }

  function placeCamera(viewpoint) {
    if (!viewpoint?.position) return;
    const [x, y, z] = viewpoint.position;
    yaw = viewpoint.yaw || 0;
    pitch = viewpoint.pitch || 0;
    const snappedGround = groundAt(x, z, y, true);
    camera.position.set(x, (snappedGround ?? y) + EYE_HEIGHT, z);
    canvas.dataset.cameraPosition = camera.position.toArray().map(value => value.toFixed(3)).join(',');
    updateCameraRotation();
  }

  function resetPosition() {
    placeCamera(spawn);
  }

  function jumpTo(viewpoint) {
    if (!viewpoint?.position) return;
    if (!model) {
      pendingWaypoint = viewpoint;
      return;
    }
    keys.clear();
    touchInput.set(0, 0);
    joystickKnob.style.transform = '';
    placeCamera(viewpoint);
  }

  async function load(source, nextSpawn, variant = 'exterior') {
    const token = ++loadingToken;
    pendingWaypoint = null;
    currentSource = source;
    currentVariant = variant;
    spawn = nextSpawn;
    setSceneMood(variant);
    onProgress(0);

    try {
      const gltf = await new Promise((resolve, reject) => {
        loader.load(source, resolve, event => {
          if (event.total) onProgress(clamp(event.loaded / event.total, 0, 1));
        }, reject);
      });
      if (token !== loadingToken) {
        disposeObject(gltf.scene);
        return;
      }
      if (model) {
        scene.remove(model);
        disposeObject(model);
      }
      model = gltf.scene;
      groundMeshes = [];
      obstacleBoxes = [];
      scene.add(model);
      model.updateMatrixWorld(true);
      model.traverse(object => {
        if (!object.isMesh || object.visible === false) return;
        if (/^(?:תווית|label)/i.test(object.name)) return;
        object.frustumCulled = true;
        const isGround = /(?:קרקע|^רצפת|^משטח|אבן ריצוף|^מעלת|^מעלה |מעלה (?:חיצונית )?במקווה|^בסיס העזרה|^המפלס המוגבה|^רצועת החיל|^כבש|^דופן נחושת כבש|^מילוי אדמה בכבש|^מילוי אדמה במזבח|^פני אדמת המזבח|^דופן מזבח הנחושת|מקום הילוך|אבן הסף|מעמד הטהרה)/.test(object.name);
        if (isGround) {
          groundMeshes.push(object);
        } else if (!/סורג/.test(object.name)) {
          obstacleBoxes.push({ name: object.name, box: new THREE.Box3().setFromObject(object) });
        }
      });
      resetPosition();
      if (pendingWaypoint) {
        placeCamera(pendingWaypoint);
        pendingWaypoint = null;
      }
      onProgress(1);
      onReady();
    } catch (error) {
      if (token === loadingToken) onError(error);
    }
  }

  function showIntro() {
    intro.hidden = false;
    startButton.focus({ preventScroll: true });
  }

  function hideIntro() {
    intro.hidden = true;
  }

  function enter({ source, spawn: nextSpawn, variant = 'exterior' }) {
    active = true;
    canvas.hidden = false;
    clock.start();
    resize();
    if (source !== currentSource || !model) load(source, nextSpawn, variant);
    else {
      spawn = nextSpawn;
      currentVariant = variant;
      setSceneMood(variant);
      resetPosition();
      onReady();
    }
    showIntro();
    cancelAnimationFrame(animationFrame);
    frame();
  }

  function exit() {
    active = false;
    keys.clear();
    touchInput.set(0, 0);
    joystickKnob.style.transform = '';
    hideIntro();
    canvas.hidden = true;
    cancelAnimationFrame(animationFrame);
    if (document.pointerLockElement === canvas) document.exitPointerLock();
  }

  function beginControl() {
    hideIntro();
    if (matchMedia('(pointer: fine)').matches) {
      const request = canvas.requestPointerLock?.();
      request?.catch?.(() => onPointerLockChange(false));
    } else canvas.focus({ preventScroll: true });
  }

  function handleKeyDown(event) {
    if (!active) return;
    if (['KeyW', 'KeyA', 'KeyS', 'KeyD', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ShiftLeft', 'ShiftRight'].includes(event.code)) {
      event.preventDefault();
      keys.add(event.code);
    }
  }

  function handleKeyUp(event) {
    keys.delete(event.code);
  }

  function handleMouseLook(event) {
    if (!active || document.pointerLockElement !== canvas) return;
    yaw -= event.movementX * 0.0022;
    pitch = clamp(pitch - event.movementY * 0.0019, -1.42, 1.42);
  }

  function updateJoystick(clientX, clientY) {
    const radius = Math.max(28, joystick.clientWidth * 0.34);
    let dx = clientX - joystickCenter.x;
    let dy = clientY - joystickCenter.y;
    const length = Math.hypot(dx, dy);
    if (length > radius) {
      dx = dx / length * radius;
      dy = dy / length * radius;
    }
    joystickKnob.style.transform = `translate(${dx}px, ${dy}px)`;
    touchInput.set(dx / radius, -dy / radius);
  }

  joystick.addEventListener('pointerdown', event => {
    if (!active) return;
    event.preventDefault();
    joystickPointer = event.pointerId;
    joystick.setPointerCapture(event.pointerId);
    const rect = joystick.getBoundingClientRect();
    joystickCenter = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
    updateJoystick(event.clientX, event.clientY);
  });
  joystick.addEventListener('pointermove', event => {
    if (event.pointerId === joystickPointer) updateJoystick(event.clientX, event.clientY);
  });
  function releaseJoystick(event) {
    if (event.pointerId !== joystickPointer) return;
    joystickPointer = null;
    touchInput.set(0, 0);
    joystickKnob.style.transform = '';
  }
  joystick.addEventListener('pointerup', releaseJoystick);
  joystick.addEventListener('pointercancel', releaseJoystick);

  canvas.addEventListener('pointerdown', event => {
    if (!active || !intro.hidden) return;
    if (event.pointerType === 'mouse') {
      canvas.requestPointerLock?.();
      return;
    }
    lastTouchLook = { id: event.pointerId, x: event.clientX, y: event.clientY };
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener('pointermove', event => {
    if (!lastTouchLook || event.pointerId !== lastTouchLook.id) return;
    yaw -= (event.clientX - lastTouchLook.x) * 0.006;
    pitch = clamp(pitch - (event.clientY - lastTouchLook.y) * 0.005, -1.42, 1.42);
    lastTouchLook.x = event.clientX;
    lastTouchLook.y = event.clientY;
  });
  function releaseTouchLook(event) {
    if (lastTouchLook?.id === event.pointerId) lastTouchLook = null;
  }
  canvas.addEventListener('pointerup', releaseTouchLook);
  canvas.addEventListener('pointercancel', releaseTouchLook);

  startButton.addEventListener('click', beginControl);
  closeButton.addEventListener('click', hideIntro);
  window.addEventListener('keydown', handleKeyDown, { passive: false });
  window.addEventListener('keyup', handleKeyUp);
  document.addEventListener('mousemove', handleMouseLook);
  document.addEventListener('pointerlockchange', () => {
    onPointerLockChange(document.pointerLockElement === canvas);
  });
  window.addEventListener('resize', resize);
  new ResizeObserver(resize).observe(stage);

  return {
    enter,
    exit,
    load(source, nextSpawn, variant) {
      spawn = nextSpawn;
      if (active) return load(source, nextSpawn, variant);
      currentSource = '';
      return Promise.resolve();
    },
    jumpTo,
    reset: resetPosition,
    showHelp: showIntro,
    get active() { return active; },
    get source() { return currentSource; },
    get variant() { return currentVariant; },
  };
}
