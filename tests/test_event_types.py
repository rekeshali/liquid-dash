"""End-to-end verification that any DOM event type works.

The library claims `any DOM event name works for on=`. This file
launches a real Dash app, mounts one emitter per event type, dispatches
each event through a real browser via Playwright, and asserts the
bridge store receives the correct `action` and `type`.

Covers twelve events spanning:
  - common UI events (click, dblclick, input, change, submit, keydown)
  - pointer / touch family (pointerdown, wheel, contextmenu)
  - non-bubbling events (focus, blur) — these rely on the capture-phase
    listener installed by the runtime
  - custom events dispatched directly to the target node

The whole file is skipped unless `playwright` is installed. To run:

    pip install -e .[integration]
    playwright install chromium
    pytest tests/test_event_types.py -v

For the default dev workflow without integration deps, the file is a
no-op — the core test suite keeps passing without these tests.
"""
from __future__ import annotations

import json
import socket
import threading
import time

import pytest

pytest.importorskip("playwright.sync_api")
pytest.importorskip("requests")

import requests
from playwright.sync_api import sync_playwright

from dash import Dash, Input, Output, dcc, html

import dash_relay as relay


# ---------------------------------------------------------------------------
# Test harness: a Dash app with one emitter per event type
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


_ACTIONS = [
    "click",
    "dblclick-action",
    "input-action",
    "change-action",
    "submit-action",
    "keydown-action",
    "contextmenu-action",
    "pointerdown-action",
    "wheel-action",
    "focus-action",
    "blur-action",
    "custom-action",
]


def _build_app() -> Dash:
    from dash import Input as _Input
    from dash_relay import Action, Emitter, DEFAULT_BRIDGE
    from dash_relay.callback import _bridge_store_id, _PENDING_CALLBACKS

    # Ensure a clean handler pool — repeated test runs in the same process
    # would otherwise accumulate.
    _PENDING_CALLBACKS.clear()

    # Register one no-op handler per action so install() mints the
    # default bridge store. The handler returns nothing of consequence;
    # this test cares about the JS → bridge wire path, not handler logic.
    for action_name in _ACTIONS:
        @relay.callback(Output("dummy-state", "data"), Action(action_name))
        def _(event):
            return event.get("action")

    app = Dash(__name__)
    app.layout = html.Div([
        dcc.Store(id="dummy-state"),
        Emitter(action="click").wrap(html.Button("click", id="t-click")),
        Emitter(action="dblclick-action", on="dblclick").wrap(html.Button("dbl", id="t-dblclick")),
        Emitter(action="input-action", on="input").wrap(dcc.Input(id="t-input", placeholder="input")),
        Emitter(action="change-action", on="change").wrap(dcc.Input(id="t-change", placeholder="change")),
        Emitter(action="submit-action", on="submit").wrap(html.Button("submit", id="t-submit")),
        Emitter(action="keydown-action", on="keydown").wrap(dcc.Input(id="t-keydown", placeholder="keydown")),
        Emitter(action="contextmenu-action", on="contextmenu").wrap(html.Div("ctx", id="t-contextmenu")),
        Emitter(action="pointerdown-action", on="pointerdown").wrap(html.Div("pd", id="t-pointerdown")),
        Emitter(action="wheel-action", on="wheel").wrap(html.Div("wheel", id="t-wheel")),
        Emitter(action="focus-action", on="focus").wrap(dcc.Input(id="t-focus", placeholder="focus")),
        Emitter(action="blur-action", on="blur").wrap(dcc.Input(id="t-blur", placeholder="blur")),
        Emitter(action="custom-action", on="my-custom-event").wrap(html.Div("custom", id="t-custom")),
        html.Pre(id="bridge-view"),
    ])

    # Debug callback: mirror the (auto-minted) bridge store into a visible
    # element so the test can read what the JS wrote.
    bridge_store_id = _bridge_store_id(DEFAULT_BRIDGE)

    @app.callback(
        Output("bridge-view", "children"),
        _Input(bridge_store_id, "data"),
        allow_duplicate=True,
        prevent_initial_call=True,
    )
    def show(data):
        return json.dumps(data) if data else ""

    relay.install(app)
    return app


@pytest.fixture(scope="module")
def app_url():
    port = _free_port()
    app = _build_app()

    def _run():
        # dev_tools_* off so the dev panel doesn't interfere
        app.run(port=port, debug=False, use_reloader=False,
                dev_tools_ui=False, dev_tools_props_check=False,
                dev_tools_silence_routes_logging=True)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}/"
    for _ in range(100):
        try:
            if requests.get(url, timeout=0.5).status_code == 200:
                break
        except (requests.ConnectionError, requests.Timeout):
            pass
        time.sleep(0.1)
    else:
        pytest.fail(f"Dash server didn't come up on {port}")

    yield url


