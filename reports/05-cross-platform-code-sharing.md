---
title: "Cross-platform strategy — two parallel codebases by host capability"
chapter: 5
date: 2026-05-24
status: complete
certainty: high (for what's observed); inferred (for non-iOS / non-macOS targets)
---

# Cross-platform strategy — two parallel codebases by host capability

## TL;DR

Plex shares code by **host capability**, not by OS. The currently observable picture has **three** distinct client codebases plus the server, with one of them (tvOS) on a deprecation path:

1. **`react-native-client`** monorepo → iOS today (Plex 2026.9.0). Set up via `react-native-tvos` (the fork) for future tvOS / Android-TV targeting, but **no tvOS application code shipped yet** — the iOS bundle has zero `Platform.OS === 'tvos'` branches.
2. **`plex-web` Webpack SPA** → every host with an HTML rendering engine (browsers, Plex Desktop via QtWebEngine, Samsung Tizen TVs, LG webOS TVs).
3. **`PlexTV` (legacy tvOS)** → currently shipping tvOS app (PlexTV 8.45, early 2024). Built on Apple's **TVMLKit** (TVML + TVJS), which Apple **deprecated at WWDC 2024**. Uses **`PlexMPV.framework`** (libmpv wrapper) as the player. Plex appears to be preparing to migrate this into the RN monorepo, but the migration is in *infrastructure-setup* phase, not yet *application-code* phase.
4. **Plex Media Server** is the protocol authority and the transcoder. Every client speaks to it via the same HTTP API.

The codebases are **deliberately not unified**. They diverge where the runtime trade-offs differ: native performance and OS integration matter on mobile, broad surface coverage matters on TVs/desktop, and the tvOS app sits on a separate legacy stack pending migration.

## The strategy as a diagram

```
                                ┌────────────────────────────────────────┐
                                │  Plex Media Server (PMS)               │
                                │  C++ / Boost / pion / FFmpeg fork      │
                                │  • Transcodes for any client capability │
                                │  • Serves Plex Web client at :32400    │
                                │  • Same HTTP API for everyone          │
                                └────────────┬───────────────────────────┘
                                             │
      ┌─────────────────────────┬──────────┴──────────┬──────────────────────────────┐
      │                         │                     │                              │
      ▼                         ▼                     ▼                              ▼
┌──────────────────┐ ┌──────────────────────┐ ┌────────────────────┐ ┌──────────────────────┐
│ react-native-    │ │  PlexTV (legacy)     │ │ plex-web Webpack   │ │ Other (unknown)      │
│ client (RN)      │ │                      │ │ SPA                │ │ • Roku?              │
│                  │ │ Currently shipping   │ │                    │ │ • PS / Xbox?         │
│ Currently        │ │ on tvOS App Store.   │ │ ONE React+Webpack  │ │ • Android TV variant?│
│ targets: iOS     │ │                      │ │ codebase with 4    │ │                      │
│ (observed)       │ │ Stack:               │ │ player adapters:   │ │ (separate from these │
│                  │ │  • TVMLKit (TVML +   │ │  • "html" + Shaka  │ │  three codebases)    │
│ Set up for       │ │    TVJS, from Apple  │ │  • "mpv" via Qt    │ │                      │
│ future tvOS /    │ │    2015 sample!)     │ │    WebChannel      │ │                      │
│ Android TV       │ │  • UIKit NIBs        │ │  • "samsung_       │ │                      │
│ via the          │ │    (31 native        │ │     avplay"        │ │                      │
│ react-native-    │ │    screens, mostly   │ │  • "webmaf_video_  │ │                      │
│ tvos fork        │ │    player UI)        │ │     player"        │ │                      │
│ (OBSERVED in     │ │  • SwiftUI bundle    │ │                    │ │                      │
│ modules.json).   │ │    (in-progress      │ │                    │ │                      │
│                  │ │    UIKit→SwiftUI     │ │                    │ │                      │
│ But: ZERO        │ │    migration)        │ │                    │ │                      │
│ Platform.OS===   │ │  • PlexMPV.framework │ │                    │ │                      │
│ 'tvos' branches  │ │    (libmpv wrapper)  │ │                    │ │                      │
│ in current iOS   │ │                      │ │                    │ │                      │
│ bundle.          │ │ Apple deprecated     │ │                    │ │                      │
│                  │ │ TVMLKit at WWDC24.   │ │                    │ │                      │
│ Native module:   │ │                      │ │                    │ │                      │
│ packages/player/ │ │                      │ │                    │ │                      │
│ = KSPlayer_      │ │                      │ │                    │ │                      │
│   private fork   │ │                      │ │                    │ │                      │
│ + FFmpeg static  │ │                      │ │                    │ │                      │
│ + libass + Metal │ │                      │ │                    │ │                      │
│                  │ │                      │ │                    │ │                      │
└────┬─────────────┘ └──────────┬───────────┘ └──────┬─────────────┘ └──────────────────────┘
     │                          │                    │
     └──────────────────────────┴────────────────────┘
                                ▲
                Plex API (HTTP / HLS / DASH / WebSocket)


  ⟵ — — — — — INFERRED FUTURE STATE — — — — — →
  Plex's deliberate react-native-tvos choice + the WWDC 2024 TVMLKit
  deprecation strongly suggest the legacy PlexTV codebase will eventually
  be replaced by the react-native-client RN codebase. Today it has not
  happened: the JS bundle has zero tvOS branches, and the leaked native
  paths in the iOS binary show only an apps/plex/targets/native/ios/
  target (no apps/plex/targets/native/tvos/ visible).
```

## Why this split? (Inferred)

Mobile and "TV/desktop/web" have fundamentally different runtime constraints:

| Constraint | Mobile (RN) | TV/Desktop/Web |
|---|---|---|
| Input latency | Tap / gesture must feel native | Remote / mouse / keyboard tolerable |
| Memory / CPU | Constrained (especially older iPhones) | Plentiful (TV SoCs + desktops) |
| OS integration | Deep (Now Playing, AirPlay, PiP, CarPlay) | Shallower for most TVs |
| Update path | Per-OS App Store policies | Web update is instant |
| Codec license | Apple covers many | Plex's own transcoder must cover |
| Container | OS sandbox is tight | Webview is sandboxed by browser engine |
| Code-sharing leverage | RN gives one codebase for iOS/tvOS/Android | One web codebase reaches dozens of platforms |

For mobile, **React Native + native player** maximises share AND keeps native polish. For everything else, **web + adapter pattern** maximises share AND minimises per-platform glue code.

## What's shared, what isn't

### Shared across BOTH client codebases

- The **Plex API contract** (HTTP REST, OAuth, media decision endpoints).
- The **server-driven media decision** (server picks "direct play" vs "direct stream" vs "transcode" based on client-reported capabilities).
- The **HLS / DASH stream format** (transcoded output the client renders).
- The **brand / UX language** (visually consistent; logo, fonts, color tokens — although delivered through different render stacks).

### Shared inside `react-native-client`

`packages/` workspace structure (from compile-time source paths):

```
packages/
├── player/                ← 30 Swift files. The video engine and RN bridge.
├── native-common/         ← shared native helpers (logging, HTTP, local network perms, DNS rebinding)
├── background-downloader/ ← background download service
```

The `apps/plex/targets/native/` directory holds the iOS target. By the structure (singular `apps/plex/`, plural-implying `targets/`), Plex almost certainly has parallel targets for `android/`, possibly `tvos/` (or tvOS handled via `react-native-tvos` from the same iOS target).

Hot-path JS modules visible in the bundle:
- `PlayerEngine`, `MediaDecisionEngine`, `ServerDecisionEngine`, `CloudDecisionEngine` (Plex's stream-selection logic in JS)
- `usePlaybackState`, `usePlayerStateIndicator*`, `useExternalScreenBehaviour`, `usePictureInPicture` (React hooks)
- Components: `BackgroundVideoPlayer`, `DownloadVideoScreen`, `LiveVideoScreen`, `InternalPlayer`

### Shared inside `plex-web`

ONE Webpack bundle (`plex-4.x.y-<hash>`) with 207+ lazy chunks. The same bundle is:

- Hosted at `app.plex.tv` (public web)
- Bundled inside Plex Desktop's `Resources/web-client/`
- Bundled inside PMS's `Plug-ins-<hash>/WebClient.bundle/Contents/Resources/`
- Loaded by Samsung Tizen / LG webOS TV apps (their player adapters are referenced from the same bundle)

The version skew between Desktop (`4.156`) and PMS (`4.159`) is expected — they ship on independent release trains — but the build pipeline is the same (matching Webpack content-hashed chunk names for unchanged code prove this).

### NOT shared

- The **player implementation itself** is per-codebase:
  - RN side: Swift `NativeEngineManager` + KSPlayer fork.
  - Web side: a `"html"|"mpv"|"samsung_avplay"|"webmaf_video_player"` adapter (the actual code per backend is different).
- The **UI rendering layer**:
  - RN side: native views (Fabric, native UIView under the hood).
  - Web side: React DOM in a browser engine.
- **OS integration code** (PiP, AirPlay, MediaSession, Now Playing) is per-platform.

## The "monorepo + workspaces" inference for the RN codebase

The compile-time path `/Users/runner/work/react-native-client/react-native-client/packages/player/...` strongly implies:

- **`/Users/runner/`** — a GitHub Actions runner home (or Azure DevOps). CI builds on a CI runner.
- **`/work/react-native-client/react-native-client/`** — the doubled directory is typical of GitHub Actions `actions/checkout` (it checks out into `_work/<repo>/<repo>/`). Strong CI fingerprint.
- **`packages/`** + **`apps/`** + **`node_modules/`** at the same level — classic **Yarn workspaces** or **PNPM workspaces** layout (a monorepo).
- The repository is **literally named `react-native-client`** — Plex named it after its purpose, not after its product.

This is consistent with the modern best practice for RN monorepos: a single repo, multiple workspaces, multiple platform targets, shared TS/JS packages and shared native modules.

## The "web client is the single source of truth" inference

Three independent artifacts contain the exact same Webpack output structure:

1. Plex Desktop's `Resources/web-client/` (web `4.156.0-4946c98`)
2. PMS's `WebClient.bundle/Contents/Resources/` (web `4.159.0-d0cea4c`)
3. Implied: `app.plex.tv` (publicly accessible, we did not fetch but the same versions presumably ship)

Chunk-hash collisions (e.g., `chunk-1045-77f6dd481485de8601be` appearing identically in both Desktop's `4.156` and PMS's `4.159`) prove these come from the **same Webpack build pipeline** and that *only the changed chunks get new hashes*. This is exactly how Webpack `[contenthash]` caching works.

So the web codebase is one project, built once per release, distributed via three channels:

```
                  ┌────────────────────────┐
                  │   plex-web repo        │
                  │   • React              │
                  │   • Webpack            │
                  │   • Shaka Player       │
                  │   • 4 player adapters  │
                  └─────────┬──────────────┘
                            │ build
                            ▼
                  ┌────────────────────────┐
                  │   Webpack output       │
                  │   • plex-X.Y.Z-<hash>  │
                  │   • 207 lazy chunks    │
                  └─┬───────┬─────────┬────┘
                    │       │         │
              ┌─────▼──┐ ┌──▼────┐ ┌──▼──────────┐
              │ deploy │ │ bundle│ │ bundle into │
              │  to    │ │  into │ │   PMS at    │
              │app.plex│ │  Plex │ │WebClient.   │
              │  .tv   │ │Desktop│ │  bundle/    │
              └────────┘ └───────┘ └─────────────┘
```

## Server-side as integration point

PMS is the **single integration point** between the two client codebases. Every client speaks the same Plex API to it. The "media decision" endpoint is where the server tells the client what stream it can have. Both codebases implement Decision-Engine logic on their side (the JS-side `MediaDecisionEngine` in RN, an equivalent in the Web SPA), but the server is the final arbiter.

This means a feature like "5.1 audio direct-play in tvOS" requires:

1. **PMS** knows the codec compatibility and serves direct-play.
2. **RN tvOS app** has KSPlayer / KSAVPlayer support for 5.1 audio output.
3. **The JS Decision Engine** knows to request direct play if the client capability profile allows it.

But it does NOT require any change to the Web SPA, the Desktop client, or the Smart TV apps. They use their own player adapters and their own audio code paths.

## Open questions (UNKNOWN)

- **Android target structure inside `react-native-client`** — not directly observable.
- **The currently shipping tvOS app IS its own codebase** (PlexTV 8.45, TVMLKit-based) — directly observed by analyzing the tvOS bundle. See chapter 07 for the full evidence. The `react-native-tvos` choice in the iOS app suggests Plex *plans* to absorb tvOS into the RN monorepo, but that has not yet happened.
- **Whether smart TV apps are pure web or have a thin native wrapper** — we observed only the JS side via player-backend constants.
- **Whether there is a separate codebase for Roku / FireTV / consoles** — none of those are referenced from the analyzed artifacts.
- **Sharing between RN's JS layer and Web's JS layer** — both are React, but we found no evidence of shared packages between the two codebases. They appear to be entirely independent at the application level (sharing only the API contract).
