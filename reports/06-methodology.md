---
title: "Methodology — how the binaries gave up the architecture"
chapter: 6
date: 2026-05-24
status: complete
---

# Methodology — how the binaries gave up the architecture

## Inputs

Three artifacts from `plex-binaries/`:

| File | Size | Type |
|---|---|---|
| `com.plexapp.plex-2026.9.0-Decrypted.ipa` | 57 MB | Decrypted iOS IPA |
| `Plex-1.112.0.359-0d79a49f-universal.app` | ~150 MB | macOS desktop app bundle |
| `PlexMediaServer-1.43.2.10687-563d026ea-universal.app` | ~400 MB | macOS PMS server bundle |

The **decrypted** IPA is critical — encrypted iOS binaries hide most of the strings until decrypted via a jailbroken-device dump (e.g., `frida-ios-dump`). With a decrypted IPA, every string in the `__cstring` section is observable.

## Toolchain

All inspection ran on macOS with standard developer tools — no special infrastructure:

| Tool | Purpose |
|---|---|
| `unzip` | Extract IPA |
| `plutil` | Parse Info.plist |
| `file` | Identify binary type / arch |
| `otool -L` | Dynamic library linkage |
| `nm -gU` | Exported symbols |
| `strings -a` | Dump all ASCII / Unicode strings |
| `rg` (ripgrep) | Fast regex search across multi-MB string dumps |
| `fd` | File enumeration |
| `jq` | Sometimes used for structured output |
| `Plex Transcoder -version` | (The transcoder is a CLI — running it spills the FFmpeg `configure` line) |
| `head` / `sed` / `awk` | Bound output |

No disassembler (e.g., Ghidra, radare2) was needed for this scope. Everything was recovered from strings + symbol tables + dynamic linkage. Sometimes the simplest tool is the best tool.

## Approach (in order of evidence yield)

1. **`file` + `otool -L` first**. Dynamic library linkage is the cheapest, highest-signal evidence about a binary's stack. In one command we knew:
   - macOS Desktop is Qt 6 + libmpv + FFmpeg.
   - PMS uses Boost + libpion + OpenCV + TF Lite + Python 2.7.
   - iOS links Hermes (proving React Native).

2. **`Info.plist` and bundle id**. Bundle IDs (`com.plexapp.plex`, `tv.plex.desktop`, `com.plexapp.plexmediaserver`) confirm we're looking at the right products. SDK versions, minimum OS, Xcode build numbers all came from here.

3. **Look at the bundle's files and folders**. The presence of `main.jsbundle` + `hermesvm.framework` + `modules.json` was conclusive for React Native. The presence of `Resources/web-client/` + `mpv.conf.sample` was conclusive for Qt+Web+mpv.

4. **`strings -a` and then mine with `rg`**. The huge wins:
   - **Compile-time source path leaks** in debug info: `/Users/runner/work/react-native-client/react-native-client/packages/player/ios/KSPlayer_private/Sources/...` told us the repo name, the monorepo structure, the player module structure, and even the fork name in one match.
   - **API symbol fingerprints**: `avcodec_open2`, `AVCodecContext`, `mpv_*`, `shaka.*`, `QWebChannel`, `RCT*`, `TurboModule` — each is a load-bearing identifier you can search for to confirm/refute a hypothesis instantly.
   - **String constants in JS bundles**: `const n="html", i="mpv", s=[n,i,"samsung_avplay","webmaf_video_player"]` — JS minification doesn't touch string contents, only identifiers, so meaningful string literals survive.

5. **Run the binary if it's a CLI**. `Plex Transcoder -version` printed the *entire* FFmpeg `./configure` line — easily 200 flags, including `--enable-eae`, the build path inside `actions-runner/_work/plex-conan/`, every Conan-managed library and its version. This is one of the highest-signal-per-effort moves available.

6. **Compare versions across artifacts**. PMS bundles `plex-4.159` Web app, Desktop bundles `plex-4.156`. Matching Webpack chunk hashes across the two versions proved both come from the same build pipeline. This is forensics by *content-hash collision*.

## Certainty levels per claim

