from __future__ import annotations

import asyncio

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static

from .main import load_cache

PLATFORM_LABELS: dict[str, str] = {
    "linux": "Linux",
    "ps1": "PS1",
    "ps2": "PS2",
    "ps3": "PS3",
    "ps4": "PS4",
    "ps5": "PS5",
    "psp": "PSP",
    "psvita": "PS Vita",
    "xbox": "Xbox",
    "xbox360": "Xbox 360",
    "wii": "Wii / GC / WiiU",
    "3ds": "3DS / DS",
    "switch": "Switch",
    "dreamcast": "Dreamcast",
    "other": "Other",
}

SOURCE_LABELS: dict[str, str] = {
    "jc141": "jc141  (1337xx.to)",
    "rutracker": "RuTracker",
}

PAGE_SIZE = 100


def _strip_prefix(title: str) -> str:
    if "] " in title:
        return title.split("] ", 1)[1]
    return title


def _wrap(text: str, width: int = 32) -> str:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        if len(line) + len(word) + (1 if line else 0) <= width:
            line = (line + " " + word).strip() if line else word
        else:
            if line:
                lines.append(line)
            line = word[:width]
    if line:
        lines.append(line)
    return "\n".join(lines)


class PlatformItem(ListItem):
    def __init__(self, key: str, label: str, count: int) -> None:
        super().__init__()
        self.platform_key = key
        self._label = label
        self._count = count

    def compose(self) -> ComposeResult:
        yield Label(f"{self._label} ({self._count})")


class EntryItem(ListItem):
    def __init__(self, title: str, meta: dict) -> None:
        super().__init__()
        self.entry_title = title
        self.meta = meta
        self._selected = False

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool) -> None:
        self._selected = value
        self._refresh_label()

    def compose(self) -> ComposeResult:
        yield Label(self._make_text())

    def _make_text(self) -> str:
        mark = "✓ " if self._selected else "  "
        short = self.entry_title
        if len(short) > 62:
            short = short[:59] + "..."
        size = self.meta.get("size", "")
        return f"{mark}{short}  [{size}]" if size else f"{mark}{short}"

    def _refresh_label(self) -> None:
        try:
            self.query_one(Label).update(self._make_text())
        except Exception:
            pass


CSS = """
Screen { layers: base; }

#layout { width: 100%; height: 1fr; }

#sidebar {
    width: 24;
    border-right: solid $panel-lighten-1;
}
#sidebar-title {
    background: $panel;
    text-align: center;
    height: 1;
    text-style: bold;
    padding: 0 1;
}
#platform-list { height: 1fr; }
#platform-list > ListItem             { padding: 0 1; height: 1; }
#platform-list > ListItem.--highlight { background: $accent; color: $text; }
#platform-list > ListItem.active      { text-style: bold; color: $success; }

#center { width: 1fr; }
#entries-header {
    background: $panel;
    padding: 0 1;
    height: 1;
    text-style: bold;
}
#entry-list { height: 1fr; }
#entry-list > ListItem             { padding: 0 1; height: 1; }
#entry-list > ListItem.--highlight { background: $accent; color: $text; }
#entry-list > ListItem.sel         { color: $success; }
#page-bar {
    background: $panel;
    height: 1;
    padding: 0 1;
    align: center middle;
}
#page-label { color: $text-muted; }

#preview {
    width: 36;
    border-left: solid $panel-lighten-1;
    background: $panel;
    padding: 0 2;
}
#preview-title {
    background: $panel-darken-1;
    text-align: center;
    height: 1;
    text-style: bold;
    margin-bottom: 1;
}
#preview-body { height: 1fr; }
.plabel { color: $text-muted; text-style: bold; margin-top: 1; }
.pvalue { color: $text; }

#search-bar {
    height: 3;
    border-top: solid $panel-lighten-1;
    background: $panel;
    padding: 0 1;
    align: left middle;
}
#search-input          { width: 1fr; border: solid $panel-lighten-2; }
#search-input:focus    { border: solid $accent; }
#count-label           { color: $text-muted; padding: 0 2; width: auto; }
"""


