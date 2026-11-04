(() => {
  const overview = document.querySelector("[data-overview-globe]");
  if (!overview) return;

  const scene = overview.querySelector("[data-globe-scene]");
  const grid = overview.querySelector("[data-globe-grid]");
  const shortcuts = [...overview.querySelectorAll("[data-globe-view]")];
  const picker = overview.querySelector("[data-globe-picker]");
  const select = overview.querySelector("[data-globe-select]");
  const legend = overview.querySelector("[data-globe-legend]");
  const detailName = overview.querySelector("[data-globe-name]");
  const detailCount = overview.querySelector("[data-globe-count]");
  const detailScope = overview.querySelector("[data-globe-scope]");
  const detailLink = overview.querySelector("[data-globe-link]");
  const detailLinkLabel = overview.querySelector("[data-globe-link-label]");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const formatter = new Intl.NumberFormat();
  const radians = degrees => degrees * Math.PI / 180;
  const wrap = angle => Math.atan2(Math.sin(angle), Math.cos(angle));
  const point = (latitude, longitude) => [
    Math.cos(latitude) * Math.sin(longitude),
    Math.sin(latitude),
    Math.cos(latitude) * Math.cos(longitude),
  ];
  const elements = [...overview.querySelectorAll("[data-globe-pin]")];
  const formElements = elements.slice(3);
  const statusPositions = [[-8, -43], [30, 0], [-8, 43]];
  const defaultPitch = radians(12);
  const columns = Math.ceil(Math.sqrt(formElements.length * 1.5));
  const rows = Math.ceil(formElements.length / columns) || 0;
  const maximum = Math.max(1, ...formElements.map(element => Number(element.dataset.count)));
  const departments = new Map();

  const pins = elements.map((element, index) => {
    const isForm = index >= statusPositions.length;
    let latitude;
    let longitude;
    if (isForm) {
      const offset = index - statusPositions.length;
      const row = Math.floor(offset / columns);
      const column = offset % columns;
      const rowLength = Math.min(columns, formElements.length - row * columns);
      latitude = rows === 1 ? 0 : 54 - row * 108 / (rows - 1);
      longitude = 180 + (column - (rowLength - 1) / 2) * (122 / Math.max(2, columns - 1));

      const location = element.dataset.location;
      if (!departments.has(location)) departments.set(location, departments.size);
      const hues = [167, 201, 44, 272, 335];
      element.style.setProperty("--pin-hue", hues[departments.get(location) % hues.length]);
      const size = 24 + 76 * Math.sqrt(Number(element.dataset.count) / maximum);
      element.style.setProperty("--pin-size", `${size}%`);
    } else {
      [latitude, longitude] = statusPositions[index];
    }

    return { element, isForm, latitude: radians(latitude), longitude: radians(longitude),
      point: point(radians(latitude), radians(longitude)) };
  });
  const formPins = new Map(pins.filter(pin => pin.isForm).map(pin => [pin.element.dataset.key, pin]));
  const sampleLine = (segments, sample) => Array.from({ length: segments + 1 }, (_, index) => sample(index / segments));
  const gridLines = [
    ...[-60, -30, 0, 30, 60].map(latitude => sampleLine(120, fraction => point(radians(latitude), fraction * 2 * Math.PI))),
    ...Array.from({ length: 12 }, (_, index) =>
      sampleLine(60, fraction => point(Math.PI * (fraction - .5), radians(index * 30)))),
  ];

  let yaw = 0;
  let pitch = defaultPitch;
  let selected = null;
  let animation = 0;
  let gesture = null;
  let suppressClick = false;

  function render() {
    const cosYaw = Math.cos(yaw);
    const sinYaw = Math.sin(yaw);
    const cosPitch = Math.cos(pitch);
    const sinPitch = Math.sin(pitch);
    const project = ([x, y, z]) => {
      const depth = x * sinYaw + z * cosYaw;
      return [
        280 + 196 * (x * cosYaw - z * sinYaw),
        228 - 196 * (y * cosPitch - depth * sinPitch),
        y * sinPitch + depth * cosPitch,
      ];
    };

    let path = "";
    for (const line of gridLines) {
      let previous = null;
      for (const sample of line) {
        const [x, y, depth] = project(sample);
        if (depth >= 0) {
          path += `${previous ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`;
        }
        previous = depth >= 0;
      }
    }
    grid.setAttribute("d", path);

    for (const pin of pins) {
      const [x, y, depth] = project(pin.point);
      pin.element.hidden = depth <= .1;
      if (pin.element.hidden) {
        if (document.activeElement === pin.element) scene.focus({ preventScroll: true });
        continue;
      }
      pin.element.style.left = `${x / 5.6}%`;
      pin.element.style.top = `${y / 4.8}%`;
      pin.element.style.zIndex = Math.round(depth * 100);
    }

    const side = cosYaw >= 0 ? "status" : "forms";
    shortcuts.forEach(button => button.setAttribute("aria-pressed", String(button.dataset.globeView === side)));
    if (picker) picker.hidden = side !== "forms";
    legend.hidden = !picker || side !== "forms";
  }

  function showMarker(pin) {
    selected?.element.setAttribute("aria-pressed", "false");
    selected = pin;
    pin.element.setAttribute("aria-pressed", "true");
    const { name, count, scope, url, location, key } = pin.element.dataset;
    detailName.textContent = name;
    detailCount.textContent = formatter.format(Number(count));
    detailScope.textContent = location && location !== name ? `${location} · ${scope}` : scope;
    detailLink.href = url;
    detailLinkLabel.textContent = pin === pins[0] ? "Open work queue" : "Open records";
    if (select) select.value = key;
  }

  function turnTo(longitude, latitude) {
    cancelAnimationFrame(animation);
    if (reduceMotion.matches) {
      yaw = longitude;
      pitch = latitude;
      render();
      return;
    }
    const startYaw = yaw;
    const startPitch = pitch;
    const distance = wrap(longitude - yaw);
    const start = performance.now();
    function frame(now) {
      const progress = Math.min(1, (now - start) / 560);
      const ease = 1 - (1 - progress) ** 3;
      yaw = wrap(startYaw + distance * ease);
      pitch = startPitch + (latitude - startPitch) * ease;
      render();
      if (progress < 1) animation = requestAnimationFrame(frame);
    }
    animation = requestAnimationFrame(frame);
  }

  function selectMarker(pin) {
    showMarker(pin);
    turnTo(pin.longitude, pin.latitude);
  }

  scene.addEventListener("pointerdown", event => {
    if (gesture || !event.isPrimary || event.button !== 0) return;
    cancelAnimationFrame(animation);
    suppressClick = false;
    gesture = { id: event.pointerId, x: event.clientX, y: event.clientY,
      yaw, pitch, marker: event.target.closest("[data-globe-pin]"), dragging: false };
  });

  scene.addEventListener("pointermove", event => {
    if (event.pointerId !== gesture?.id) return;
    const dx = event.clientX - gesture.x;
    const dy = event.clientY - gesture.y;
    if (!gesture.dragging) {
      if (Math.hypot(dx, dy) < 7) return;
      gesture.dragging = true;
      suppressClick = true;
      scene.setPointerCapture(event.pointerId);
      overview.setAttribute("data-globe-dragging", "");
    }
    const speed = Math.PI / Math.max(175, scene.getBoundingClientRect().width * .68);
    yaw = wrap(gesture.yaw - dx * speed);
    pitch = Math.max(-1.48, Math.min(1.48, gesture.pitch + dy * speed));
    render();
  });

  function endGesture(event) {
    if (event.pointerId !== gesture?.id) return;
    const { marker, dragging } = gesture;
    gesture = null;
    overview.removeAttribute("data-globe-dragging");
    // Touch may suppress the native click after a rotation.
    if (event.type === "pointerup" && event.pointerType === "touch" && !dragging && marker &&
        document.elementFromPoint(event.clientX, event.clientY) === marker) {
      suppressClick = true;
      selectMarker(pins.find(pin => pin.element === marker));
    }
  }

  window.addEventListener("pointerup", endGesture);
  window.addEventListener("pointercancel", endGesture);
  scene.addEventListener("lostpointercapture", event => {
    if (event.target === scene) endGesture(event);
  });

  scene.addEventListener("click", event => {
    if (!suppressClick || event.detail === 0) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    suppressClick = false;
  }, true);

  scene.addEventListener("keydown", event => {
    if (event.target !== scene || event.altKey || event.ctrlKey || event.metaKey) return;
    const step = radians(15);
    const moves = { ArrowLeft: [step, 0], ArrowRight: [-step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] };
    if (!moves[event.key]) return;
    event.preventDefault();
    cancelAnimationFrame(animation);
    const [dx, dy] = moves[event.key];
    yaw = wrap(yaw + dx);
    pitch = Math.max(-1.48, Math.min(1.48, pitch + dy));
    render();
  });

  pins.forEach(pin => {
    pin.element.setAttribute("aria-pressed", "false");
    pin.element.addEventListener("click", () => selectMarker(pin));
  });
  shortcuts.forEach(button => button.addEventListener("click", () => {
    const forms = button.dataset.globeView === "forms";
    if (forms) {
      const busiest = pins.slice(3).reduce((best, pin) =>
        Number(pin.element.dataset.count) > Number(best.element.dataset.count) ? pin : best);
      showMarker(busiest);
    } else {
      showMarker(pins[0]);
    }
    turnTo(forms ? Math.PI : 0, defaultPitch);
  }));
  select?.addEventListener("change", () => {
    const pin = formPins.get(select.value);
    if (pin) selectMarker(pin);
  });

  scene.tabIndex = 0;
  scene.setAttribute("role", "group");
  scene.setAttribute("aria-label", "Interactive record globe");
  scene.setAttribute("aria-describedby", "overview-globe-instructions");
  showMarker(pins[0]);
  render();
  overview.querySelector("[data-globe-fallback]").hidden = true;
  overview.querySelector("[data-globe-controls]").hidden = false;
  overview.querySelector("[data-globe-detail]").hidden = false;
  overview.setAttribute("data-globe-ready", "");
})();