(Per the reverse-engineer skill's discipline: every claim has a tag.)

### OBSERVED (direct binary evidence)
- iOS app uses React Native (Hermes framework + main.jsbundle + RN privacy bundles + modules.json with `react-native-tvos@0.83.4-2`).
- iOS player module path: `packages/player/ios/KSPlayer_private/Sources/...` (compile-time path leaks).
- iOS RN bridge classes: `NativeEngineManager`, `NativeAVRoutePickerManager`, `NativePictureInPictureManager` (string table).
- iOS does **NOT** ship libmpv (zero `mpv_*` symbols in strings).
- iOS does ship FFmpeg statically (181 source-path hits, 27 API symbol hits).
- macOS Desktop links Qt 6.2.4 + libmpv 2.0 + FFmpeg 5.x (otool -L).
- macOS Desktop bundles the Plex Web SPA (`Resources/web-client/index.html` + 207 chunks).
- macOS Desktop's web bundle is Qt-aware (loads `qrc://...qwebchannel.js`).
- Plex Web has a 4-backend selector (`["html","mpv","samsung_avplay","webmaf_video_player"]`).
- Plex Web uses QtWebChannel when running in Qt (`new window.QWebChannel(window.qt.webChannelTransport, ...)`).
- Plex Web includes Shaka Player in a lazy chunk (`chunk-7065-…`, ~800 KB).
- PMS uses a custom FFmpeg fork (Plex Transcoder -version output).
- PMS uses `--enable-eae` for Dolby codecs (same).
- PMS uses Conan + Plex clang (path leaks).
- PMS bundles the Plex Web client (`WebClient.bundle`).

### INFERRED (one logical step from observed)
- The Plex iOS app's `apps/plex/targets/native/` structure implies sibling targets for Android / tvOS that we don't have in this artifact.
- The web client's 4-backend abstraction implies all four backend implementations exist somewhere in the bundle (we only deep-dived into html / mpv).
- The `react-native-tvos` dep implies the tvOS app is the same RN codebase as iOS.
- The PMS-bundled Web client at `WebClient.bundle` implies `http://<server>:32400/web/` serves it (standard PMS behaviour).

### UNKNOWN (not investigated / not in artifacts)
- The Plex Android app's exact RN setup.
- The Smart TV (Tizen / webOS) app shells — only the web-side adapter constants visible.
- The exact Shaka Player version (minified bundle).
- The full diff of Plex's FFmpeg fork vs upstream.
- Plex's clang fork content.
- The `NativeEngineManager` method signatures (would need Swift metadata recovery).
- Whether there is a separate native player for Roku / consoles.

## What we did not need to do

- **No disassembly**. We didn't run Ghidra or radare2. Plex's binaries leak enough structural evidence in strings and dynamic linkage that disassembly was unnecessary for the architectural questions.
- **No dynamic instrumentation**. We didn't run any binary in a sandbox (except `Plex Transcoder -version` which is harmless). No Frida, no LLDB.
- **No source access**. Everything was deduced from compiled artifacts.

If the questions had been more specific (e.g., "what is the exact protocol message format for NativeEngineManager.openMedia?") we would have needed disassembly. For the architectural questions in scope, strings + linkage + bundle layout was sufficient.

## Time and tool spend

The whole investigation took ~30 minutes of tool time:

- ~5 min: initial orientation and tool check.
- ~5 min: extract IPA, inventory all 3 bundles.
- ~5 min: iOS strings dump + grep passes.
- ~5 min: macOS Desktop linkage + web-client inspection.
- ~5 min: PMS linkage + transcoder version + Plug-ins inspection.
- ~5 min: cross-bundle version comparison + synthesis.

The report writing took longer than the analysis — which is the right ratio.

## Reproducing the analysis

To verify or extend, the artifacts and findings tree are self-contained:

```
plex-player-reverse-engineering-research/
├── PROGRESS.md                          # the research log
├── findings/
│   ├── ios/                             # iOS strings, symbol dumps, otool output, leaked source paths
│   ├── macos-client/                    # Desktop otool output
│   ├── server/                          # PMS strings, otool, source path leaks
│   └── web/                             # web-client license attribution
├── reports/                             # this report (the 7 chapters)
├── scripts/                             # (empty — no automation needed for this scope)
└── tmp/ios/Payload/Plex.app/            # the extracted IPA
```

Key scripts to re-run (using the findings files):

```bash
# Verify "iOS doesn't ship mpv"
rg -ic '\bmpv_|libmpv' findings/ios/plex-all-strings.txt
# Expected: 0

# List Plex-owned iOS source paths
rg -o 'packages/[^[:space:]]+\.(swift|m|mm|h|c|cpp)' findings/ios/plex-all-strings.txt \
  | sort -u

# Confirm the player backend constants in the web app
WC=./plex-binaries/Plex-1.112.0.359-0d79a49f-universal.app/Contents/Resources/web-client
grep -oE '.{0,60}"mpv","samsung_avplay","webmaf_video_player".{0,60}' \
  "$WC/js/main-8792-10f56281ccddbac864ec-plex-4.156.0-4946c98.js"

# Get the Plex Transcoder FFmpeg fingerprint
./plex-binaries/PlexMediaServer-1.43.2.10687-563d026ea-universal.app/Contents/MacOS/Plex\ Transcoder -version
```

The findings/ tree contains all the raw extracted data so a future reader can verify any specific claim without re-running the analysis.