@pytest.fixture(scope="module")
def page(app_url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context()
        pg = ctx.new_page()
        pg.goto(app_url)
        # Wait for Dash to hydrate: the bridge-view element must be in the
        # DOM (it renders empty initially, so state="attached" not the
        # default "visible"). Then wait for the dash-relay runtime to
        # install itself.
        pg.wait_for_selector("#bridge-view", state="attached")
        pg.wait_for_function("window.__dashRelayInstalled === true", timeout=10000)
        yield pg
        browser.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_bridge(page) -> dict | None:
    text = page.locator("#bridge-view").text_content() or ""
    return json.loads(text) if text.strip() else None


def _dispatch_and_wait(page, js: str, expected_action: str, timeout: float = 5.0) -> dict:
    """Dispatch an event via JS and poll bridge-view until the expected action arrives."""
    # Clear previous bridge data by dispatching a no-op click on a known target is
    # unreliable; instead we inspect the action field and wait for the *new* one.
    page.evaluate(js)
    deadline = time.time() + timeout
    last = _read_bridge(page)
    while time.time() < deadline:
        data = _read_bridge(page)
        if data and data.get("action") == expected_action:
            return data
        last = data
        time.sleep(0.05)
    pytest.fail(
        f"bridge never received action={expected_action!r}; last observed: {last!r}"
    )


# ---------------------------------------------------------------------------
# Per-event-type cases
# ---------------------------------------------------------------------------


# Each row: (test_id, expected_action, expected_event_type, dispatch_js)
# dispatch_js is evaluated in the page — it triggers the event and should
# result in the bridge store receiving an envelope with .action and .type.
EVENT_CASES = [
    (
        "click",
        "click", "click",
        "document.getElementById('t-click').click()",
    ),
    (
        "dblclick",
        "dblclick-action", "dblclick",
        "document.getElementById('t-dblclick').dispatchEvent("
        "new MouseEvent('dblclick', {bubbles: true, cancelable: true}))",
    ),
    (
        "input",
        "input-action", "input",
        "(() => {"
        " const el = document.getElementById('t-input');"
        " el.value = 'hello';"
        " el.dispatchEvent(new Event('input', {bubbles: true}));"
        "})()",
    ),
    (
        "change",
        "change-action", "change",
        "(() => {"
        " const el = document.getElementById('t-change');"
        " el.value = 'changed';"
        " el.dispatchEvent(new Event('change', {bubbles: true}));"
        "})()",
    ),
    (
        "submit",
        "submit-action", "submit",
        # Dispatch a native submit event directly. The library listens in
        # capture phase on document, so bubbles:true + cancelable:true is
        # enough; we don't actually need the element to be a form.
        "document.getElementById('t-submit').dispatchEvent("
        "new Event('submit', {bubbles: true, cancelable: true}))",
    ),
    (
        "keydown",
        "keydown-action", "keydown",
        "document.getElementById('t-keydown').dispatchEvent("
        "new KeyboardEvent('keydown', {bubbles: true, key: 'a'}))",
    ),
    (
        "contextmenu",
        "contextmenu-action", "contextmenu",
        "document.getElementById('t-contextmenu').dispatchEvent("
        "new MouseEvent('contextmenu', {bubbles: true, cancelable: true}))",
    ),
    (
        "pointerdown",
        "pointerdown-action", "pointerdown",
        "document.getElementById('t-pointerdown').dispatchEvent("
        "new PointerEvent('pointerdown', {bubbles: true}))",
    ),
    (
        "wheel",
        "wheel-action", "wheel",
        "document.getElementById('t-wheel').dispatchEvent("
        "new WheelEvent('wheel', {bubbles: true, deltaY: 10}))",
    ),
    (
        "focus-non-bubbling",
        "focus-action", "focus",
        # focus/blur do NOT bubble. This test proves the capture-phase
        # listener picks them up anyway.
        "document.getElementById('t-focus').focus()",
    ),
    (
        "blur-non-bubbling",
        "blur-action", "blur",
        "(() => {"
        " const el = document.getElementById('t-blur');"
        " el.focus();"
        " el.blur();"
        "})()",
    ),
    (
        "custom-event",
        "custom-action", "my-custom-event",
        "document.getElementById('t-custom').dispatchEvent("
        "new CustomEvent('my-custom-event', {bubbles: true, detail: {k: 1}}))",
    ),
]


@pytest.mark.parametrize(
    "case_id, expected_action, expected_event_type, dispatch_js",
    EVENT_CASES,
    ids=[row[0] for row in EVENT_CASES],
)
def test_event_type_flows_to_bridge(
    page, case_id, expected_action, expected_event_type, dispatch_js,
):
    ev = _dispatch_and_wait(page, dispatch_js, expected_action)
    assert ev["type"] == expected_event_type, (
        f"expected type={expected_event_type!r}, got {ev['type']!r}"
    )
    assert ev["action"] == expected_action
    # Every envelope should carry the mandatory keys.
    for key in ("action", "target", "source", "bridge", "type", "details", "timestamp"):
        assert key in ev, f"missing {key} in envelope: {ev}"


def test_runtime_is_installed_under_new_flag(page):
    """window.__dashRelayInstalled should be the only install marker."""
    installed = page.evaluate("window.__dashRelayInstalled")
    old_installed = page.evaluate("window.__liquidDashInstalled")
    assert installed is True
    assert old_installed is None, (
        "legacy __liquidDashInstalled flag should not exist in a dash-relay build"
    )


def test_data_attributes_use_relay_prefix(page):
    """All emitter wrappers should use data-relay-* attributes."""
    relay_attrs = page.evaluate("document.querySelectorAll('[data-relay-action]').length")
    legacy_attrs = page.evaluate("document.querySelectorAll('[data-ld-action]').length")
    assert relay_attrs > 0
    assert legacy_attrs == 0


def test_asset_route_is_dash_relay(app_url):
    """The JS asset must be served from /_dash_relay/dash_relay.js."""
    resp = requests.get(f"{app_url}_dash_relay/dash_relay.js", timeout=5)
    assert resp.status_code == 200
    body = resp.text
    # Sanity: the script must mark itself as dash-relay.
    assert "__dashRelayInstalled" in body
    assert "__liquidDashInstalled" not in body
    assert "data-relay-action" in body
    assert "data-ld-action" not in body
