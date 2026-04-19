(function () {
  if (window.__dashRelayInstalled) {
    return;
  }
  window.__dashRelayInstalled = true;

  var registered = new Set();

  function isUsableSetProps() {
    return !!(window.dash_clientside && typeof window.dash_clientside.set_props === "function");
  }

  function getBridge(node) {
    if (!node) return null;
    var own = node.getAttribute("data-relay-bridge");
    if (own) return own;
    var scope = node.closest ? node.closest("[data-relay-default-bridge]") : null;
    return scope ? scope.getAttribute("data-relay-default-bridge") : null;
  }

  function parseJsonAttr(raw, name) {
    if (raw === null || raw === undefined || raw === "") return null;
    try {
      return JSON.parse(raw);
    } catch (err) {
      console.warn("dash_relay: failed to parse " + name, err);
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
      ? event.target.closest("[data-relay-action]")
      : null;
    if (!start) return;
    if (start.dataset.relayOn !== event.type) return;
    if (start.hasAttribute("disabled") || start.getAttribute("aria-disabled") === "true") return;

    var bridge = getBridge(start);
    if (!bridge) {
      console.warn("dash_relay: no bridge found for action", start.dataset.relayAction);
      return;
    }

    if (start.dataset.relayPreventDefault === "true" && typeof event.preventDefault === "function") {
      event.preventDefault();
    }

    var payload = {
      action: start.dataset.relayAction,
      target: parseJsonAttr(start.dataset.relayTarget, "target"),
      payload: parseJsonAttr(start.dataset.relayPayload, "payload"),
      source: parseJsonAttr(start.dataset.relaySource, "source"),
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
    if (root.dataset && root.dataset.relayOn) ensureListener(root.dataset.relayOn);
    if (root.querySelectorAll) {
      var nodes = root.querySelectorAll("[data-relay-on]");
      for (var i = 0; i < nodes.length; i++) {
        ensureListener(nodes[i].dataset.relayOn);
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
      attributeFilter: ["data-relay-on"],
    });
  }

  if (document.body) {
    install();
  } else {
    document.addEventListener("DOMContentLoaded", install);
  }
})();
