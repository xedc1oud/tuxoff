<div align="center">

```
████████╗██╗   ██╗██╗  ██╗ ██████╗ ███████╗███████╗
╚══██╔══╝██║   ██║╚██╗██╔╝██╔═══██╗██╔════╝██╔════╝
   ██║   ██║   ██║ ╚███╔╝ ██║   ██║█████╗  █████╗  
   ██║   ██║   ██║ ██╔██╗ ██║   ██║██╔══╝  ██╔══╝  
   ██║   ╚██████╔╝██╔╝ ██╗╚██████╔╝██║     ██║     
   ╚═╝    ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝     
```

**A terminal-based repack manager for Linux**

![Linux](https://img.shields.io/badge/Linux-only-FCC624?style=flat-square&logo=linux&logoColor=black)
![Python](https://img.shields.io/badge/Python-3.13+-3776AB?style=flat-square&logo=python&logoColor=white)
![uv](https://img.shields.io/badge/built_with-uv-DE5FE9?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

</div>

---

## What is tuxoff?

`tuxoff` is a command-line tool for searching and opening game torrents directly from your terminal. It indexes repacks from [jc141](https://www.1337xx.to/user/johncena141/) and searches [RuTracker](https://rutracker.org) across all major platforms — no GUI, no browser, just fast keyboard-driven access.

---

## Requirements

- **OS:** Linux (only)
- **Python:** 3.13+
- **Package manager:** [`uv`](https://github.com/astral-sh/uv)

---

## Installation

### 1. Install `uv` (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

> Restart your shell or run `source $HOME/.local/bin/env` after installation.

### 2. Clone the repository

```bash
git clone https://github.com/xedc1oud/tuxoff.git
cd tuxoff
```

### 3. Build and install

```bash
uv tool install .
```

---

## Updating

```bash
cd tuxoff
git pull
uv tool install . --reinstall
```

---

## Setup

### Sync the jc141 index

```bash
tuxoff --sync
```

Crawls all jc141 pages in parallel and saves the index to `~/.cache/tuxoff/index.json`. Do this once, then re-run occasionally to pick up new releases.

### Log in to RuTracker

```bash
tuxoff --login
```

Opens a browser window — log in manually, press **Enter** in the terminal. Session is saved to `~/.config/tuxoff/config.json` and reused for all future searches.

---

## Usage

### Interactive catalog

```bash
tuxoff --catalog
```

Opens a full-screen TUI browser of the local jc141 index.

```
┌──────────────────────────────────────────────────────────────────┐
│ tuxoff                                                12:34:56   │
├──────────────────┬───────────────────────────┬───────────────────┤
│  PLATFORMS       │  ENTRIES  100/1247         │  PREVIEW          │
│                  │                            │                   │
│  ● All (1247)    │   [jc141] Supraland        │  Title            │
│    Linux (1247)  │   [jc141] Hollow Knight    │  Supraland        │
│                  │ ✓ [jc141] Celeste          │                   │
│                  │   [jc141] Witcher 3        │  Source           │
│                  │   ...                      │  jc141            │
│                  │                            │                   │
│                  │  ← page 1 / 13  →          │  Platform         │
│                  │                            │  Linux            │
├──────────────────┴───────────────────────────┴───────────────────┤
│  /  type to filter...                              100 results    │
├──────────────────────────────────────────────────────────────────┤
│  /: Search   SPACE/↵: Select   Ctrl+O: Open   ESC: Back   ^C: Quit│
└──────────────────────────────────────────────────────────────────┘
```

**Controls:**

| Key | Action |
|---|---|
| `↑` / `↓` | Navigate entries |
| `←` / `→` | Previous / next page |
| `SPACE` or `Enter` | Toggle selection |
| `Ctrl+O` | Open selected (or highlighted) in torrent client |
| `/` | Focus search bar |
| `ESC` | Clear search / return to list / quit |
| `Ctrl+C` | Quit without opening |

The list is paginated at 100 entries per page for instant rendering regardless of index size. Select multiple entries with `SPACE`, then `Ctrl+O` to open all at once.

---

### Browse by platform

```bash
tuxoff -p=<platform>
```

Fetches the full RuTracker listing for a platform live and opens it in the catalog. Requires a RuTracker session (`tuxoff --login`).

```bash
tuxoff -p=switch
tuxoff -p=ps4
tuxoff -p=ps3
```

---

### Search and open

```bash
tuxoff <game-name>
```

Searches the local jc141 cache and queries RuTracker live, then opens the catalog pre-filtered to matching results.

```bash
tuxoff supraland
tuxoff "hollow knight"
tuxoff witcher
```

### Search by platform

```bash
tuxoff <game-name> -p=<platform>
```

```bash
tuxoff zelda -p=switch
tuxoff "god of war" -p=ps4
tuxoff halo -p=xbox360
tuxoff "crash bandicoot" -p=ps1
```

### Search without the catalog TUI

```bash
tuxoff <game-name> --no-catalog
```

Falls back to a simple curses menu instead of the full TUI. Useful on minimal setups or if you prefer a faster selection flow.

---

**Available platforms:**

| Flag | Platform |
|---|---|
| `linux` | GNU/Linux — Wine + Native *(default)* |
| `ps1` | PlayStation 1 |
| `ps2` | PlayStation 2 |
| `ps3` | PlayStation 3 |
| `ps4` | PlayStation 4 |
| `ps5` | PlayStation 5 |
| `psp` | PlayStation Portable |
| `psvita` | PlayStation Vita |
| `xbox` | Xbox (original) |
| `xbox360` | Xbox 360 |
| `wii` | Wii / Wii U / GameCube |
| `3ds` | 3DS / DS |
| `switch` | Nintendo Switch |
| `dreamcast` | Sega Dreamcast |
| `other` | Other platforms |

---

## Quick Reference

| Command | Description |
|---|---|
| `tuxoff --sync` | Index all jc141 pages into local cache |
| `tuxoff --login` | Log in to RuTracker and save session |
| `tuxoff --catalog` | Open interactive catalog browser |
| `tuxoff -p=<platform>` | Browse all RuTracker entries for a platform |
| `tuxoff <game>` | Search by name (linux by default) |
| `tuxoff <game> -p=<platform>` | Search on a specific platform |
| `tuxoff <game> --no-catalog` | Search with simple curses menu |
| `tuxoff --debug <command>` | Enable verbose output |
| `tuxoff --help` | Show help |

---

## Files

| Path | Description |
|---|---|
| `~/.cache/tuxoff/index.json` | Local jc141 repack index |
| `~/.config/tuxoff/config.json` | RuTracker session cookies |

---

## Uninstall

```bash
uv tool uninstall tuxoff
```

---

## Contributing

Pull requests are welcome. For major changes, open an issue first to discuss what you'd like to change.

---

<div align="center">
<sub>Made for Linux. Runs in a terminal. Does its job.</sub>
</div>
