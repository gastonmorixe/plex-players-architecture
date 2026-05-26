---
title: "tvOS — currently shipped TVMLKit app + tvOS-readiness of the iOS RN codebase"
chapter: 7
date: 2026-05-25
artifact: tvos-app/downloads/tvos-via-ipatool-new/383457673_8.45/Payload/PlexTV.app
sha_or_version:
  bundle_id: com.plexapp.plex
  bundle_name: PlexTV
  short_version: "8.45"
  build: "9684"
  min_os: "tvOS 14.5"
  sdk: "appletvos17.2"
  xcode_build: "15C500b"
  built: "early 2024"
status: complete
certainty: high (observed) / clearly-flagged inferences
---

# tvOS — currently shipped TVMLKit app + tvOS-readiness of the iOS RN codebase

## TL;DR

There are **two distinct stories** here, and they need to be told separately:

### A. The Plex tvOS app *currently in the App Store* (PlexTV 8.45, built early 2024)

It is **NOT** React Native. It is a hybrid app built on Apple's now-deprecated **TVMLKit** (TVML markup + TVJS JavaScript) with native **UIKit** screens (31 `.nib` files), a **SwiftUI bundle** (mid-migration), and **mpv** as the playback engine (`PlexMPV.framework`, bundle id `tv.plex.mpv`). It was **literally bootstrapped from Apple's 2015 TVMLKit sample** (the `application.js` file still carries Apple's 2015 sample header).

### B. Plex's iOS RN codebase (Plex 2026.9.0)

It is **set up to target tvOS** — the deliberate use of the `react-native-tvos` fork (vs stock `react-native`) is observed in `modules.json` — but **no application-level tvOS branches have been written yet** (`Platform.OS === 'tvos'` count: zero). The fork choice is a strong intent signal; the absence of `'tvos'` conditionals means the migration has not yet begun in earnest.

Combined picture: **Plex's plan is to migrate tvOS to share the iOS RN codebase**, but the shipped tvOS app today is still legacy TVMLKit. The migration appears to be in *infrastructure-setup* phase, not yet *application-code* phase.

## Part A — The currently shipped tvOS app

### A.1 — Artifact identity

From `Payload/PlexTV.app/Info.plist`:

| key | value |
|---|---|
| `CFBundleIdentifier` | `com.plexapp.plex`  ← same App Store entry as iOS |
| `CFBundleName` | `PlexTV` |
| `CFBundleExecutable` | `PlexTV` |
| `CFBundleShortVersionString` | `8.45` |
| `CFBundleVersion` | `9684` |
| `DTPlatformName` | `appletvos` |
| `DTSDKName` | `appletvos17.2` |
| `DTXcodeBuild` | `15C500b` (Xcode 15.2 / early 2024) |
| `MinimumOSVersion` | `14.5` (tvOS 14.5+) |

**Version skew with iOS is dramatic**: iOS is at `2026.9.0` (built with `iphoneos26.0` SDK — a late-2025/2026 build), tvOS is at `8.45` (built ~18 months earlier with `appletvos17.2`). Same App Store entry, totally different release trains, totally different codebases.

### A.2 — Important caveat: the binary is FairPlay-encrypted

The IPA was downloaded via `ipatool` (App Store), which does NOT decrypt. Verified:

```
otool -arch arm64 -l PlexTV → LC_ENCRYPTION_INFO_64:
  cryptoff   32768
  cryptsize  23773184
  cryptid    1            ← still encrypted
```

This means **we cannot read strings from the `__TEXT` section** of the main binary. However we CAN observe:

- The bundle's filesystem layout (NIBs, JS files, asset bundles) — *not encrypted*
- `Info.plist` files — *not encrypted*
- The Mach-O load commands (dynamic linkage) — *not encrypted*
- Resource bundles (`*.bundle/`, `*.nib`, `js/`, `includes/`) — *not encrypted*

The dynamic linkage alone is sufficient for the architectural conclusions.

### A.3 — Dynamic linkage proves TVMLKit + mpv + FFmpeg + BASS

`otool -L PlexTV` (selected entries):

**Apple frameworks (the TVMLKit stack)**:
```
TVMLKit.framework
TVServices.framework        ← tvOS-specific (Top Shelf, etc.)
JavaScriptCore.framework    ← TVJS executor
AVFoundation.framework
AVKit.framework
```

**Plex's bundled `.framework`s** (all `@rpath/`):
```
PlexMPV.framework            ← the video player engine — libmpv wrapper
                              (bundle id confirmed: tv.plex.mpv)
libavcodec.framework         ┐
libavformat.framework        │
libavutil.framework          │  FFmpeg 5.x as Apple Frameworks
libavfilter.framework        │  (libav*.framework — note: framework
libswscale.framework         │   bundles, not dylibs. tvOS requires
libswresample.framework      ┘   framework packaging.)

bass.framework               ┐  un4seen.com BASS audio library family —
bass_fx.framework            │  used for HI-RES / LOSSLESS music playback.
bass_mpc.framework           │  Plex's "Plexamp-grade" audio backend.
bass_tta.framework           │
bassape.framework            │  (Plex licenses BASS commercially.)
bassdsd.framework            │
bassenc.framework            │  Supported formats:
bassenc_flac.framework       │    APE, DSD, FLAC, HLS, MIDI,
bassflac.framework           │    Opus, WebM, WavPack (WV),
basshls.framework            │    TTA, Musepack (MPC), MIDI,
bassmidi.framework           │    Encoder, Mix, FX
bassmix.framework            │
bassopus.framework           │
basswebm.framework           │
basswv.framework             ┘

tags.framework               ← Plex's own media-tag parsing framework
MUXSDKStats.framework        ┐  Mux Data (mux.com) — video QoE / QoS analytics
MuxCore.framework            ┘
GoogleInteractiveMediaAds.framework   ← Google IMA ad SDK (same as iOS)
```

**Notably ABSENT**:
- No `hermesvm.framework` (no React Native Hermes engine)
- No `RCT*` / `React-*` frameworks
- No `KSPlayer*` (the iOS app's player library)
- No FullStory, Sentry, etc. (the iOS app's analytics stack is different)
- No Vizbee SDK (the iOS app has it; tvOS doesn't seem to use it)
- No KochavaTracker (iOS has it)

This is **conclusively a different application** with a different player engine and a different analytics stack.

### A.4 — TVMLKit JavaScript and XML/XSLT assets

`PlexTV.app/js/` contains 6 JavaScript files plus one dialog template:

```
js/
├── application.js         (3.9 KB)  ← TVMLKit App.onLaunch entry
├── PlexNavigation.js      (2.0 KB)
├── Presenter.js           (17 KB)
├── ResourceLoader.js      (4.4 KB)
├── Utilities.js           (1.5 KB)
└── dialogs/
    └── MediaMenu.xml.js   (7.0 KB)
```

The smoking gun is `application.js`:

```js
//# sourceURL=application.js

/*
Copyright (C) 2015 Apple Inc. All Rights Reserved.
See LICENSE.txt for this sample's licensing information

Abstract:
This is the entry point to the application and handles the initial loading
of required JavaScript files.
*/
var resourceLoader;
var PLEX_SERVER_IDENTIFIER = null;
var PLEX_PROXY_BASE_URL;
...

App.onLaunch = function(options) {
    plexConsole = options.bridgeConsole;
    plexBridge  = options.nativeBridge;
    ...
};
```

**Plex literally started from Apple's 2015 TVMLKit sample template** (the copyright header is preserved verbatim). Over the years they layered on `Presenter.js` and `PlexNavigation.js` for their own application logic, but the bones are Apple's TVMLKit sample from a decade ago.

`PlexNavigation.js` uses TVMLKit's `navigationDocument` global API:
```js
navigationDocument.documents
navigationDocument.removeDocument(navigationDocument.documents[0])
Presenter.loadNewPage(null, null, null, 'Settings', '/private/prefs', getActiveDocument())
```

`PlexTV.app/includes/` contains:

```
Background.xml      (TVML markup — background image element)
Components.xsl      (XSLT 1.0 stylesheet — transforms Plex XML into TVML)
css.xml             (TVML CSS using tv-text-style, tv-text-max-lines, tv-text-highlight-style)
```

The `Components.xsl` is fascinating: it uses **XSLT 1.0 with EXSLT extensions + a Plex namespace** to transform Plex Media Server's XML responses directly into TVML markup at the client. Example template:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:plex="http://plex.tv/plex"
    xmlns:str="http://exslt.org/strings"
    extension-element-prefixes="str plex" >

    <xsl:template name="settingDialog">
        <xsl:attribute name="onselect">
            <xsl:text>mediaDialog.showSetting(this, '</xsl:text>
            <xsl:value-of select="@type" /> ...
```

This means PMS XML → XSLT transform on tvOS → TVML markup → TVMLKit renders it. It's a very 2015-era architecture: server-driven UI via XSLT.

### A.5 — Native UIKit screens (31 NIB files) sit alongside TVMLKit

The bundle has **31 compiled NIBs at the top level** — all named `PTV*.nib` (PlexTV prefix):

```
PTVAudioPlayerLyricsItemViewCell.nib
PTVAudioPlayerLyricsLineViewCell.nib
PTVAudioPlayerLyricsView.nib
PTVAudioPlayerViewController.nib
PTVChapterSelectionViewCell.nib
PTVLiveChannelPlaybackConflictResolutionViewController.nib
PTVLoadingView.nib
PTVMediaSubscriptionViewController.nib
PTVNowPlayingInfoViewController.nib
PTVPhotoGalleryViewController.nib
PTVPinEntryViewController.nib
PTVPlayQueueTableViewCell.nib
PTVPlexPassUpsellPromotionView.nib
PTVPlexPassUpsellViewController.nib
PTVPlexSettingListView.nib
PTVRecordingPriorityTableViewCell.nib
PTVRecordingScheduleTableViewCell.nib
PTVRelatedPhotoHubViewCell.nib
PTVReviewCollectionViewCell.nib
PTVSeasonEpisodeInfoViewCell.nib
PTVServerWhatsNewViewController.nib
PTVSongTableViewCell.nib
PTVTechnicalInfoViewController.nib
PTVUserListViewController.nib
PTVUserPickerViewCell.nib
PTVVideoPostPlayFocusablePlayThumbCell.nib
PTVVideoPostPlayNextView.nib
PTVVideoPostPlayQueueCell.nib
PTVVideoPostPlayReplayOnlyView.nib
PTVVideoPostPlayReplayView.nib
PTVVideoPostPlayReplayView.nib (etc.)
```

The breakdown of these screens reveals the hybrid architecture:

- **Player-related** (most): `PTVAudioPlayer*`, `PTVNowPlayingInfoViewController`, `PTVChapterSelectionViewCell`, `PTVTechnicalInfoViewController`, `PTVVideoPostPlay*` — the entire **video playback UI is native UIKit**, not TVML. This makes sense: TVML's built-in player is limited; serious media apps build native player UIs.
- **Photo gallery**: `PTVPhotoGalleryViewController` — native UIKit.
- **DVR / Live TV scheduling**: `PTVRecordingPriority*`, `PTVRecordingSchedule*`, `PTVLiveChannelPlaybackConflictResolution*` — DVR UI is native.
- **User pickers / PIN entry / subscription upsells**: also native UIKit.

So the architecture split is:
- **TVML pages**: content browsing (libraries, sections, on-deck, search results, hub pages) — server-driven via XSLT.
- **Native UIKit screens (via NIBs)**: playback UI, DVR scheduling, photo gallery, modal flows.

### A.6 — SwiftUI and Plex's design system bundles

Three sibling resource bundles at the top level:

```
ChromaUI_ChromaUI.bundle/             ← Plex's design system (matches the
                                        "chroma" workspace name seen in iOS RN bundle)
PlexCoreUILegacy_PlexCoreUILegacy.bundle/  ← "Legacy" UI bundle
PlexSwiftUI_PlexSwiftUI.bundle/       ← SwiftUI bundle — newer screens
```

The `_X.bundle/X` naming convention is characteristic of **Swift Package Manager** resources (when SPM packages have resources, they get this `XXX_XXX.bundle` double-name treatment in the consuming app).

The juxtaposition of `*Legacy*` and `*SwiftUI*` bundles strongly implies an **in-progress UIKit-NIB → SwiftUI migration**, separate from any planned TVMLKit → RN migration. So Plex tvOS has two migrations queued:

1. The micro one: UIKit NIBs → SwiftUI (already in progress in 8.45)
2. The macro one: TVMLKit → React Native (not yet shipped, but the iOS codebase is being prepared — see Part B)

### A.7 — The player: `PlexMPV.framework`

`PlexMPV.framework/Info.plist`:

```xml
CFBundleExecutable          PlexMPV
CFBundleIdentifier          tv.plex.mpv
CFBundlePackageType         FMWK
CFBundleShortVersionString  1.0.0
MinimumOSVersion            14.5
```

The framework binary itself (`PlexMPV.framework/PlexMPV`, 3.7 MB) has its own FairPlay encryption marker:

```
SC_Info/
├── PlexMPV.supf
├── PlexMPV.supp
└── PlexMPV.supx
```

`SC_Info/*` files (Apple's name: "supplemental code-signing"; also where FairPlay key material lives for separate-app DRM'd dylibs) indicates the framework binary is **separately encrypted** and we can't read its strings. But the framework's *name* (`PlexMPV`), bundle id (`tv.plex.mpv`), and the fact that **the main binary's dynamic linkage references this framework** is conclusive evidence Plex ships a libmpv wrapper on tvOS.

This is consistent with public statements (2018–2021 Plex forum posts and blog write-ups confirming "Plex Beta introduces mpv as video player ... iOS and Apple TV apps"). On tvOS the mpv-based "Enhanced Video Player" stuck. **On iOS, by contrast, the current 2026.9.0 build has *dropped* libmpv in favor of a KSPlayer fork — see chapter 01** — so the two clients diverged.

### A.8 — Other bundled support

`PlexTV.app/` top-level resources of note:

- **`Acknowledgements.md`**, **`Acknowledgements.xslt`** — open-source license attribution (consumed via XSLT into a TVML acknowledgements page)
- **`default.metallib`** — Metal shader library (for hardware video rendering)
- **`PingFang Regular.ttf`** — Chinese font (same as iOS app's KSPlayer bundle — for Chinese subtitle rendering)
- **`empty.mp3`** — silent audio (likely a playback placeholder)
- **`LaunchScreen.storyboardc`** — launch screen
- **`Settings.bundle`** — iOS/tvOS Settings.app integration
- **`PMKDefaultAppSettings.plist`** + **`DefaultAppSettings.plist`** — default settings
- **Localization**: `af-ZA.lproj`, `bg.lproj`, `cs.lproj`, ..., 30+ locales

## Part B — Is the iOS RN codebase tvOS-ready?

This is the more nuanced question, and it deserves a careful answer.

### B.1 — OBSERVED: Plex uses `react-native-tvos`, not stock `react-native`

`Payload/Plex.app/modules.json` (Plex iOS 2026.9.0) — direct file contents:

```json
{
  "react-native-tvos": "0.83.4-2",
  "@react-native-tvos/virtualized-lists": "0.83.4-2",
  ...
}
```

There is **NO** plain `react-native` entry. The fork is the one being used.

Per the `react-native-tvos` README (verified locally at `research/react-native/react-native-tvos/README.md`):

> "Apple TV and Android TV support for React Native are maintained here ... This is a **full fork** of the main repository ... To build your project for Apple TV, you should change your package.json imports to import react-native as follows ... `"react-native": "npm:react-native-tvos@latest"` ... **You cannot use this package and the core react-native package simultaneously in a project.**"

So this is an unambiguous, deliberate choice. Plex picked the fork **knowing they can't dual-use** with stock RN. The cost: they lag the stock RN release cadence and inherit any fork bugs.

### B.2 — OBSERVED: tvOS API exports are present in the bundle

The Hermes bytecode bundle (`main.jsbundle`) contains string-table entries for the tvOS-specific APIs that `react-native-tvos` exports:

```
get TVEventHandler
get useTVEventHandler
get TVFocusGuide / TVFocusGuideView
get TVEventControl
get TVMenuControl
```

Plus the prop-name strings:

```
nextFocusUp, nextFocusDown, nextFocusLeft, nextFocusRight, nextFocusForward
tvParallaxProperties, tvFocusable, hasTVPreferredFocus, isTVSelectable
```

These strings are present because the `react-native-tvos` package is bundled — it exports them whether the application uses them or not. **Their presence proves only that the fork is bundled, not that Plex's app code calls them.**

### B.3 — OBSERVED: no application-level `Platform.OS === 'tvos'` branches yet

Direct grep on `main.jsbundle` string table:

| Comparison | Occurrences |
|---|---:|
| `Platform.OS === 'ios'` | 1 |
| `Platform.OS === 'android'` | 3 |
| `Platform.OS === 'web'` | 1 |
| `Platform.OS === 'macos'` | 0 |
| `Platform.OS === 'tvos'` | **0** |

(Note: Hermes string-table entries are deduplicated, so 1 means "this comparison appears in the source — possibly in 1 or many places".)

Plex's code is platform-conditional for iOS / Android / web, but **not yet for tvOS**. There are zero `'tvos'` literal comparisons in the bundle.

### B.4 — OBSERVED: no `packages/player/tvos/` and no `apps/plex/targets/native/tvos/`

The compile-time path leaks in the iOS native binary show only these workspaces from the `react-native-client` monorepo:

```
packages/player/ios/             (30 files — present)
packages/native-common/ios/      (4 files)
packages/background-downloader/ios/ (4 files)
apps/plex/targets/native/ios/    (present, the iOS target)
```

There is **no** corresponding `packages/player/tvos/` or `apps/plex/targets/native/tvos/` in this binary's leaked paths. (Of course, those would only be visible if they had compiled into the iOS binary — they wouldn't. But neither does any compile-time evidence of a parallel tvOS target structure surface.)

### B.5 — Honest interpretation: intent set, code not yet written

Putting B.1 + B.2 + B.3 + B.4 together:

- ✅ **Plex has set up the deps** to make tvOS RN possible (using the fork).
- ✅ **The fork's TV-specific APIs are bundled** (because the fork is bundled).
- ❌ **Plex's own JS code does not yet branch on tvOS** (zero `Platform.OS === 'tvos'`).
- ❌ **The monorepo's native side has no tvOS target visible** in this iOS binary's leaks.

**The strongest defensible claim**: Plex's iOS RN codebase is set up to *enable* a future tvOS target, but the actual tvOS application code has not yet been written (or at least, has not yet shipped) as of the analyzed builds.

**Alternative interpretation worth considering**: Plex might have switched to `react-native-tvos` for **Android TV support** rather than (or in addition to) Apple TV. The fork supports both. Without observing an Android variant of the app, we cannot distinguish. But given:

- The currently shipped tvOS app is on a legacy stack that Apple has deprecated (WWDC 2024 announced TVMLKit deprecation — see `apple-platform/WWDC/WWDC2024-10207-Migrate-TVML-app-to-SwiftUI.md` locally).
- The tvOS Plex app on the App Store hasn't been *meaningfully updated* in ~18 months (8.45 from early 2024).
- The iOS app is on a much faster release cadence (versions 2026.x).

…the most plausible interpretation is that **Plex is preparing the iOS RN codebase to replace the tvOS TVMLKit app**, and the migration is in early/structural phase.

### B.6 — What's hidden vs what's missing

A reader might ask: "Could there be tvOS code that's just not visible in this build?" Yes:

- The iOS binary only contains code that was compiled INTO the iOS target. tvOS-only source files (e.g., a hypothetical `packages/player/tvos/Player.swift`) wouldn't show up in `apps/plex/targets/native/ios/` build output.
- Plex's *JS* code, however, would mostly be shared across iOS and tvOS targets (only platform-specific branches differ). The Hermes JS bundle in the iOS app IS that shared JS. So the absence of `Platform.OS === 'tvos'` checks in this bundle is *strong* evidence that the *JS layer* has not yet been tvOS-conditionalised.
- It's possible Plex has a separate tvOS Metro bundle config that produces a different JS bundle with tvOS branches. But normally RN projects ship one JS bundle per platform target, and any conditional code is in the same source files.

So: **the JS layer has not yet been written for tvOS**, with high certainty. The native module layer is *probably* not yet written either (no `packages/*/tvos/` leaks), but a separate tvOS target build could exist without us seeing it.

## The two Plex tvOS narratives, side-by-side

```
                    Currently shipped              Likely future
                    on the App Store               (in setup phase)
                    ────────────────────           ─────────────────────
Codebase            PlexTV repo (legacy)           react-native-client
                                                   (the iOS RN monorepo)

UI                  TVMLKit (TVML + TVJS) +        React Native + JS
                    UIKit NIBs +                   (using react-native-tvos
                    SwiftUI bundle                  fork's TV APIs)
                    (mid-migration UIKit→SwiftUI)

Player engine       PlexMPV.framework              ??? (unknown — could
                    (libmpv wrapper)               extend KSPlayer fork to
                                                   tvOS, could keep mpv via
                                                   a tvOS-specific module,
                                                   could go AVKit-only)

Asset pipeline      Apple's 2015 TVMLKit sample    Webpack-like Metro bundle
                    + XSLT transforming PMS XML     (same as iOS app)

Build version       PlexTV 8.45 (early 2024,       (not yet observed)
                    Xcode 15.2)

Status              On a deprecation path          Infrastructure set up
                    (Apple deprecated TVMLKit at   (`react-native-tvos`
                    WWDC 2024)                     dependency present),
                                                   application code not
                                                   yet written
```

## Methodology notes specific to tvOS

1. **The IPA was not decrypted.** Source: `ipatool` downloads encrypted IPAs from the App Store. `cryptid: 1` on the main binary and on `PlexMPV.framework/PlexMPV` confirms this. To inspect strings/symbols inside the binaries, we'd need a jailbroken-device dump (`frida-ios-dump` or similar). We did not perform that step — and we did not need to, because:
   - Dynamic linkage load commands are **not** encrypted (`otool -L` works).
   - Resource files (NIBs, XML, JS, bundles) are **not** encrypted.
   - Info.plists are **not** encrypted.

2. **The iOS bundle (which IS decrypted) was the source of truth for Part B**. That bundle's `modules.json`, `main.jsbundle` string table, and compile-time source path leaks gave us conclusive evidence about the RN setup. No new tooling was needed.

3. **Local docs at `research/react-native/react-native-tvos/README.md`** and `research/apple-platform/WWDC/WWDC2024-10207-Migrate-TVML-app-to-SwiftUI.md` provided the third-party context (what `react-native-tvos` is; what Apple announced about TVMLKit deprecation).

## Updates to earlier chapters

The following claims in earlier chapters need to be updated for honesty:

- **chapter 00 / 01 / 05** earlier said "the iOS RN app targets tvOS via `react-native-tvos`" — this was **partially inferred**. The correct claim is: "*the iOS app depends on the `react-native-tvos` fork* (OBSERVED in `modules.json`), which is *a deliberate setup choice that enables a future tvOS target* (INFERRED), but *the currently-shipped Plex tvOS app today is a different, legacy TVMLKit codebase* (OBSERVED in `PlexTV.app`)."
- **chapter 05** said the RN monorepo "almost certainly" has a tvOS target — that was speculation. The currently-observable evidence is that the iOS target exists and the tvOS RN target does not yet ship.

See chapters 01 and 05 for inline annotations of these corrections.
