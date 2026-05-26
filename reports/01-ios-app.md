---
title: "iOS / tvOS — React Native app with KSPlayer-fork player"
chapter: 1
date: 2026-05-24
artifact: com.plexapp.plex-2026.9.0-Decrypted.ipa
sha_or_version:
  bundle_id: com.plexapp.plex
  short_version: "2026.9.0"
  build: "1704"
  min_os: "iOS 16.0"
  sdk: "iphoneos26.0"
  xcode_build: "17A400"
status: complete
certainty: high
---

# iOS / tvOS — React Native app with KSPlayer-fork player

## TL;DR

Plex's iOS app (and, by inference, tvOS) is a **React Native 0.83 application with the new architecture (Fabric + TurboModules)**, running on **Hermes**. The video player is **NOT** an off-the-shelf RN library. It is a **custom Plex-owned RN native module** (`packages/player/`) that wraps a **private fork of [KSPlayer](https://github.com/kingslay/KSPlayer)** called `KSPlayer_private`. KSPlayer in turn offers two playback engines:

- **`KSAVPlayer`** — a thin AVPlayer wrapper (used when the asset is directly playable by AVFoundation).
- **`KSMEPlayer`** — a custom "Media Engine" built on **statically-linked FFmpeg 5.x** with **libass** subtitle rendering, **Metal**-based video output, and a choice of four CoreAudio output backends.

There is **no `libmpv`** in the iOS binary, contrary to several public blog posts from 2018–2021. Plex changed direction.

## How we know — evidence trail

### 1. The app is React Native

**OBSERVED** evidence in `Payload/Plex.app/`:

| Indicator | Evidence |
|---|---|
| RN JS bundle | `main.jsbundle` — 20.8 MB Hermes bytecode |
| Hermes engine linked | `Frameworks/hermesvm.framework`, `otool -L Plex` shows `@rpath/hermesvm.framework/hermesvm` |
| RN module manifest | `modules.json` lists 200+ packages including `react-native-tvos@0.83.4-2`, `react@19.2.4`, `react-native-reanimated@4.2.3`, `@shopify/flash-list@2.3.1`, `@tanstack/react-query@5.90.21`, `zustand@5.0.11` |
| RN Pods present | Source path leaks for `Pods/RCT-Folly/`, `Pods/Sentry/`, `Pods/glog/` |
| Fabric / TurboModules | Source path leaks for `Pods/Headers/Private/React-Fabric/react/renderer/...`, plus C++ symbols for `facebook::react::ObjCInteropTurboModule`, `ObjCTurboModule`, `TurboModuleConvertUtils` |
| RN privacy bundles | 12+ `*_privacy.bundle` directories required by Apple Privacy Manifests for `React-Core`, `React-cxxreact`, `RCT-Folly`, `Lottie_React_Native`, `RNCAsyncStorage`, `RNDeviceInfo`, `RNFS`, `RNImagePicker`, `RNPermissions`, `RNSVGFilters`, `boost`, `glog`, `nanopb`, `RCT-Folly`, `SDWebImage`, `Sentry`, `SSZipArchive` |
| RN component assets | `assets/____packages/`, `assets/____node_modules/`, `assets/__app/` directories with `.png`/`.webp`/`.ttf` resources referenced by JS bundle |

Hermes bytecode header confirms version: `0xc6 0x1f 0xbc 0x03 0xc1 0x03 0x19 0x1f` → Hermes bytecode version 96 (corresponds to recent RN, ~0.79+).

### 2. The repo is `react-native-client` — a Yarn/PNPM monorepo

**OBSERVED** in compile-time source paths embedded in the binary (recovered with `strings -a Plex | rg -o '/Users/runner/.*\.(swift|m|mm|h|cpp)'`):

```
/Users/runner/work/react-native-client/react-native-client/
├── apps/plex/targets/native/ios/          ← the iOS app target
│   ├── Pods/  (CocoaPods third-party native deps)
│   └── build/generated/ios/ReactCodegen/  (RN codegen output)
├── packages/
│   ├── background-downloader/ios/         (4 files: ConnectionTestingService, DownloadsService, NetworkService, RNBackgroundDownloader)
│   ├── native-common/ios/                 (4 files: DNSRebindingProtection, HTTPServer, RNLocalNetworkPermission, RNLogger)
│   └── player/ios/                        (30 files — see below)
└── node_modules/
    ├── react-native/  (React, ReactCommon, Libraries)
    ├── react-native-{gesture-handler, screens, share, svg, vizbee-*}/
    ├── @react-native-{async-storage, community/datetimepicker, google-signin}/
    ├── @d11/react-native-fast-image
    └── @fullstory/react-native
```

