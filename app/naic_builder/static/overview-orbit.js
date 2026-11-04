(() => {
  const panel = document.querySelector("[data-overview-orbit]");
  if (!panel) return;

  const control = panel.querySelector("[data-orbit-control]");
  const hint = panel.querySelector("[data-orbit-hint]");
  const reset = panel.querySelector("[data-orbit-reset]");
  const front = panel.querySelector("[data-orbit-front]");
  const back = panel.querySelector("[data-orbit-back]");
  const dots = [...panel.querySelectorAll("[data-orbit-dot]")];

  const samples = 72;
  const turn = 2 * Math.PI;
  const initialPitch = 0.38;
  const initialYaw = -0.45;
  let pitch = initialPitch;
  let yaw = initialYaw;
  let drag = null;

  const circle = (radius, point) => Array.from({ length: samples }, (_, index) => {
    const angle = index * turn / samples;
    return point(radius * Math.cos(angle), radius * Math.sin(angle));
  });
  const orbitTilt = -Math.PI / 7;
  const orbit = circle(74, (x, z) => [x * Math.cos(orbitTilt), x * Math.sin(orbitTilt), z]);
  const rings = [
    circle(48, (x, z) => [x, 0, z]),
    circle(48, (y, z) => [0, y, z]),
    orbit,
  ];

  const svgPoint = ([x, y]) => `${(114 + x).toFixed(2)} ${(75 + y).toFixed(2)}`;
  const segment = (a, b) => `M${svgPoint(a)}L${svgPoint(b)}`;

  function render() {
    const cosYaw = Math.cos(yaw);
    const sinYaw = Math.sin(yaw);
    const cosPitch = Math.cos(pitch);
    const sinPitch = Math.sin(pitch);
    const project = ([x, y, z]) => {
      const depth = z * cosYaw - x * sinYaw;
      return [x * cosYaw + z * sinYaw, y * cosPitch - depth * sinPitch, y * sinPitch + depth * cosPitch];
    };

    const layers = ["", ""];
    for (const ring of rings) {
      const points = ring.map(project);
      for (let index = 0; index < points.length; index++) {
        const a = points[index];
        const b = points[(index + 1) % points.length];
        const aLayer = a[2] >= 0 ? 1 : 0;
        const bLayer = b[2] >= 0 ? 1 : 0;
        if (aLayer === bLayer) {
          layers[aLayer] += segment(a, b);
        } else {
          // Split a segment where it crosses the camera plane so the rear arc stays behind the front arc.
          const ratio = a[2] / (a[2] - b[2]);
          const edge = [a[0] + (b[0] - a[0]) * ratio, a[1] + (b[1] - a[1]) * ratio];
          layers[aLayer] += segment(a, edge);
          layers[bLayer] += segment(edge, b);
        }
      }
    }

    back.setAttribute("d", layers[0]);
    front.setAttribute("d", layers[1]);
    dots.forEach((dot, index) => {
      const [x, y, depth] = project(orbit[index === 0 ? 4 : 40]);
      dot.setAttribute("cx", 114 + x);
      dot.setAttribute("cy", 75 + y);
      dot.setAttribute("opacity", depth >= 0 ? "1" : ".42");
    });

    const isRotated = pitch !== initialPitch || yaw !== initialYaw;
    hint.hidden = isRotated;
    reset.hidden = !isRotated;
  }

  control.addEventListener("pointerdown", (event) => {
    if (drag || !event.isPrimary || event.button !== 0) return;
    control.setPointerCapture(event.pointerId);
    drag = { id: event.pointerId, x: event.clientX, y: event.clientY };
    control.classList.add("is-dragging");
  });

  control.addEventListener("pointermove", (event) => {
    if (!drag || event.pointerId !== drag.id) return;
    const dx = event.clientX - drag.x;
    const dy = event.clientY - drag.y;
    if (!dx && !dy) return;
    yaw = (yaw + dx * 0.018) % turn;
    pitch = (pitch - dy * 0.018) % turn;
    drag.x = event.clientX;
    drag.y = event.clientY;
    render();
  });

  function endDrag(event) {
    if (event.pointerId !== drag?.id) return;
    drag = null;
    control.classList.remove("is-dragging");
  }

  for (const name of ["pointerup", "pointercancel", "lostpointercapture"]) {
    control.addEventListener(name, endDrag);
  }

  const arrowSteps = {
    ArrowLeft: [-1, 0],
    ArrowRight: [1, 0],
    ArrowUp: [0, 1],
    ArrowDown: [0, -1],
  };
  control.addEventListener("keydown", (event) => {
    const step = arrowSteps[event.key];
    if (!step || event.altKey || event.ctrlKey || event.metaKey) return;
    event.preventDefault();
    yaw = (yaw + step[0] * Math.PI / 18) % turn;
    pitch = (pitch + step[1] * Math.PI / 18) % turn;
    render();
  });

  function resetView() {
    pitch = initialPitch;
    yaw = initialYaw;
    control.focus({ preventScroll: true });
    render();
  }

  reset.addEventListener("click", resetView);
  reset.addEventListener("pointerup", (event) => {
    // Touch browsers can suppress the click after a rotation gesture.
    if (event.pointerType === "touch" && event.isPrimary &&
        document.elementFromPoint(event.clientX, event.clientY) === reset) {
      resetView();
    }
  });

  render();
  panel.querySelector("[data-orbit-static]").setAttribute("hidden", "");
  dots.forEach((dot) => dot.removeAttribute("hidden"));
  control.tabIndex = 0;
  control.setAttribute("role", "group");
  control.setAttribute("aria-label", "3D hologram");
  control.setAttribute("aria-describedby", "overview-orb-instructions");
})();