class CatalogApp(App[list[tuple[str, dict]]]):
    CSS = CSS

    BINDINGS = [
        Binding("/", "focus_search", "Search", show=True),
        Binding("escape", "clear_or_quit", "Back", show=True),
        Binding("space", "toggle_select", "Select", show=True),
        Binding("ctrl+o", "confirm", "Open", show=True),
        Binding("ctrl+c", "force_quit", "Quit", show=True),
        Binding("right", "next_page", "Next →", show=True),
        Binding("left", "prev_page", "← Prev", show=True),
    ]

    _active_platform: reactive[str] = reactive("all")
    _search_query: reactive[str] = reactive("")
    _page: reactive[int] = reactive(0)

    def __init__(self, index: dict) -> None:
        super().__init__()
        self._index = index
        self._filtered: list[tuple[str, dict]] = []
        self._selected: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="layout"):
            with Vertical(id="sidebar"):
                yield Static("  PLATFORMS", id="sidebar-title")
                yield ListView(id="platform-list")
            with Vertical(id="center"):
                yield Static("", id="entries-header")
                yield ListView(id="entry-list")
                yield Static("", id="page-bar")
            with Vertical(id="preview"):
                yield Static("  PREVIEW", id="preview-title")
                yield Vertical(id="preview-body")
        with Horizontal(id="search-bar"):
            yield Label("  /  ")
            yield Input(placeholder="type to filter...", id="search-input")
            yield Label("", id="count-label")
        yield Footer()

    def on_mount(self) -> None:
        self._build_platforms()
        self._refilter()
        self.query_one("#entry-list", ListView).focus()

    # ── sidebar ───────────────────────────────────────────────────────────────

    def _build_platforms(self) -> None:
        lv = self.query_one("#platform-list", ListView)
        lv.clear()

        # Count per platform
        counts: dict[str, int] = {}
        for m in self._index.values():
            p = m.get("platform", "linux")
            counts[p] = counts.get(p, 0) + 1

        total = len(self._index)
        all_item = PlatformItem("all", "  ● All", total)
        all_item.add_class("active")
        lv.append(all_item)

        for key, label in PLATFORM_LABELS.items():
            if key in counts:
                lv.append(PlatformItem(key, f"    {label}", counts[key]))

    @on(ListView.Highlighted, "#platform-list")
    def _on_platform_highlight(self, event: ListView.Highlighted) -> None:
        if not isinstance(event.item, PlatformItem):
            return
        for item in self.query("#platform-list ListItem"):
            item.remove_class("active")
        event.item.add_class("active")
        self._active_platform = event.item.platform_key
        self._page = 0
        self._refilter()

    # ── filtering + pagination ────────────────────────────────────────────────

    def _refilter(self) -> None:
        """Rebuild _filtered from index, then render current page."""
        query = self._search_query.lower()
        plat = self._active_platform

        self._filtered = sorted(
            [
                (t, m)
                for t, m in self._index.items()
                if (plat == "all" or m.get("platform", "linux") == plat)
                and (not query or query in t.lower())
            ],
            key=lambda x: x[0].lower(),
        )

        # Clamp page
        max_page = max(0, (len(self._filtered) - 1) // PAGE_SIZE)
        if self._page > max_page:
            self._page = max_page

        self._render_page()

    def _render_page(self) -> None:
        """Render only PAGE_SIZE items for the current page."""
        start = self._page * PAGE_SIZE
        end = start + PAGE_SIZE
        page_items = self._filtered[start:end]

        lv = self.query_one("#entry-list", ListView)
        lv.clear()
        for title, meta in page_items:
            item = EntryItem(title, meta)
            if title in self._selected:
                item._selected = True
                item.add_class("sel")
            lv.append(item)

        self._update_header()
        self._update_page_bar()
        self._clear_preview()

    def _update_header(self) -> None:
        total = len(self._index)
        shown = len(self._filtered)
        sel = len(self._selected)
        sel_str = f"  {sel} selected" if sel else ""
        self.query_one("#entries-header", Static).update(
            f"  ENTRIES  {shown}/{total}{sel_str}"
        )
        self.query_one("#count-label", Label).update(f"{shown} results")

    def _update_page_bar(self) -> None:
        total_pages = max(1, -(-len(self._filtered) // PAGE_SIZE))  # ceil div
        bar = self.query_one("#page-bar", Static)
        if total_pages <= 1:
            bar.update("")
        else:
            bar.update(
                f"← page {self._page + 1} / {total_pages}  →   (←/→ to navigate)"
            )

    # ── entry events ──────────────────────────────────────────────────────────

    @on(ListView.Selected, "#entry-list")
    def _on_entry_enter(self, event: ListView.Selected) -> None:
        event.stop()
        if isinstance(event.item, EntryItem):
            self._do_toggle(event.item)

    @on(ListView.Highlighted, "#entry-list")
    def _on_entry_highlight(self, event: ListView.Highlighted) -> None:
        if isinstance(event.item, EntryItem):
            self._show_preview(event.item.entry_title, event.item.meta)

    # ── preview ───────────────────────────────────────────────────────────────

    def _clear_preview(self) -> None:
        self.query_one("#preview-body", Vertical).remove_children()

    def _show_preview(self, title: str, meta: dict) -> None:
        body = self.query_one("#preview-body", Vertical)
        body.remove_children()

        def row(label: str, value: str) -> None:
            body.mount(Label(label, classes="plabel"))
            body.mount(Label(_wrap(value), classes="pvalue"))

        row("Title", _strip_prefix(title))
        row(
            "Source", SOURCE_LABELS.get(meta.get("source", ""), meta.get("source", "?"))
        )
        row(
            "Platform",
            PLATFORM_LABELS.get(meta.get("platform", ""), meta.get("platform", "?")),
        )
        if meta.get("size"):
            row("Size", meta["size"])
        row("URL", meta.get("url", "?"))

    # ── toggle ────────────────────────────────────────────────────────────────

    def _do_toggle(self, item: EntryItem) -> None:
        t = item.entry_title
        if t in self._selected:
            self._selected.discard(t)
            item._selected = False
            item.remove_class("sel")
        else:
            self._selected.add(t)
            item._selected = True
            item.add_class("sel")
        item._refresh_label()
        self._update_header()

    # ── actions ───────────────────────────────────────────────────────────────

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_clear_or_quit(self) -> None:
        inp = self.query_one("#search-input", Input)
        if inp.has_focus and inp.value:
            inp.value = ""
            self._search_query = ""
            self._page = 0
            self._refilter()
        elif inp.has_focus:
            self.query_one("#entry-list", ListView).focus()
        else:
            self.exit([])

    def action_toggle_select(self) -> None:
        item = self.query_one("#entry-list", ListView).highlighted_child
        if isinstance(item, EntryItem):
            self._do_toggle(item)

    def action_confirm(self) -> None:
        lv = self.query_one("#entry-list", ListView)
        if self._selected:
            chosen = [(t, m) for t, m in self._index.items() if t in self._selected]
        else:
            item = lv.highlighted_child
            chosen = (
                [(item.entry_title, item.meta)] if isinstance(item, EntryItem) else []
            )
        self.exit(chosen)

    def action_force_quit(self) -> None:
        self.exit([])

    def action_next_page(self) -> None:
        total_pages = max(1, -(-len(self._filtered) // PAGE_SIZE))
        if self._page < total_pages - 1:
            self._page += 1
            self._render_page()

    def action_prev_page(self) -> None:
        if self._page > 0:
            self._page -= 1
            self._render_page()

    @on(Input.Changed, "#search-input")
    def _on_search_changed(self, event: Input.Changed) -> None:
        self._search_query = event.value
        self._page = 0
        self._refilter()


# ── public API ────────────────────────────────────────────────────────────────


async def run_catalog_async(index: dict | None = None) -> list[tuple[str, dict]]:
    if index is None:
        index = load_cache()
    if not index:
        print("[!] Cache is empty. Run 'tuxoff --sync' first.")
        return []
    return await CatalogApp(index).run_async() or []


def run_catalog(index: dict | None = None) -> list[tuple[str, dict]]:
    if index is None:
        index = load_cache()
    if not index:
        print("[!] Cache is empty. Run 'tuxoff --sync' first.")
        return []
    return CatalogApp(index).run() or []