The `apps/plex/targets/native/` path *suggests* sibling targets for other platforms (Android, possibly tvOS). **However**, only the `ios/` target's compiled artifacts are observable in this binary; sibling target directories are *inferred*, not directly observed. The repo name `react-native-client` and the `react-native-tvos` dep version both confirm Plex's deliberate choice of the **tvOS-capable** fork of React Native as the cross-platform mobile framework — but as documented in chapter 07, **the currently shipping tvOS Plex app is a separate legacy TVMLKit codebase**, and Plex's iOS RN code does **not** yet contain any `Platform.OS === 'tvos'` branches. The fork choice is a strong intent signal for a future tvOS RN migration, not evidence that the migration has already occurred.

### 3. The video player is a Plex-owned native module that vendors a KSPlayer fork

**OBSERVED** files in `packages/player/ios/` (all 30 compiled-in files):

```
avplayer/
├── ads/AdsManager.swift                   (ad slot manager, paired with Google IMA SDK)
├── Player.swift                            (top-level player orchestration)

common/
├── ExternalScreenManager.swift             (AirPlay external display routing)
├── PictureInPictureManager.swift           (PiP container)
├── PictureInPictureNotifier.swift          (PiP state events)

KSPlayer_private/Sources/KSPlayer/         ← FORKED KSPlayer
├── APPlayer/
│   └── FFmpegWrapper.swift                 (low-level FFmpeg C-API wrapper)
├── AVPlayer/
│   ├── KSAVPlayer.swift                    (AVPlayer-backed engine)
│   ├── KSOptions.swift                     (engine config)
│   └── KSPlayerLayer.swift                 (player view layer)
├── Libass/
│   ├── ASSLibraryWrapper.swift             (libass C-API binding)
│   └── ASSSubtitlesRenderer.swift          (renders ASS/SSA subtitles)
├── MEPlayer/                               ← The "Media Engine" — Plex's custom FFmpeg-based player
│   ├── KSMEPlayer.swift                    (top-level ME player)
│   ├── MEPlayerItem.swift                  (an item in the queue)
│   ├── MEPlayerItemTrack.swift             (per-stream track)
│   ├── FFmpegDecode.swift                  (decoder pipeline)
│   ├── SubtitleDecode.swift                (subtitle decoder)
│   ├── Resample.swift                      (audio resampling via libswresample)
│   ├── AVFFmpegExtension.swift             (FFmpeg helpers)
│   ├── MetalPlayView.swift                 (Metal-based video renderer)
│   ├── AudioEnginePlayer.swift             (audio backend #1 — AVAudioEngine)
│   ├── AudioGraphPlayer.swift              (audio backend #2 — AUGraph)
│   ├── AudioRendererPlayer.swift           (audio backend #3 — AVSampleBufferAudioRenderer)
│   └── AudioUnitPlayer.swift               (audio backend #4 — direct AudioUnit)
├── Metal/
│   └── PixelBufferProtocol.swift           (CVPixelBuffer abstraction)
└── Subtitle/
    └── PingFangFontRegister.swift          (registers Chinese PingFang font)

ksplayer/
└── KSPlayerVideoPlayer.swift               ← Plex's adapter over KSPlayer

react/
├── NativeAVRoutePickerManager.swift        ← RN bridge: AirPlay route picker
└── NativeEngineManager.swift               ← RN bridge: the player engine (THE bridge)

seek-preview/
├── BIFDecoder.swift                        (decodes Plex BIF thumbnail strips)
└── BIFParser.swift                         (parses BIF container)
```

**The KSPlayer fork name `KSPlayer_private`** (rather than `KSPlayer`) is observable in every compile-time path leak. This is consistent with the standard vendoring pattern (private fork to avoid public name collision in dependency resolution).

**Plex's own subclass `PlexKSOptions`** appears in the binary's class strings — Plex overrides KSPlayer's options to inject Plex-specific defaults.

### 4. FFmpeg is statically linked into the main Plex binary

