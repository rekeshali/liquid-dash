(function () {
  if (window.__liquidDashInstalled) {
    return;
  }
  window.__liquidDashInstalled = true;

  var registered = new Set();

  function isUsableSetProps() {
    return !!(window.dash_clientside && typeof window.dash_clientside.set_props === "function");
  }

  function getBridge(node) {
    if (!node) return null;
    var own = node.getAttribute("data-ld-bridge");
    if (own) return own;
    var scope = node.closest ? node.closest("[data-ld-default-bridge]") : null;
    return scope ? scope.getAttribute("data-ld-default-bridge") : null;
  }

  function parsePayload(raw) {
    if (raw === null || raw === undefined || raw === "") return null;
    try {
      return JSON.parse(raw);
    } catch (err) {
      console.warn("liquid_dash: failed to parse payload", err);
      return null;
    }
  }

  function extractEventFields(event) {
    var out = {};
    var target = event.target;
    if (target) {
      if ("value" in target) out.value = target.value;
      if ("checked" in target) out.checked = target.checked;
    }
    var scalars = ["key", "code", "clientX", "clientY", "deltaX", "deltaY", "button"];
    for (var i = 0; i < scalars.length; i++) {
      var k = scalars[i];
      if (k in event) {
        var v = event[k];
        if (v === null || typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
          out[k] = v;
        }
      }
    }
    return out;
  }

  function handle(event) {
    if (!isUsableSetProps()) return;
    var start = event.target && event.target.closest
      ? event.target.closest("[data-ld-action]")
      : null;
    if (!start) return;
    if (start.dataset.ldEvent !== event.type) return;
    if (start.hasAttribute("disabled") || start.getAttribute("aria-disabled") === "true") return;

    var bridge = getBridge(start);
    if (!bridge) {
      console.warn("liquid_dash: no bridge found for action", start.dataset.ldAction);
      return;
    }

    if (start.dataset.ldPreventDefault === "true" && typeof event.preventDefault === "function") {
      event.preventDefault();
    }

    var payload = {
      action: start.dataset.ldAction,
      target: start.dataset.ldTarget || null,
      payload: parsePayload(start.dataset.ldPayload),
      source: start.dataset.ldSource || null,
      bridge: bridge,
      event_type: event.type,
      native: extractEventFields(event),
      timestamp: Date.now() / 1000,
    };

    window.dash_clientside.set_props(bridge, { data: payload });
  }

  function ensureListener(type) {
    if (!type || registered.has(type)) return;
    registered.add(type);
    document.addEventListener(type, handle, true);
  }

  function scan(root) {
    if (!root) return;
    if (root.nodeType !== 1 && root.nodeType !== 9 && root.nodeType !== 11) return;
    if (root.dataset && root.dataset.ldEvent) ensureListener(root.dataset.ldEvent);
    if (root.querySelectorAll) {
      var nodes = root.querySelectorAll("[data-ld-event]");
      for (var i = 0; i < nodes.length; i++) {
        ensureListener(nodes[i].dataset.ldEvent);
      }
    }
  }

  var observer = new MutationObserver(function (muts) {
    for (var i = 0; i < muts.length; i++) {
      var m = muts[i];
      if (m.type === "attributes") {
        scan(m.target);
      } else {
        for (var j = 0; j < m.addedNodes.length; j++) {
          scan(m.addedNodes[j]);
        }
      }
    }
  });

  function install() {
    scan(document.body);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-ld-event"],
    });
  }

  if (document.body) {
    install();
  } else {
    document.addEventListener("DOMContentLoaded", install);
  }
})();
