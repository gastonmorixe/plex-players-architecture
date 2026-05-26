---
title: "Plex Desktop (macOS) — Qt + QtWebEngine + libmpv hybrid"
chapter: 2
date: 2026-05-24
artifact: Plex-1.112.0.359-0d79a49f-universal.app
sha_or_version:
  bundle_id: tv.plex.desktop
  short_version: "1.112.0"
  build: "1.112.0.359"
  min_os: "macOS 10.12"
  hash: "0d79a49f"
status: complete
certainty: high
---

# Plex Desktop (macOS) — Qt + QtWebEngine + libmpv hybrid

## TL;DR

Plex Desktop is **not a "native Mac app" in the AppKit sense, nor an Electron app**. It is a **Qt 6 application** whose actual UI is **the Plex Web client running inside QtWebEngine** (Qt's Chromium-based web view). The playback engine is **libmpv** — and the web app talks to mpv via **QtWebChannel**, Qt's standard JavaScript ↔ C++ RPC bridge.

This is the spiritual successor to "Plex Media Player" (PMP), which was open source on GitHub (`plexinc/plex-media-player`, archived 2022). The current Plex Desktop continues the same Qt + libmpv design but with a privatised codebase.

## How we know — evidence trail

### 1. Bundle structure

`Plex-1.112.0.359-0d79a49f-universal.app/Contents/`:

```
Info.plist                    bundle id: tv.plex.desktop, version 1.112.0
MacOS/
├── Plex                      (3.5 MB — small! the actual UI runs in web/Qt)
└── Plex Transcoder           (727 KB — embedded mini-transcoder)
Frameworks/                   (~30 Qt 6 frameworks + libmpv + FFmpeg)
PlugIns/                      (Qt plugins: platforms, sqldrivers, tls, …)
Resources/
├── qml/                      (395 .qml files — Qt Quick UI primitives + plex-specific)
├── web-client/               ← THE WEB APP
│   ├── index.html            (loads qrc://qtwebchannel/qwebchannel.js)
│   └── js/ + .css/           (207 chunks, plex-4.156.0-4946c98)
├── mpv.conf.sample           ← user-facing mpv config example
├── mpv.conf.md               ← documentation
├── input.conf.sample         ← user-facing remote/key bindings
├── input.conf.md             ← documentation
├── inputmaps/                ← input bindings (remote controls)
├── scripts/                  ← Lua scripts (mpv supports Lua scripting)
├── sdrBlack.mkv              ← placeholder black-frame video
└── Plex Updater.app
```

The fact that the main `Plex` binary is only **3.5 MB** is itself diagnostic: it's the Qt host shim. The bulk of the app is web + Qt frameworks + libmpv.

### 2. The dynamic linkage proves Qt + mpv

`otool -L Plex` (arm64 slice, selected lines):

```
@rpath/QtCore.framework/Versions/A/QtCore (current version 6.2.4)
@rpath/QtGui.framework/Versions/A/QtGui (current version 6.2.4)
@rpath/QtQml.framework/Versions/A/QtQml
@rpath/QtQuick.framework/Versions/A/QtQuick
@rpath/QtWidgets.framework/Versions/A/QtWidgets
@rpath/QtNetwork.framework/Versions/A/QtNetwork
@rpath/QtWebEngineCore.framework/Versions/A/QtWebEngineCore   ← Chromium-based web view
@rpath/QtWebEngineQuick.framework/Versions/A/QtWebEngineQuick
@rpath/QtWebChannel.framework/Versions/A/QtWebChannel          ← JS↔C++ RPC
@rpath/libmpv.2.dylib                                          ← libmpv 2.0 — the player
@rpath/libavcodec.59.dylib  (FFmpeg 5.x — libmpv's decoder)
@rpath/libavformat.59.dylib
@rpath/libavutil.57.dylib
@rpath/libavfilter.8.dylib
@rpath/libswscale.6.dylib
@rpath/libswresample.4.dylib
@rpath/PlexMediaServer.framework/Versions/A/PlexMediaServer   ← shared HTTP/transport code
```

The full Qt 6.2.4 stack is present, libmpv 2.0 is dynamically loaded, and FFmpeg 5.x dylibs are the codec layer (these are the standard FFmpeg dylib soname numbers that match FFmpeg 5.x's libav* versions).

The `PlexMediaServer.framework` linked here is a **shared framework** between the Desktop client and the server itself — probably containing the HTTP/HTTPS server, certificate handling, and Plex protocol code. (Not the entire PMS — there is no full PMS embedded here.)

### 3. The UI is the Plex Web SPA loaded by QtWebEngine

`Resources/web-client/index.html` (annotated):

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <title>Plex</title>
  ...
  <link rel="stylesheet" href="1531-1531-…-plex-4.156.0-4946c98.css">
  <link rel="stylesheet" href="main-…-plex-4.156.0-4946c98.css">
</head>
<body>
  <div id="plex" class="application"></div>
  <div id="modal-root"></div>

  <!-- THIS LINE: qrc:// is Qt's resource scheme. This script only resolves
       when the page is loaded inside QtWebEngine. -->
  <script src="qrc://:/qtwebchannel/qwebchannel.js"></script>

  <script>
    // Pointer-event suppression on window blur — Qt-side focus handling
    (function () { … })();
  </script>

  <!-- Webpack entry points: runtime → vendor → main -->
  <script src="js/runtime-9121-…-plex-4.156.0-4946c98.js"></script>
  <script src="js/1531-1531-…-plex-4.156.0-4946c98.js"></script>
  <script src="js/main-…-plex-4.156.0-4946c98.js"></script>
</body>
</html>
```

The web app version is **`plex-4.156.0`** (commit `4946c98`). The asset structure is Webpack code-split: a `runtime`, a vendor chunk, a `main`, and **207 lazy chunks** loaded on demand. Total JS payload: **8.7 MB**.

The presence of the `qrc://:/qtwebchannel/qwebchannel.js` script is the smoking gun: this URL only resolves under QtWebEngine. Public app.plex.tv would not have this tag.

### 4. The web app uses QtWebChannel to call into mpv

**OBSERVED** in `main-…-plex-4.156.0-4946c98.js`:

```js
const Sd = "QWebChannel";

function Pd(e) { return `[${Sd}(${e})]`; }
...

// Inside an async initializer:
const e = yield new Promise(e => {
  new window.QWebChannel(window.qt.webChannelTransport, e);
});

return this.objects = e.objects,
       this.connect("system.onDeferredRet…", …);
```

This is the **canonical QtWebChannel init pattern**. The web app:
1. Constructs `window.QWebChannel` using `window.qt.webChannelTransport` (a transport object Qt injects when the page is hosted in QtWebEngine).
2. Receives a set of `objects` — these are proxy objects for C++ QObjects registered by the Qt host.
3. Calls methods on those proxies (e.g., `r.invoke(...)`, `servers.invoke(...)`) to drive the native side: opening a stream in mpv, seeking, pausing, switching audio/subtitle track, etc.

QtWebChannel turns C++ QObject methods/signals/slots into JS methods/promises/events transparently.

### 5. The web app's player-backend selector

**OBSERVED** in `main-…-plex-4.156.0-4946c98.js`:

```js
19: (e, t, r) => {
    "use strict";
    r.d(t, {
      II: () => i,    // ← export: the "mpv" backend constant
      g3: () => n,    // ← export: the "html" backend constant
      y2: () => s     // ← export: the array of all backends
    });

    const n = "html",
          i = "mpv",
          s = [n, i, "samsung_avplay", "webmaf_video_player"];
}
```

This single export tells the whole story. The Plex Web app supports **four player backends** chosen at runtime:

| Constant | Backend | Used by |
|---|---|---|
| `"html"` | HTML5 `<video>` + Shaka Player | regular browsers, app.plex.tv |
| `"mpv"` | libmpv via QtWebChannel | **Plex Desktop (this app)** |
| `"samsung_avplay"` | Samsung Tizen's AVPlay API | Samsung Smart TVs |
| `"webmaf_video_player"` | LG webOS WebMAF | LG Smart TVs |

When running inside QtWebEngine (Plex Desktop), the host environment detection picks `"mpv"`, and all calls that would normally hit a `<video>` element get routed through QtWebChannel to libmpv.

### 6. mpv configuration is exposed to power users

The bundle ships:

- `Resources/mpv.conf.sample` — example mpv config (mpv reads `mpv.conf` from a known location to let users tune deinterlacing, scaler, HDR mapping, etc.)
- `Resources/mpv.conf.md` — documentation of which options Plex respects
- `Resources/input.conf.sample` — keyboard / remote bindings (mpv's standard input syntax)
- `Resources/input.conf.md` — docs
- `Resources/inputmaps/` — predefined input maps (per-device key/remote mappings)
- `Resources/scripts/` — Lua scripts (mpv's plugin system)

This is unambiguous: Plex Desktop is explicitly built around mpv and exposes mpv's config knobs to users who want to tweak.

### 7. QML primitives present but UI is web

`Resources/qml/` contains **395 .qml files**, but inspection shows almost all are standard Qt Quick Controls (Basic theme): `Button.qml`, `ComboBox.qml`, `Slider.qml`, etc. These are needed because QtWebEngine itself uses Qt Quick under the hood for rendering chrome, dialogs, file pickers, etc. There are no Plex-specific QML files that constitute the actual app UI — the app UI is entirely the web SPA.

This is consistent with how Spotify or Discord ship: a thin native shell + an embedded web view that loads the actual UI.

### 8. Why not Electron?

Electron is ~150-200 MB to ship a comparable app. Qt + QtWebEngine ships ~150-200 MB too (the Frameworks folder is large). The win for Qt is **direct C++ integration with libmpv** without a Node.js process or N-API. mpv → Qt is much tighter than mpv → Node → Electron.

This is also why Plex Desktop on macOS can ship a single Mach-O binary and load native dynamic libraries (libmpv, libavcodec, etc.) directly, rather than spawning a separate transcoder/player process.

## Lineage: this is "Plex Media Player 2"

The historical context (NOT from binary, from public record): in 2015–2022, Plex maintained **Plex Media Player (PMP)** as an open-source project at `github.com/plexinc/plex-media-player`. PMP used **Qt 5 + QML + libmpv + an embedded WebKit/QtWebEngine** for the web client. The project was archived in 2022 and replaced by "Plex Desktop".

The artifact analyzed here (Plex 1.112.0 with bundle id `tv.plex.desktop`) is the continuation of PMP's architecture — same Qt + libmpv + embedded web app design, just with a privatised codebase and modernised to Qt 6.2.4.

## Architecture summary

```
┌───────────────────────────────────────────────────────────────────────┐
│  Plex Desktop process (Plex.app, 3.5 MB Mach-O)                       │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  Qt 6.2.4 application (QtCore + QtGui + QtWidgets + QtQuick)     │ │
│  │                                                                 │ │
│  │  ┌────────────────────────────────────────────┐                 │ │
│  │  │  QtWebEngineCore (Chromium-based webview)  │                 │ │
│  │  │                                            │                 │ │
│  │  │  Loads: Resources/web-client/index.html    │                 │ │
│  │  │                                            │                 │ │
│  │  │  ┌────────────────────────────────────┐    │                 │ │
│  │  │  │ Plex Web SPA (plex-4.156.0)        │    │                 │ │
│  │  │  │  • React + Webpack code-split      │    │                 │ │
│  │  │  │  • 207 lazy chunks, 8.7 MB total   │    │                 │ │
│  │  │  │  • Player backend = "mpv"          │    │                 │ │
│  │  │  └────┬───────────────────────────────┘    │                 │ │
│  │  │       │  JS ↔ C++ via QtWebChannel         │                 │ │
│  │  │       │  (new window.QWebChannel(qt.webChannelTransport))    │ │
│  │  └───────┼────────────────────────────────────┘                 │ │
│  │          │                                                       │ │
│  │  ┌───────▼──────────────────────────┐                           │ │
│  │  │  Plex-owned C++ objects exposed  │                           │ │
│  │  │  via QtWebChannel:               │                           │ │
│  │  │   • player                        │                           │ │
│  │  │   • servers                       │                           │ │
│  │  │   • system                        │                           │ │
│  │  │   • (and others)                  │                           │ │
│  │  └───────┬──────────────────────────┘                           │ │
│  └──────────┼─────────────────────────────────────────────────────┘ │
│             │                                                        │
│  ┌──────────▼────────────────────────────────────────────────────┐  │
│  │  libmpv 2.0  (Frameworks/libmpv.2.dylib)                       │  │
│  │   • Reads mpv.conf / input.conf from user dir                  │  │
│  │   • Loads Lua scripts                                          │  │
│  │   • Owns the playback pipeline                                 │  │
│  │   ↓                                                            │  │
│  │  FFmpeg 5.x dylibs (Frameworks/libavcodec.59.dylib + friends)  │  │
│  │   • Decode, demux, filter, scale, resample                     │  │
│  │   ↓                                                            │  │
│  │  Apple HW frameworks (VideoToolbox, AudioToolbox, Metal)       │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  Plus: PlexMediaServer.framework (shared transport + protocol code)  │
└───────────────────────────────────────────────────────────────────────┘
```

## Why this matters for code-sharing

The Plex Desktop ships **the same web SPA** as PMS bundles (compare PMS's `WebClient.bundle/Contents/Resources/index.html` and Desktop's `Resources/web-client/index.html`). Different versions (PMS 1.43.2 ships `plex-4.159`, Desktop 1.112 ships `plex-4.156`), but identical Webpack chunk-naming pipeline and identical chunk hashes for unchanged code.

So **one web codebase reaches: browsers, Plex Desktop, Smart TVs**, and the **only thing that differs is which player backend the runtime selects**. This is the most important cross-platform decision Plex has made — see [05-cross-platform-code-sharing.md](05-cross-platform-code-sharing.md) for the full story.