**OBSERVED**:

- `otool -L Plex` shows **no** `libavcodec.dylib` / `libavformat.dylib` / `libmpv.dylib` / `libvlc.dylib` references. The dynamic linkage is only to Apple system frameworks plus a handful of third-party `.framework` bundles.
- However, the strings dump shows **181 hits** for FFmpeg source file paths (`src/libavcodec/...`, `src/libavformat/...`, etc.) and **27 hits** for FFmpeg API symbols (`avcodec_open2`, `AVCodecContext`, `AVHWFramesContext`, …).
- This means FFmpeg is **statically linked** into the Plex binary, not loaded as a dylib. This is consistent with iOS App Store rules (apps used to ship dylibs; today they prefer static linkage for non-system libs).
- Notable FFmpeg source files compiled in: `audiotoolboxdec.c` — confirms VideoToolbox / AudioToolbox **hardware decoder** wrapper is enabled (Plex uses hardware decode on iOS via FFmpeg's AT decoder + native VideoToolbox calls).

### 5. mpv is NOT in the iOS binary

**OBSERVED**:

- `strings -a Plex | rg -i '\bmpv\b|libmpv|mpv_'` returns **zero** hits (the only matches are inside FFmpeg source paths like `mpv-style profile`, which are configuration strings, not symbols).
- No `libmpv.dylib`, no mpv-* symbols, no `mpv_` API surface.
- This **contradicts** several public blog posts from 2018–2021 that claimed Plex switched iOS/tvOS to mpv. **Plex changed direction**: the current 2026.9.0 build uses KSPlayer + FFmpeg, not mpv.

### 6. The RN ↔ native bridge

**OBSERVED** TurboModule fingerprints in the binary:

- `NativeEngineManager` (Swift class registered as RN TurboModule)
- `NativeAVRoutePickerManager` (Swift class registered as RN TurboModule)
- `NativePictureInPictureManager` (referenced as concatenated string in the JS bundle's TurboModule registry)
- The web-side JS modules reference these names. Example string in `main.jsbundle`:
  ```
  NativeEngineManagerror ... NativeAVRoutePickerManagerz ... NativePictureInPictureManager ...
  ```
  (concatenated minified property keys)

The JS-side API surface (player React hooks and components — observable in the JS bundle string tables) includes:

- `usePlayerState`, `usePlaybackState`, `usePlaybackError`, `usePlaybackOptionsScreen`, `usePlaybackProfile`, `usePlayQueueItems`
- `usePlayerStateIndicatorPlayPauseInterceptor`, `usePlayerStateIndicatorForwardBackward`, `usePlayerStateIndicatorSeekForward`, `usePlayerStateIndicatorSeekLabel`, `usePlayerStateIndicatorPauseAdView`
- `BackgroundVideoPlayer`, `DownloadVideoScreen`, `LiveVideoScreen`, `InternalPlayer`
- `PlayerEngine`, `MediaDecisionEngine`, `ServerDecisionEngine`, `CloudDecisionEngine`
- `useExternalScreenBehaviour` (AirPlay hook)

These names suggest the **JS side** owns:

- The player UI (controls, transport, scrubber).
- "Decision engines" — Plex's logic that picks the right stream (direct play vs direct stream vs transcode) given client capabilities and server caps.
- State management (Zustand + React Query are present in deps).

The **native side** owns: the actual decode/render/audio output pipeline.

### 7. Dynamic linkage — the full ecosystem

`otool -L Plex` (108 entries total) — selected highlights:

**Apple media / playback frameworks** (the platform side):
```
AVFoundation, AVKit, AVFAudio, AudioToolbox, CoreMedia, CoreVideo,
VideoToolbox, MediaPlayer, MediaAccessibility, MetalKit, Metal, IOSurface,
QuartzCore
```

**Plex's bundled third-party `.framework`s** (all `@rpath/`):
```
hermesvm.framework            ← React Native Hermes JS engine
GoogleCast.framework          ← Chromecast SDK
GoogleInteractiveMediaAds.framework  ← IMA ad SDK
KochavaCore.framework, KochavaTracker.framework  ← attribution analytics
VizbeeKit.framework, VizbeeHomeOSKit.framework, VizbeeHomeSSOKit.framework  ← smart-TV cast + SSO
FullStory.framework           ← analytics / session replay
```

**Apple Swift runtime**: `libswiftCore`, `libswiftAVFoundation`, `libswiftAccelerate`, `libswiftCompression`, etc.

**System libs**: standard set (`libc++`, `libobjc`, `libSystem`, `libsqlite3`, `libxml2`, `libz`, `libiconv`, `libcompression`).

### 8. Notable bundled resources

- `Assets.car` (3.8 MB) — compiled asset catalog
- `KSPlayer_KSPlayer.bundle/` — KSPlayer resources (`default.metallib`, `PingFang Regular.ttf`, `Shaders.dat`)
- `LaunchScreen.storyboardc` — the only storyboard (just for app launch)
- `GoogleService-Info.plist` — Firebase config
- `FullStory.json` — FullStory config (36 KB)
- `PrivacyInfo.xcprivacy` — Plex's Apple Privacy Manifest
- `plex-icons.ttf`, `PlexCircular-Bold.ttf`, `InterDisplay-*.ttf` — fonts

The `LaunchScreen.storyboardc` being the only storyboard is consistent with RN apps: launch screen is native, everything else is React-rendered.

## Architecture summary

```
                            ┌──────────────────────────────────────────────┐
                            │     React Native (Hermes JS, 20.8 MB)        │
                            │                                              │
                            │   • Player UI components                      │
                            │   • State (Zustand) + React Query             │
                            │   • Media Decision Engines (JS)               │
                            │   • Hooks: usePlaybackState, usePlayer…       │
                            └─────────────┬────────────────────────────────┘
                                          │  TurboModule bridge
                                          │  (JSI → Swift)
                            ┌─────────────▼────────────────────────────────┐
                            │  NativeEngineManager.swift  (RN native module)│
                            │  NativeAVRoutePickerManager.swift             │
                            │  NativePictureInPictureManager.swift          │
                            └─────────────┬────────────────────────────────┘
                                          │
                            ┌─────────────▼────────────────────────────────┐
                            │  KSPlayerVideoPlayer.swift  (Plex adapter)    │
                            │  + PlexKSOptions (Plex's config subclass)     │
                            └────┬───────────────────────────────────┬─────┘
                                 │                                   │
                  ┌──────────────▼──────┐               ┌────────────▼──────────────────┐
                  │  KSAVPlayer         │               │   KSMEPlayer (Media Engine)    │
                  │  (uses AVPlayer)    │               │                                │
                  │                     │               │   FFmpegDecode ──┐             │
                  │  AVPlayer →         │               │                  │             │
                  │   VideoToolbox HW   │               │   FFmpeg ────────┘             │
                  │   AudioToolbox      │               │   (static, no dylib)           │
                  │                     │               │      │                         │
                  │  Used for           │               │      ├──► MetalPlayView        │
                  │  "directly playable"│               │      │    (Metal video render) │
                  │  assets             │               │      │                         │
                  │                     │               │      ├──► libass (subtitles)   │
                  └─────────────────────┘               │      │                         │
                                                        │      └──► One of 4 audio       │
                                                        │           backends:            │
                                                        │           • AudioEnginePlayer  │
                                                        │           • AudioGraphPlayer   │
                                                        │           • AudioRendererPlayer│
                                                        │           • AudioUnitPlayer    │
                                                        └────────────────────────────────┘
```

## Open questions (UNKNOWN / not investigated)

- **Android target?** *Inferred* from the monorepo naming + `react-native-tvos` (which supports Android TV) but not directly observable in this artifact.
- **tvOS RN target?** *Inferred to be planned* from the deliberate `react-native-tvos` dependency choice — but the currently shipping tvOS Plex app (`PlexTV.app` 8.45) is a separate **legacy TVMLKit** codebase (see chapter 07 for the full evidence). The iOS RN bundle has the tvOS-fork APIs exported but **zero `Platform.OS === 'tvos'` branches in Plex's application code**. So: setup done, code not yet written.
- **NativeEngineManager method signature?** Would require recovering Swift class metadata from the binary. Names visible, methods not.
- **How JS decides between KSAVPlayer and KSMEPlayer?** The JS likely passes a flag through `NativeEngineManager` based on the media decision result. The user-facing setting is historically called "Use Old Video Player" (which corresponds to KSAVPlayer).
- **react-native-video / expo-av usage?** None observed. The native module is fully in-house.
