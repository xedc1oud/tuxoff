from __future__ import annotations

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


def _strip_prefix(title: str) -> str:
    for part in (title.split("] ", 1),):
        if len(part) == 2 and part[0].startswith("["):
            return part[1]
    return title


def _wrap(text: str, width: int = 34) -> str:
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
    def __init__(self, key: str, label: str) -> None:
        super().__init__()
        self.platform_key = key
        self._label = label

    def compose(self) -> ComposeResult:
        yield Label(self._label)


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
        if len(short) > 64:
            short = short[:61] + "..."
        size = self.meta.get("size", "")
        return f"{mark}{short}  [{size}]" if size else f"{mark}{short}"

    def _refresh_label(self) -> None:
        try:
            self.query_one(Label).update(self._make_text())
        except Exception:
            pass


CSS = """
Screen { background: $surface; }
#layout { height: 1fr; }

#sidebar {
    width: 22;
    border-right: solid $primary-darken-2;
    background: $surface-darken-1;
}
#sidebar-title {
    background: $primary-darken-3;
    color: $text;
    text-align: center;
    height: 1;
    text-style: bold;
    padding: 0 1;
}
#platform-list > ListItem              { padding: 0 2; height: 1; }
#platform-list > ListItem.active       { color: $success; text-style: bold; }
#platform-list > ListItem.--highlight  { background: $primary; }

#center { width: 1fr; }
#entries-header {
    background: $primary-darken-3;
    color: $text;
    padding: 0 1;
    height: 1;
    text-style: bold;
}
#entry-list > ListItem              { padding: 0 1; height: 1; }
#entry-list > ListItem.--highlight  { background: $primary; }
#entry-list > ListItem.selected-row { color: $success; }

#preview {
    width: 38;
    border-left: solid $primary-darken-2;
    background: $surface-darken-1;
    padding: 0 2;
}
#preview-title {
    background: $primary-darken-3;
    color: $text;
    text-align: center;
    height: 1;
    text-style: bold;
    margin-bottom: 1;
}
.plabel { color: $text-muted; text-style: bold; margin-top: 1; }
.pvalue { color: $text; }

#search-bar {
    height: 3;
    border-top: solid $primary-darken-2;
    background: $surface-darken-2;
    padding: 0 1;
    align: left middle;
}
#search-input              { width: 1fr; border: solid $primary-darken-1; }
#search-input:focus        { border: solid $primary; }
#count-label               { color: $text-muted; padding: 0 2; width: auto; }
"""


