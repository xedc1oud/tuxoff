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

`tuxoff` is a command-line tool for browsing and managing game repacks directly from your terminal. No GUI, no browser — just fast, keyboard-driven access to your library.

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

Make sure you're in the **root directory** of the project, then run:

```bash
uv tool install .
```

The `tuxoff` command will now be available globally in your terminal.

---

## Usage

### Sync the repack database

```bash
tuxoff --sync
```

Fetches and updates the local repack index from the remote source.  
⏱ This usually takes around **4 minutes** — grab a coffee.

---

### Search for a game

```bash
tuxoff <game-name>
```

**Examples:**

```bash
tuxoff cyberpunk 2077
tuxoff hollow knight
tuxoff witcher
```

Returns a list of available repacks matching the query, with relevant metadata.

---

## Quick Reference

| Command | Description |
|---|---|
| `tuxoff --sync` | Sync the repack database (~4 min) |
| `tuxoff <game-name>` | Search for a game by name |

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
