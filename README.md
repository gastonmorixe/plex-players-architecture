<p align="center">
  <img src="assets/plex-logo.svg?v2" alt="Plex" width="220">
</p>

# Plex Players — Architecture (reverse-engineered)

A black-box reverse-engineering study of how Plex actually ships video playback across its client surfaces. The whole investigation ran from compiled artifacts: a decrypted iOS IPA, the macOS Desktop `.app` bundle, the macOS Plex Media Server bundle, and the (still-encrypted) tvOS IPA pulled from the App Store. No disassembly, no source access, no dynamic instrumentation. Just `otool -L`, `strings`, `rg`, `Info.plist` dumps, and running the Plex Transcoder CLI to make it spill its `./configure` line.

The seven chapters in [`reports/`](./reports/) walk through what each platform actually uses, where the codebases overlap, where they diverge, and how Plex's "host capability over OS" strategy plays out in practice.

## Reports

- **[`00-overview.md`](./reports/00-overview.md)** — top-level summary. The seven research questions with one-paragraph answers, the per-platform UI-stack / player-engine matrix, and the master architecture diagram.
- **[`01-ios-app.md`](./reports/01-ios-app.md)** — iOS. React Native 0.83 on the `react-native-tvos` fork, Hermes, Fabric + TurboModules. Player is `KSPlayer_private` (a Plex fork of [KSPlayer](https://github.com/kingslay/KSPlayer)) wrapping AVPlayer or a custom Media Engine on statically-linked FFmpeg 5 + libass + Metal. No libmpv on iOS, contradicting older blog posts.
- **[`02-macos-desktop.md`](./reports/02-macos-desktop.md)** — Desktop (macOS / Windows / Linux). Qt 6.2.4 host running QtWebEngine that loads the Plex Web SPA. Playback is libmpv 2.0 + FFmpeg 5.x dylibs, driven from JS via QtWebChannel. The spiritual successor to the archived `plexinc/plex-media-player`.
- **[`03-plex-web.md`](./reports/03-plex-web.md)** — Plex Web. One React + Webpack SPA (`plex-4.156+`) with 207 lazy chunks. Shaka Player for HTML5, plus three platform adapters (`mpv` for Qt, `samsung_avplay` for Tizen, `webmaf_video_player` for webOS) chosen at runtime. The same bundle ships inside Plex Desktop, inside PMS as `WebClient.bundle`, and at app.plex.tv.
- **[`04-plex-media-server.md`](./reports/04-plex-media-server.md)** — PMS. C++ server (Boost + pion + OpenSSL) plus 11 sibling binaries. The transcoder is a Plex-maintained fork of FFmpeg 6.1 built with a Plex clang fork via Conan, with proprietary Enhanced Audio Engine decoders for E-AC3 / TrueHD / MLP. Also bundles OpenCV, TF Lite, ONNX Runtime, and Python 2.7 (legacy channel plugins).
- **[`05-cross-platform-code-sharing.md`](./reports/05-cross-platform-code-sharing.md)** — the strategy synthesis. Three client codebases plus the server: `react-native-client` (mobile), `plex-web` (everything HTML-capable), and the legacy `PlexTV` tvOS app. They share a protocol (the Plex API) and a brand, not a codebase. The split is by host capability, not OS.
- **[`06-methodology.md`](./reports/06-methodology.md)** — the tool stack and the order operations matter ran in. Certainty levels (OBSERVED / INFERRED / UNKNOWN) per claim, what *wasn't* needed (no disassembler, no Frida), and the commands to reproduce any single finding.
- **[`07-tvos-app.md`](./reports/07-tvos-app.md)** — tvOS. Two stories told separately: the currently-shipping `PlexTV` 8.45 app is TVMLKit + UIKit NIBs + a SwiftUI bundle mid-migration, with `PlexMPV.framework` (libmpv wrapper) as the player. The iOS RN codebase is *set up* to absorb tvOS (the `react-native-tvos` fork choice is deliberate) but ships zero `Platform.OS === 'tvos'` branches today. The migration is in infrastructure-setup phase, not application-code phase.

## Overview

```
               ┌──────────────────────────────────────────────────────────────────────────┐
               │                         Plex Media Server (PMS)                          │
               ├──────────────────────────────────────────────────────────────────────────┤
               │ C++ / Boost / pion HTTP server                                           │
               │ Custom FFmpeg fork (Plex Transcoder) + Enhanced Audio Engine             │
               │ Shared HTTP / HLS / DASH API + media decision endpoint                   │
               └──────────────────────────────────────────────────────────────────────────┘
                                                     │
                                                     │
              ┌─────────────────────────┬────────────┴────────────┬─────────────────────────┐
              │                         │                         │                         │
  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
  │       iOS App        │  │  tvOS App (legacy)   │  │Desktop (mac/Win/Lin) │  │   Web / Smart TVs    │
  ├──────────────────────┤  ├──────────────────────┤  ├──────────────────────┤  ├──────────────────────┤
  │ Plex 2026.9.0        │  │ PlexTV 8.45 (2024)   │  │ Plex 1.112.0         │  │ plex-4.156+ SPA      │
  │                      │  │                      │  │                      │  │                      │
  │ React Native 0.83    │  │ TVMLKit              │  │ Qt 6.2.4 host        │  │ React + Webpack      │
  │ (react-native-tvos   │  │   (TVML + TVJS,      │  │ + QtWebEngine        │  │ code-split SPA       │
  │   fork) + Hermes JS  │  │   Apple 2015 sample) │  │   (Chromium)         │  │ (207 lazy chunks)    │
  │ + Fabric / TurboMod. │  │ + UIKit NIBs (31x)   │  │                      │  │                      │
  │                      │  │ + SwiftUI bundle     │  │ Loads Plex Web SPA   │  │ Same bundle ships in │
  │ TurboModule bridge:  │  │   (in migration)     │  │ (plex-4.156+ bundle) │  │ browsers, Desktop,   │
  │   NativeEngineMgr    │  │                      │  │                      │  │ Tizen, webOS, and    │
  │                      │  │ Player:              │  │ Bridge:              │  │ PMS WebClient.bundle │
  │ Player:              │  │   PlexMPV.framework  │  │   QtWebChannel       │  │                      │
  │   KSPlayer_private   │  │   (libmpv wrapper)   │  │   (JS <-> C++ RPC)   │  │ Runtime player       │
  │   (Plex's fork)      │  │ + FFmpeg 5.x         │  │                      │  │ selector picks 1 of: │
  │                      │  │ + BASS audio family  │  │ Web backend = 'mpv'  │  │   - 'html'           │
  │ Backends:            │  │ + Mux QoE            │  │                      │  │     Shaka Player     │
  │   - KSAVPlayer       │  │                      │  │ Player:              │  │     (MSE / EME)      │
  │     (AVPlayer/HW VT) │  │ TVMLKit deprecated   │  │   libmpv 2.0         │  │   - 'mpv'            │
  │   - KSMEPlayer       │  │ at WWDC 2024.        │  │ + FFmpeg 5.x dylibs  │  │     (Plex Desktop)   │
  │     (FFmpeg 5 static │  │ RN tvOS scaffolding  │  │ + VideoToolbox HW    │  │   - 'samsung_avplay' │
  │     +libass+Metal)   │  │ set up in iOS mono-  │  │                      │  │     (Tizen)          │
  │                      │  │ repo. Not yet built. │  │                      │  │   - 'webmaf_player'  │
  │                      │  │                      │  │                      │  │     (LG webOS)       │
  └──────────────────────┘  └──────────────────────┘  └──────────────────────┘  └──────────────────────┘
```

> The diagram is generated by [`assets/scripts/render_arch_diagram.py`](./assets/scripts/render_arch_diagram.py) (zero deps, Python 3.10+). Run it to regenerate.

Three things stand out once the pieces are laid side by side.

**Plex splits codebases by host capability, not by OS.** "Has a JS engine and can render HTML?" — that one codebase reaches every browser, the Qt-hosted desktop app, Samsung Tizen, LG webOS, and (transitively) the PMS-served `/web/` UI. "Has a React Native runtime?" — that's the iOS app today and almost certainly Android plus future tvOS. The OS family doesn't matter; the runtime capability does.

**The player is the pluggable seam.** Each surface fixes the rest of the stack and varies one piece: the web SPA picks one of four player adapters (`html` / `mpv` / `samsung_avplay` / `webmaf_video_player`) at startup; the RN side hides the same choice behind the `NativeEngineManager` TurboModule, which can route to KSPlayer's AVPlayer-backed engine or to a Plex-built Media Engine on top of statically-linked FFmpeg. The contract is "give the host a stream, get back transport / scrub / track-switch / EME events."

**The server eats the hard problem.** Codec licensing, hardware-encoder fan-out, Dolby's Enhanced Audio Engine, DVR / commercial-skip / fingerprinting ML, the legacy Python plugin host — all of it lives in PMS. The clients only have to render what the media-decision endpoint hands them. That's why a player as different as KSPlayer on iOS, libmpv on macOS Desktop, Shaka on the web, and PlexMPV (libmpv) on tvOS can coexist without fragmenting the user-facing capability matrix.

The clean nuance worth highlighting: the currently-shipping tvOS app is **not** part of the RN monorepo. It's still TVMLKit + UIKit NIBs + a SwiftUI bundle in mid-migration, with `PlexMPV.framework` as the player. Apple deprecated TVMLKit at WWDC 2024, and Plex's iOS bundle ships the `react-native-tvos` fork — strong intent signals — but zero `Platform.OS === 'tvos'` branches have been written in the JS bundle. Chapter 07 lays out exactly what's observed vs inferred there.

## Scope and provenance

All claims are tagged in-text as **OBSERVED** (direct binary evidence), **INFERRED** (one logical step from observed), or **UNKNOWN** (out of scope or not in the artifacts). See [`reports/06-methodology.md`](./reports/06-methodology.md) for the full evidence trail and the commands to verify any single finding.

The artifacts analyzed:

| Artifact | Version | Source |
|---|---|---|
| `com.plexapp.plex` (iOS) | 2026.9.0, build 1704 | decrypted IPA |
| `Plex.app` (macOS Desktop) | 1.112.0.359 | universal `.app` bundle |
| `PlexMediaServer.app` (macOS PMS) | 1.43.2.10687 | universal `.app` bundle |
| `PlexTV.app` (tvOS) | 8.45, build 9684 | App Store IPA via `ipatool` (FairPlay-encrypted) |

This is an independent third-party study. Not affiliated with or endorsed by Plex Inc.

## License

MIT — see [`LICENSE`](./LICENSE).

The Plex name and logo are trademarks of Plex Inc. and are used here under nominative fair use to identify the subject of the analysis. The logo file in `assets/` comes from [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Plex_logo_2022.svg).

Copyright © 2026 Gaston Morixe &lt;gaston@gastonmorixe.com&gt;.
