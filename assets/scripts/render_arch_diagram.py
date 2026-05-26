# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Render the Plex players architecture diagram for the README.

Run with `uv run assets/scripts/render_arch_diagram.py` (or any Python 3.10+).
Output goes to stdout. Self-contained, no third-party deps.
"""


class Grid:
    """A 2D character canvas. Minimal subset of ascii-renderer's grid_buffer."""

    def __init__(self, width: int, height: int, fill: str = " ") -> None:
        self.width = width
        self.height = height
        self.cells = [[fill] * width for _ in range(height)]

    def set(self, x: int, y: int, ch: str) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.cells[y][x] = ch[0] if ch else " "

    def text(self, x: int, y: int, s: str) -> None:
        for i, ch in enumerate(s):
            self.set(x + i, y, ch)

    def hline(self, x: int, y: int, length: int, ch: str = "-") -> None:
        for i in range(length):
            self.set(x + i, y, ch)

    def vline(self, x: int, y: int, length: int, ch: str = "|") -> None:
        for i in range(length):
            self.set(x, y + i, ch)

    def box(self, x: int, y: int, w: int, h: int, border: str) -> None:
        tl, t, tr, r, br, b, bl, l = border
        self.set(x, y, tl)
        self.hline(x + 1, y, w - 2, t)
        self.set(x + w - 1, y, tr)
        for row in range(1, h - 1):
            self.set(x, y + row, l)
            self.set(x + w - 1, y + row, r)
        self.set(x, y + h - 1, bl)
        self.hline(x + 1, y + h - 1, w - 2, b)
        self.set(x + w - 1, y + h - 1, br)

    def render(self) -> str:
        return "\n".join("".join(row).rstrip() for row in self.cells)


U = "┌─┐│┘─└│"  # TL T TR R BR B BL L


def header_box(g: Grid, x: int, y: int, w: int, h: int,
               title: str, lines: list[str]) -> None:
    inner_w = w - 2
    usable = inner_w - 2
    for line in lines:
        assert len(line) <= usable, (
            f"line {line!r} ({len(line)} chars) exceeds usable width {usable}"
        )
    assert len(title) <= inner_w
    g.box(x, y, w, h, border=U)
    tx = x + 1 + (inner_w - len(title)) // 2
    g.text(tx, y + 1, title)
    g.hline(x + 1, y + 2, w - 2, "─")
    g.set(x, y + 2, "├")
    g.set(x + w - 1, y + 2, "┤")
    for i, line in enumerate(lines):
        g.text(x + 2, y + 3 + i, line)


def main() -> None:
    col_w = 24
    col_gap = 2
    n_cols = 4
    cols_total = col_w * n_cols + col_gap * (n_cols - 1)
    margin = 2
    W = cols_total + margin * 2

    base_x = margin
    col_xs = [base_x + i * (col_w + col_gap) for i in range(n_cols)]
    col_mids = [x + col_w // 2 for x in col_xs]

    pms_w = 76
    pms_x = (W - pms_w) // 2
    pms_y = 0
    pms_h = 7
    bus_y = pms_y + pms_h + 2
    boxes_y = bus_y + 2
    box_h = 26
    H = boxes_y + box_h
    g = Grid(W, H)

    header_box(
        g, pms_x, pms_y, pms_w, pms_h,
        title="Plex Media Server (PMS)",
        lines=[
            "C++ / Boost / pion HTTP server",
            "Custom FFmpeg fork (Plex Transcoder) + Enhanced Audio Engine",
            "Shared HTTP / HLS / DASH API + media decision endpoint",
        ],
    )

    pms_mid_x = pms_x + pms_w // 2
    g.vline(pms_mid_x, pms_y + pms_h, 2, "│")

    g.hline(col_mids[0], bus_y, col_mids[-1] - col_mids[0] + 1, "─")
    g.set(col_mids[0], bus_y, "┌")
    g.set(col_mids[-1], bus_y, "┐")
    for cm in col_mids[1:-1]:
        g.set(cm, bus_y, "┬")
    g.set(pms_mid_x, bus_y, "┴")

    for cm in col_mids:
        for yy in range(bus_y + 1, boxes_y):
            g.set(cm, yy, "│")
        g.set(cm, boxes_y, "┬")

    header_box(
        g, col_xs[0], boxes_y, col_w, box_h,
        title="iOS App",
        lines=[
            "Plex 2026.9.0",
            "",
            "React Native 0.83",
            "(react-native-tvos",
            "  fork) + Hermes JS",
            "+ Fabric / TurboMod.",
            "",
            "TurboModule bridge:",
            "  NativeEngineMgr",
            "",
            "Player:",
            "  KSPlayer_private",
            "  (Plex's fork)",
            "",
            "Backends:",
            "  - KSAVPlayer",
            "    (AVPlayer/HW VT)",
            "  - KSMEPlayer",
            "    (FFmpeg 5 static",
            "    +libass+Metal)",
        ],
    )

    header_box(
        g, col_xs[1], boxes_y, col_w, box_h,
        title="tvOS App (legacy)",
        lines=[
            "PlexTV 8.45 (2024)",
            "",
            "TVMLKit",
            "  (TVML + TVJS,",
            "  Apple 2015 sample)",
            "+ UIKit NIBs (31x)",
            "+ SwiftUI bundle",
            "  (in migration)",
            "",
            "Player:",
            "  PlexMPV.framework",
            "  (libmpv wrapper)",
            "+ FFmpeg 5.x",
            "+ BASS audio family",
            "+ Mux QoE",
            "",
            "TVMLKit deprecated",
            "at WWDC 2024.",
            "RN tvOS scaffolding",
            "set up in iOS mono-",
            "repo. Not yet built.",
        ],
    )

    header_box(
        g, col_xs[2], boxes_y, col_w, box_h,
        title="Desktop (mac/Win/Lin)",
        lines=[
            "Plex 1.112.0",
            "",
            "Qt 6.2.4 host",
            "+ QtWebEngine",
            "  (Chromium)",
            "",
            "Loads Plex Web SPA",
            "(plex-4.156+ bundle)",
            "",
            "Bridge:",
            "  QtWebChannel",
            "  (JS <-> C++ RPC)",
            "",
            "Web backend = 'mpv'",
            "",
            "Player:",
            "  libmpv 2.0",
            "+ FFmpeg 5.x dylibs",
            "+ VideoToolbox HW",
        ],
    )

    header_box(
        g, col_xs[3], boxes_y, col_w, box_h,
        title="Web / Smart TVs",
        lines=[
            "plex-4.156+ SPA",
            "",
            "React + Webpack",
            "code-split SPA",
            "(207 lazy chunks)",
            "",
            "Same bundle ships in",
            "browsers, Desktop,",
            "Tizen, webOS, and",
            "PMS WebClient.bundle",
            "",
            "Runtime player",
            "selector picks 1 of:",
            "  - 'html'",
            "    Shaka Player",
            "    (MSE / EME)",
            "  - 'mpv'",
            "    (Plex Desktop)",
            "  - 'samsung_avplay'",
            "    (Tizen)",
            "  - 'webmaf_player'",
            "    (LG webOS)",
        ],
    )

    print(g.render())


if __name__ == "__main__":
    main()
