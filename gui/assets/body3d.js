(() => {
  const container = document.getElementById("container");
  const statusBadge = document.getElementById("status-badge");

  let bridge = null;
  let renderer;
  let scene;
  let camera;
  let raycaster;
  let pointer;
  let rootGroup;
  let clock;
  const regions = [];
  let selectedName = null;

  function setStatus(text, variant = "neutral") {
    if (!statusBadge) {
      return;
    }
    statusBadge.textContent = text;
    statusBadge.className = variant === "neutral" ? "" : variant;
  }

  function connectBridge() {
    if (window.qt && window.qt.webChannelTransport && window.QWebChannel) {
      new window.QWebChannel(window.qt.webChannelTransport, (channel) => {
        bridge = channel.objects.bridge;
      });
    }
  }

  function addRegion(geometry, name, x, y, z, color = 0x65acc2) {
    const material = new THREE.MeshStandardMaterial({
      color,
      roughness: 0.52,
      metalness: 0.05,
      emissive: 0x000000,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = name;
    mesh.position.set(x, y, z);
    mesh.userData.baseColor = color;
    rootGroup.add(mesh);
    regions.push(mesh);
    return mesh;
  }

  function addBasePart(geometry, x, y, z, sx = 1, sy = 1, sz = 1) {
    const material = new THREE.MeshStandardMaterial({
      color: 0xdbe6ef,
      roughness: 0.76,
      metalness: 0.02,
      transparent: true,
      opacity: 0.92,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(x, y, z);
    mesh.scale.set(sx, sy, sz);
    rootGroup.add(mesh);
  }

  function highlight(name) {
    regions.forEach((mesh) => {
      const isActive = mesh.name === name;
      mesh.material.color.setHex(isActive ? 0x1e8d96 : mesh.userData.baseColor);
      mesh.material.emissive.setHex(isActive ? 0x4dc7c6 : 0x000000);
      mesh.material.opacity = isActive ? 1 : 0.96;
      mesh.scale.setScalar(isActive ? 1.04 : 1);
    });
  }

  function updateHoverState(event) {
    if (!renderer || !camera) {
      return;
    }

    const rect = renderer.domElement.getBoundingClientRect();
    pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(pointer, camera);
    const intersects = raycaster.intersectObjects(regions, false);
    renderer.domElement.style.cursor = intersects.length > 0 ? "pointer" : "default";
  }

  function buildScene() {
    if (!window.THREE) {
      setStatus("3D 库加载失败，请使用下拉框", "error");
      return;
    }

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf2f7fb);
    scene.fog = new THREE.Fog(0xf2f7fb, 5.8, 9.5);

    camera = new THREE.PerspectiveCamera(34, container.clientWidth / container.clientHeight, 0.1, 100);
    camera.position.set(0, 1.55, 4.45);

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(window.devicePixelRatio || 1);
    renderer.setSize(container.clientWidth, container.clientHeight);
    if ("outputColorSpace" in renderer && window.THREE.SRGBColorSpace) {
      renderer.outputColorSpace = window.THREE.SRGBColorSpace;
    }
    container.appendChild(renderer.domElement);

    raycaster = new THREE.Raycaster();
    pointer = new THREE.Vector2();
    clock = new THREE.Clock();

    const hemi = new THREE.HemisphereLight(0xffffff, 0x8fa5b6, 1.15);
    scene.add(hemi);

    const dir = new THREE.DirectionalLight(0xffffff, 1.15);
    dir.position.set(2.8, 4.4, 3.2);
    scene.add(dir);

    const fill = new THREE.DirectionalLight(0xcfe8ee, 0.5);
    fill.position.set(-2.4, 2.8, 1.6);
    scene.add(fill);

    const floor = new THREE.GridHelper(8, 8, 0xaabcc9, 0xd8e4eb);
    floor.position.y = -0.35;
    floor.material.opacity = 0.14;
    floor.material.transparent = true;
    scene.add(floor);

    const shadow = new THREE.Mesh(
      new THREE.CircleGeometry(1.35, 48),
      new THREE.MeshBasicMaterial({ color: 0xd4e1ea, transparent: true, opacity: 0.42 }),
    );
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.set(0, -0.34, 0);
    scene.add(shadow);

    rootGroup = new THREE.Group();
    scene.add(rootGroup);

    addBasePart(new THREE.SphereGeometry(0.23, 20, 20), 0, 2.08, 0);
    addBasePart(new THREE.CapsuleGeometry(0.38, 0.58, 8, 16), 0, 1.4, 0);
    addBasePart(new THREE.CylinderGeometry(0.12, 0.12, 0.86, 16), -0.23, 0.35, 0);
    addBasePart(new THREE.CylinderGeometry(0.12, 0.12, 0.86, 16), 0.23, 0.35, 0);

    addRegion(new THREE.BoxGeometry(0.72, 0.42, 0.18), "胸骨后/正中胸口", 0, 1.45, 0.24, 0x68a8bb);
    addRegion(new THREE.BoxGeometry(0.32, 0.30, 0.16), "左胸", -0.36, 1.42, 0.26, 0x7cb6c8);
    addRegion(new THREE.BoxGeometry(0.32, 0.30, 0.16), "右胸", 0.36, 1.42, 0.26, 0x7cb6c8);
    addRegion(new THREE.BoxGeometry(0.52, 0.28, 0.20), "上腹/心窝", 0, 1.03, 0.21, 0x82b6b3);
    addRegion(new THREE.BoxGeometry(0.90, 0.56, 0.16), "背部/肩胛间", 0, 1.37, -0.26, 0x93c2d4);

    const leftArm = addRegion(new THREE.CylinderGeometry(0.11, 0.11, 0.84, 18), "左肩/左上肢", -0.76, 1.43, 0, 0x8abecd);
    leftArm.rotation.z = 0.35;

    const rightArm = addRegion(new THREE.CylinderGeometry(0.11, 0.11, 0.84, 18), "右肩/右上肢", 0.76, 1.43, 0, 0x8abecd);
    rightArm.rotation.z = -0.35;

    renderer.domElement.addEventListener("pointerdown", onPointerDown);
    renderer.domElement.addEventListener("pointermove", updateHoverState);
    window.addEventListener("resize", onResize);

    setStatus("未选择");
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

    if (intersects.length === 0) {
      return;
    }

    selectedName = intersects[0].object.name || null;
    highlight(selectedName);
    setStatus(selectedName, "active");

    if (bridge && typeof bridge.selectRegion === "function") {
      bridge.selectRegion(selectedName);
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
    if (!renderer || !scene || !camera || !rootGroup || !clock) {
      return;
    }

    const elapsed = clock.getElapsedTime();
    rootGroup.rotation.y = Math.sin(elapsed * 0.45) * 0.22;
    renderer.render(scene, camera);
    requestAnimationFrame(animate);
  }

  window.clearSelection = () => {
    selectedName = null;
    highlight("__none__");
    setStatus("未选择");
  };

  connectBridge();
  buildScene();
})();