class CatalogApp(App[list[tuple[str, dict]]]):
    CSS = CSS

    BINDINGS = [
        Binding("/", "focus_search", "Search", show=True),
        Binding("escape", "clear_search", "Clear", show=True),
        Binding("space", "toggle_select", "Select", show=True),
        Binding("enter", "confirm", "Open", show=True),
        Binding("q", "quit_empty", "Quit", show=True),
    ]

    _active_platform: reactive[str] = reactive("all")
    _search_query: reactive[str] = reactive("")

    def __init__(self, index: dict) -> None:
        super().__init__()
        self._index = index
        self._filtered: list[tuple[str, dict]] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="layout"):
            with Vertical(id="sidebar"):
                yield Static("  PLATFORMS", id="sidebar-title")
                yield ListView(id="platform-list")
            with Vertical(id="center"):
                yield Static("", id="entries-header")
                yield ListView(id="entry-list")
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
        self._refresh_entries()

    def _build_platforms(self) -> None:
        lv = self.query_one("#platform-list", ListView)
        lv.clear()
        all_item = PlatformItem("all", "  ● All")
        all_item.add_class("active")
        lv.append(all_item)
        present = {m.get("platform", "linux") for m in self._index.values()}
        for key, label in PLATFORM_LABELS.items():
            if key in present:
                lv.append(PlatformItem(key, f"    {label}"))

    @on(ListView.Highlighted, "#platform-list")
    def _on_platform_highlight(self, event: ListView.Highlighted) -> None:
        if not isinstance(event.item, PlatformItem):
            return
        for item in self.query("#platform-list ListItem"):
            item.remove_class("active")
        event.item.add_class("active")
        self._active_platform = event.item.platform_key
        self._refresh_entries()

    def _refresh_entries(self) -> None:
        query = self._search_query.lower()
        plat = self._active_platform
        selected_titles = {
            item.entry_title for item in self.query(EntryItem) if item.selected
        }

        self._filtered = [
            (t, m)
            for t, m in self._index.items()
            if (plat == "all" or m.get("platform", "linux") == plat)
            and (not query or query in t.lower())
        ]
        self._filtered.sort(key=lambda x: x[0].lower())

        lv = self.query_one("#entry-list", ListView)
        lv.clear()
        for title, meta in self._filtered:
            item = EntryItem(title, meta)
            if title in selected_titles:
                item.selected = True
                item.add_class("selected-row")
            lv.append(item)

        total = len(self._index)
        shown = len(self._filtered)
        sel = len(selected_titles)
        sel_str = f"  {sel} selected  " if sel else ""
        self.query_one("#entries-header", Static).update(
            f"  ENTRIES  {shown}/{total}{sel_str}"
        )
        self.query_one("#count-label", Label).update(f"{shown} results")
        self._clear_preview()

    @on(ListView.Highlighted, "#entry-list")
    def _on_entry_highlight(self, event: ListView.Highlighted) -> None:
        if isinstance(event.item, EntryItem):
            self._show_preview(event.item.entry_title, event.item.meta)

    def _clear_preview(self) -> None:
        self.query_one("#preview-body", Vertical).remove_children()

    def _show_preview(self, title: str, meta: dict) -> None:
        body = self.query_one("#preview-body", Vertical)
        body.remove_children()

        source = meta.get("source", "?")
        platform = meta.get("platform", "?")
        url = meta.get("url", "?")
        size = meta.get("size", "")

        def row(label: str, value: str) -> None:
            body.mount(Label(label, classes="plabel"))
            body.mount(Label(_wrap(value), classes="pvalue"))

        row("Title", _strip_prefix(title))
        row("Source", SOURCE_LABELS.get(source, source))
        row("Platform", PLATFORM_LABELS.get(platform, platform))
        if size:
            row("Size", size)
        row("URL", url)

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_clear_search(self) -> None:
        inp = self.query_one("#search-input", Input)
        inp.value = ""
        self._search_query = ""
        self._refresh_entries()
        self.query_one("#entry-list", ListView).focus()

    def action_toggle_select(self) -> None:
        lv = self.query_one("#entry-list", ListView)
        item = lv.highlighted_child
        if not isinstance(item, EntryItem):
            return
        item.selected = not item.selected
        if item.selected:
            item.add_class("selected-row")
        else:
            item.remove_class("selected-row")
        sel = sum(1 for i in lv.query(EntryItem) if i.selected)
        total = len(self._index)
        shown = len(self._filtered)
        sel_str = f"  {sel} selected  " if sel else ""
        self.query_one("#entries-header", Static).update(
            f"  ENTRIES  {shown}/{total}{sel_str}"
        )

    def action_confirm(self) -> None:
        lv = self.query_one("#entry-list", ListView)
        chosen = [(i.entry_title, i.meta) for i in lv.query(EntryItem) if i.selected]
        if not chosen:
            item = lv.highlighted_child
            if isinstance(item, EntryItem):
                chosen = [(item.entry_title, item.meta)]
        self.exit(chosen)

    def action_quit_empty(self) -> None:
        self.exit([])

    @on(Input.Changed, "#search-input")
    def _on_search_changed(self, event: Input.Changed) -> None:
        self._search_query = event.value
        self._refresh_entries()


def run_catalog(index: dict | None = None) -> list[tuple[str, dict]]:
    if index is None:
        index = load_cache()
    if not index:
        print("[!] Cache is empty. Run 'tuxoff --sync' first.")
        return []
    return CatalogApp(index).run() or []
