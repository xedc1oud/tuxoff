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
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![uv](https://img.shields.io/badge/built_with-uv-DE5FE9?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

</div>

---

## What is tuxoff?

`tuxoff` is a command-line tool for searching and opening game torrents directly from your terminal. It indexes repacks from [jc141](https://www.1337xx.to/user/johncena141/) and searches [RuTracker](https://rutracker.org) across all major platforms — no GUI, no browser, just fast keyboard-driven access.

---

## Requirements

- **OS:** Linux (only)
- **Python:** 3.10+
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

## Setup

### Sync the index

```bash
tuxoff --sync
```

Crawls all jc141 pages and, if logged in, all RuTracker forums in parallel. Saves everything to `~/.cache/tuxoff/index.json`. Do this once, then re-run occasionally to pick up new releases.

### Log in to RuTracker

```bash
tuxoff --login
```

Opens a browser window — log in manually, press **Enter** in the terminal. Session is saved to `~/.config/tuxoff/config.json` and reused for all future searches and syncs.

---

## Usage

### Interactive catalog

```bash
tuxoff --catalog
```

Opens a full-screen TUI browser of the local index.

```
┌─────────────────────────────────────────────────────────────┐
│ tuxoff catalog                                   12:34:56   │
├─────────────────┬──────────────────────────┬────────────────┤
│  PLATFORMS      │  ENTRIES  342/1247        │  PREVIEW       │
│                 │                           │                │
│  ● All          │   [jc141] Supraland       │  Title         │
│    Linux        │   [jc141] Hollow Knight   │  Supraland     │
│    PS4          │ ✓ [jc141] Celeste         │                │
│    Switch       │   [rutracker/ps4] GoW     │  Source        │
│    ...          │   ...                     │  jc141         │
│                 │                           │                │
│                 │                           │  Platform      │
│                 │                           │  Linux         │
│                 │                           │                │
│                 │                           │  Size          │
│                 │                           │  2.1 GB        │
│                 │                           │                │
│                 │                           │  URL           │
│                 │                           │  https://...   │
├─────────────────┴──────────────────────────┴────────────────┤
│  /: search    SPACE: select    ENTER: open    Q: quit        │
└─────────────────────────────────────────────────────────────┘
```

**Controls:**

| Key | Action |
|---|---|
| `↑` / `↓` | Navigate entries |
| `SPACE` | Toggle selection |
| `ENTER` | Open selected (or highlighted) in torrent client |
| `/` | Focus search bar |
| `ESC` | Clear search, return to list |
| `Q` | Quit without opening |

Click a platform in the sidebar to filter. Type in the search bar to filter by name. Select multiple entries with `SPACE`, then `ENTER` to open all at once.

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

### Filter by platform

```bash
tuxoff <game-name> -p=<platform>
```

```bash
tuxoff zelda -p=switch
tuxoff "god of war" -p=ps4
tuxoff halo -p=xbox360
tuxoff "crash bandicoot" -p=ps1
```

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
| `tuxoff --sync` | Sync jc141 + RuTracker index |
| `tuxoff --login` | Log in to RuTracker and save session |
| `tuxoff --catalog` | Open interactive catalog browser |
| `tuxoff <game>` | Search by name (linux by default) |
| `tuxoff <game> -p=<platform>` | Search on a specific platform |
| `tuxoff --debug <command>` | Enable verbose output |
| `tuxoff --help` | Show help |

---

## Files

| Path | Description |
|---|---|
| `~/.cache/tuxoff/index.json` | Local repack index |
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
