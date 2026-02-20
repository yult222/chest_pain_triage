(() => {
  const container = document.getElementById("container");
  const hint = document.getElementById("hint");

  let bridge = null;
  let renderer;
  let scene;
  let camera;
  let raycaster;
  let pointer;
  let rootGroup;
  const regions = [];
  let selectedName = null;

  function setHint(text) {
    if (hint) {
      hint.textContent = text;
    }
  }

  function connectBridge() {
    if (window.qt && window.qt.webChannelTransport && window.QWebChannel) {
      new window.QWebChannel(window.qt.webChannelTransport, (channel) => {
        bridge = channel.objects.bridge;
      });
    }
  }

  function addRegion(geometry, name, x, y, z, color = 0x6aa9ff) {
    const material = new THREE.MeshStandardMaterial({
      color,
      roughness: 0.58,
      metalness: 0.04,
      emissive: 0x000000,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = name;
    mesh.position.set(x, y, z);
    rootGroup.add(mesh);
    regions.push(mesh);
    return mesh;
  }

  function addBasePart(geometry, x, y, z, sx = 1, sy = 1, sz = 1) {
    const material = new THREE.MeshStandardMaterial({
      color: 0xd7e2ef,
      roughness: 0.75,
      metalness: 0.02,
      transparent: true,
      opacity: 0.85,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(x, y, z);
    mesh.scale.set(sx, sy, sz);
    rootGroup.add(mesh);
  }

  function highlight(name) {
    regions.forEach((mesh) => {
      if (mesh.name === name) {
        mesh.material.emissive.setHex(0xffaa00);
      } else {
        mesh.material.emissive.setHex(0x000000);
      }
    });
  }

  function buildScene() {
    if (!window.THREE) {
      setHint("3D 库加载失败，请使用下拉框选择疼痛位置");
      return;
    }

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf5f8fc);

    camera = new THREE.PerspectiveCamera(35, container.clientWidth / container.clientHeight, 0.1, 100);
    camera.position.set(0, 1.55, 4.4);

    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    raycaster = new THREE.Raycaster();
    pointer = new THREE.Vector2();

    const hemi = new THREE.HemisphereLight(0xffffff, 0x64748b, 0.95);
    scene.add(hemi);

    const dir = new THREE.DirectionalLight(0xffffff, 0.95);
    dir.position.set(2.5, 4.0, 3.0);
    scene.add(dir);

    const ground = new THREE.GridHelper(8, 8, 0x94a3b8, 0xcbd5e1);
    ground.position.y = -0.35;
    ground.material.opacity = 0.2;
    ground.material.transparent = true;
    scene.add(ground);

    rootGroup = new THREE.Group();
    scene.add(rootGroup);

    // Base mannequin silhouette (non-clickable)
    addBasePart(new THREE.SphereGeometry(0.23, 20, 20), 0, 2.08, 0);
    addBasePart(new THREE.CapsuleGeometry(0.38, 0.58, 8, 16), 0, 1.4, 0);
    addBasePart(new THREE.CylinderGeometry(0.12, 0.12, 0.86, 16), -0.23, 0.35, 0);
    addBasePart(new THREE.CylinderGeometry(0.12, 0.12, 0.86, 16), 0.23, 0.35, 0);

    // Clickable regions
    addRegion(new THREE.BoxGeometry(0.72, 0.42, 0.18), "胸骨后/正中胸口", 0, 1.45, 0.24, 0x5ea4ff);
    addRegion(new THREE.BoxGeometry(0.32, 0.30, 0.16), "左胸", -0.36, 1.42, 0.26, 0x7cb6ff);
    addRegion(new THREE.BoxGeometry(0.32, 0.30, 0.16), "右胸", 0.36, 1.42, 0.26, 0x7cb6ff);
    addRegion(new THREE.BoxGeometry(0.52, 0.28, 0.20), "上腹/心窝", 0, 1.03, 0.21, 0x6ea8f7);
    addRegion(new THREE.BoxGeometry(0.90, 0.56, 0.16), "背部/肩胛间", 0, 1.37, -0.26, 0x93c5fd);

    const leftArm = addRegion(new THREE.CylinderGeometry(0.11, 0.11, 0.84, 18), "左肩/左上肢", -0.76, 1.43, 0, 0x8bbcf8);
    leftArm.rotation.z = 0.35;
    const rightArm = addRegion(new THREE.CylinderGeometry(0.11, 0.11, 0.84, 18), "右肩/右上肢", 0.76, 1.43, 0, 0x8bbcf8);
    rightArm.rotation.z = -0.35;

    renderer.domElement.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("resize", onResize);

    setHint("点击模型选择疼痛位置");
    animate();
  }

  function onPointerDown(event) {
    if (!renderer || !camera || !scene) {
      return;
    }

    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(pointer, camera);
    const intersects = raycaster.intersectObjects(regions, false);

    if (intersects.length > 0) {
      selectedName = intersects[0].object.name || null;
      highlight(selectedName);
      setHint(`已选择: ${selectedName}`);
      if (bridge && typeof bridge.selectRegion === "function") {
        bridge.selectRegion(selectedName);
      }
    }
  }

  function onResize() {
    if (!renderer || !camera) {
      return;
    }
    const width = container.clientWidth;
    const height = container.clientHeight;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
  }

  function animate() {
    if (!renderer || !scene || !camera) {
      return;
    }
    rootGroup.rotation.y += 0.003;
    renderer.render(scene, camera);
    requestAnimationFrame(animate);
  }

  window.clearSelection = () => {
    selectedName = null;
    highlight("__none__");
    setHint("点击模型选择疼痛位置");
  };

  connectBridge();
  buildScene();
})();
