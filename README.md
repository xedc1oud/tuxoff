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

The `tuxoff` command will now be available globally in your terminal.

---

## Setup

### Sync the jc141 index

```bash
tuxoff --sync
```

Crawls all jc141 pages and saves the index to `~/.cache/tuxoff/index.json`.  
⏱ Takes a few minutes. Do this once, then re-run occasionally to pick up new releases.

### Log in to RuTracker

```bash
tuxoff --login
```

Opens a browser window — log in manually, then press **Enter** in the terminal to save the session to `~/.config/tuxoff/config.json`. Required for RuTracker search to work.

---

## Usage

### Search for a game

```bash
tuxoff <game-name>
```

Searches the local jc141 cache and queries RuTracker live. Results appear in an interactive selection menu — use arrow keys to navigate, **Space** to toggle, **Enter** to confirm. Selected torrents are opened immediately in your torrent client via `xdg-open`.

```bash
tuxoff supraland
tuxoff "hollow knight"
tuxoff witcher
```

### Search by platform

```bash
tuxoff <game-name> -p=<platform>
```

Limits the search to a specific platform on RuTracker.

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
| `tuxoff --sync` | Index all jc141 pages into local cache |
| `tuxoff --login` | Log in to RuTracker and save session |
| `tuxoff <game>` | Search by name (linux by default) |
| `tuxoff <game> -p=<platform>` | Search on a specific platform |
| `tuxoff --debug <...>` | Enable verbose output for any command |
| `tuxoff --help` | Show help |

---

## Files

| Path | Description |
|---|---|
| `~/.cache/tuxoff/index.json` | jc141 repack index |
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
