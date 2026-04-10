(function () {
  if (window.__liquidDashInstalled) {
    return;
  }
  window.__liquidDashInstalled = true;

  function isUsableSetProps() {
    return !!(window.dash_clientside && typeof window.dash_clientside.set_props === "function");
  }

  function getBridge(node) {
    if (!node) {
      return null;
    }
    var own = node.getAttribute("data-ld-bridge");
    if (own) {
      return own;
    }
    var region = node.closest("[data-ld-default-bridge]");
    if (!region) {
      return null;
    }
    var inherited = region.getAttribute("data-ld-default-bridge");
    return inherited || null;
  }

  function parsePayload(raw) {
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw);
    } catch (err) {
      console.warn("liquid_dash: failed to parse payload", err);
      return null;
    }
  }

  function emit(node, eventName, originalEvent) {
    if (!node || !isUsableSetProps()) {
      return;
    }

    var action = node.getAttribute("data-ld-action");
    if (!action) {
      return;
    }

    var configuredEvent = node.getAttribute("data-ld-event") || "click";
    if (configuredEvent !== eventName) {
      return;
    }

    var bridge = getBridge(node);
    if (!bridge) {
      console.warn("liquid_dash: no bridge found for action", action);
      return;
    }

    var payload = {
      action: action,
      target: node.getAttribute("data-ld-target") || null,
      payload: parsePayload(node.getAttribute("data-ld-payload")),
      source: node.getAttribute("data-ld-source") || null,
      bridge: bridge,
      event_type: eventName,
      timestamp: Date.now() / 1000,
    };

    window.dash_clientside.set_props(bridge, { data: payload });

    if (originalEvent && typeof originalEvent.stopPropagation === "function") {
      originalEvent.stopPropagation();
    }
  }

  document.addEventListener("click", function (event) {
    var node = event.target && event.target.closest ? event.target.closest("[data-ld-action]") : null;
    if (!node) {
      return;
    }
    if (node.hasAttribute("disabled") || node.getAttribute("aria-disabled") === "true") {
      return;
    }
    emit(node, "click", event);
  });

  document.addEventListener("keydown", function (event) {
    if (!(event.key === "Enter" || event.key === " ")) {
      return;
    }
    var node = event.target && event.target.closest ? event.target.closest("[data-ld-action]") : null;
    if (!node) {
      return;
    }
    var role = node.getAttribute("role");
    if (role && role !== "button") {
      return;
    }
    event.preventDefault();
    emit(node, "keydown", event);
  });
})();
