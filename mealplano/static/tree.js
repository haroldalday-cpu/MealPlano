// Fit the tree drawing to its box: shrink it to the box width, but never below
// 60% (smaller text would be unreadable). If it is still wider than the box,
// the box scrolls sideways and starts with the root in the middle.
// Without this script the drawing still works; it is just shown at full size.
(function () {
  var MIN_SCALE = 0.6;

  function fit(box) {
    var svg = box.querySelector("svg");
    if (!svg) return;
    var w = Number(svg.dataset.width), h = Number(svg.dataset.height);
    var avail = box.clientWidth - 8;
    var scale = Math.max(Math.min(1, avail / w), MIN_SCALE);
    svg.setAttribute("width", Math.round(w * scale));
    svg.setAttribute("height", Math.round(h * scale));
    box.scrollLeft = Number(svg.dataset.rootX) * scale - box.clientWidth / 2;
  }

  function fitAll() {
    document.querySelectorAll(".tree-scroll").forEach(fit);
  }

  fitAll();
  window.addEventListener("resize", fitAll);
})();
