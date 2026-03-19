#! /usr/bin/env python3

import sys
import os
import json
import curses
import asyncio
import random
import subprocess

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

CACHE_FILE = os.path.expanduser("~/.cache/tuxoff/index.json")
CONFIG_FILE = os.path.expanduser("~/.config/tuxoff/config.json")

RUTRACKER_HOST = "rutracker.org"

RUTRACKER_PLATFORMS = {
    "linux": [2059, 1992],
    "ps1": [908],
    "ps2": [357],
    "ps3": [886],
    "ps4": [973],
    "ps5": [546],
    "psp": [1352],
    "psvita": [595],
    "xbox": [887],
    "xbox360": [510],
    "wii": [773],
    "3ds": [774],
    "switch": [1605],
    "dreamcast": [968],
    "other": [129],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

JC141_SEM = asyncio.Semaphore(8)
RT_SEM = asyncio.Semaphore(5)
DEBUG = False
NO_CATALOG = False


def dbg(msg):
    if DEBUG:
        print(f"[debug] {msg}")


# ── args ──────────────────────────────────────────────────────────────────────


def parse_args(argv):
    global DEBUG, NO_CATALOG

    if len(argv) < 2:
        return None, None, None

    args = argv[1:]

    if "--debug" in args:
        DEBUG = True
        args = [a for a in args if a != "--debug"]

    if "--no-catalog" in args:
        NO_CATALOG = True
        args = [a for a in args if a != "--no-catalog"]

    if not args:
        return None, None, None

    command = args[0]
    if command.startswith("--"):
        return command, None, None

    # tuxoff -p=switch  →  open catalog filtered to that platform
    if command.startswith("-p="):
        platform = command[3:].lower().replace(" ", "").replace("/", "")
        return "--platform-catalog", None, platform

    game_name_parts = []
    platform = None

    for arg in args[1:]:
        if arg.startswith("-p="):
            platform = arg[3:].lower().replace(" ", "").replace("/", "")
        elif arg.startswith("-"):
            pass  # skip unknown flags silently
        else:
            game_name_parts.append(arg)

    game_name = " ".join([command] + game_name_parts)
    return None, game_name, platform


# ── cache / config ────────────────────────────────────────────────────────────


def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    with open(CACHE_FILE, "r") as f:
        raw = json.load(f)
    result = {}
    for title, meta in raw.items():
        if isinstance(meta, str):
            result[title] = {"url": meta, "source": "jc141", "platform": "linux"}
        else:
            result[title] = meta
    return result


def save_cache(data):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(data):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_cookies(storage_state):
    cookies = {}
    for c in storage_state.get("cookies", []):
        if "rutracker" in c.get("domain", ""):
            cookies[c["name"]] = c["value"]
    return cookies


# ── curses fallback select ────────────────────────────────────────────────────


def curses_select(items):
    def _inner(stdscr):
        curses.curs_set(0)
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)
        selected = [False] * len(items)
        cursor = 0
        while True:
            stdscr.clear()
            height, width = stdscr.getmaxyx()
            stdscr.addstr(0, 0, "SPACE toggle  ENTER confirm  Q quit")
            stdscr.addstr(1, 0, "─" * (width - 1))
            visible_start = max(0, cursor - (height - 4))
            for i, item in enumerate(items[visible_start:], start=visible_start):
                row = i - visible_start + 2
                if row >= height - 1:
                    break
                mark = "✓" if selected[i] else " "
                line = f"  [{mark}] {item}"
                if len(line) > width - 1:
                    line = line[: width - 4] + "..."
                if i == cursor:
                    stdscr.attron(curses.color_pair(1))
                    stdscr.addstr(row, 0, line.ljust(width - 1))
                    stdscr.attroff(curses.color_pair(1))
                else:
                    stdscr.addstr(row, 0, line)
            stdscr.refresh()
            key = stdscr.getch()
            if key == curses.KEY_UP and cursor > 0:
                cursor -= 1
            elif key == curses.KEY_DOWN and cursor < len(items) - 1:
                cursor += 1
            elif key == ord(" "):
                selected[cursor] = not selected[cursor]
            elif key in (curses.KEY_ENTER, ord("\n"), ord("\r")):
                return [items[i] for i, s in enumerate(selected) if s]
            elif key in (ord("q"), ord("Q")):
                return []

    return curses.wrapper(_inner)


# ── browsers ──────────────────────────────────────────────────────────────────


async def ensure_browsers():
    try:
        async with async_playwright() as p:
            await p.chromium.launch(headless=True)
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            print("[!] Browsers not found. Starting installation...")
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"], check=True
            )
            print("[+] Installation completed successfully!")
        else:
            raise e


# ── jc141 sync ────────────────────────────────────────────────────────────────


def jc141_parse_page(html):
    soup = BeautifulSoup(html, "lxml")
    entries = {}
    for row in soup.select("table.table-list tbody tr"):
        links = row.select("td.coll-1 a")
        if len(links) < 2:
            continue
        a = links[1]
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if href:
            entries[f"[jc141] {title}"] = {
                "url": "https://www.1337xx.to" + href,
                "source": "jc141",
                "platform": "linux",
            }
    return entries


def jc141_get_last_page(html):
    soup = BeautifulSoup(html, "lxml")
    nums = []
    for sel in ["ul.pagination li a", ".pagination a", "div.pagination a"]:
        for a in soup.select(sel):
            t = a.get_text(strip=True)
            if t.isdigit():
                nums.append(int(t))
        if nums:
            dbg(f"pagination selector matched: {sel!r}, max={max(nums)}")
            break
    if not nums:
        dbg("pagination: no selector matched, fallback to sequential scan")
    return max(nums) if nums else None


async def jc141_fetch_page(client, page_num):
    async with JC141_SEM:
        url = (
            f"https://www.1337xx.to/user/johncena141/{page_num}/"
            if page_num > 1
            else "https://www.1337xx.to/user/johncena141/"
        )
        await asyncio.sleep(random.uniform(0.1, 0.4))
        try:
            resp = await client.get(url)
            dbg(f"jc141 page {page_num}: {resp.status_code}")
            return page_num, jc141_parse_page(resp.text)
        except Exception as e:
            dbg(f"jc141 page {page_num} error: {e}")
            return page_num, {}


async def run_sync():
    index = load_cache()
    total_new = 0

    async with httpx.AsyncClient(
        headers=HEADERS, timeout=30, follow_redirects=True
    ) as client:
        print("[~] Fetching jc141 page 1...")
        resp = await client.get("https://www.1337xx.to/user/johncena141/")
        first_page_entries = jc141_parse_page(resp.text)
        last_page = jc141_get_last_page(resp.text)

        if last_page is not None:
            print(f"[*] jc141: {last_page} pages found, fetching all in parallel...")
            tasks = [jc141_fetch_page(client, n) for n in range(2, last_page + 1)]
            results = await asyncio.gather(*tasks)
            all_entries = {**first_page_entries}
            for _, page_entries in sorted(results, key=lambda x: x[0]):
                all_entries.update(page_entries)
        else:
            print("[*] jc141: pagination not detected, scanning sequentially...")
            all_entries = {**first_page_entries}
            seen: set[str] = set(first_page_entries.keys())
            page_num = 2
            while True:
                _, page_entries = await jc141_fetch_page(client, page_num)
                if not page_entries:
                    break
                new_keys = set(page_entries.keys()) - seen
                if not new_keys:
                    dbg(f"page {page_num} is duplicate, stopping")
                    break
                seen.update(page_entries.keys())
                all_entries.update(page_entries)
                print(f"[~] jc141 page {page_num}: {len(page_entries)} entries")
                page_num += 1
                await asyncio.sleep(random.uniform(0.3, 0.7))

    for key, meta in all_entries.items():
        if key not in index:
            index[key] = meta
            total_new += 1

    save_cache(index)
    print(f"[+] jc141 sync complete. {total_new} new entries. Total: {len(index)}.")


# ── RuTracker search ──────────────────────────────────────────────────────────


def rt_parse_page(html, platform_key):
    soup = BeautifulSoup(html, "lxml")
    results = {}
    for a in soup.select("td.t-title-col a.tLink"):
        title = a.get_text(strip=True)
        href = a.get("href", "")
        if href:
            results[f"[rutracker/{platform_key}] {title}"] = {
                "url": f"https://{RUTRACKER_HOST}/forum/{href}",
                "source": "rutracker",
                "platform": platform_key,
            }
    return results


def rt_get_extra_starts(html):
    soup = BeautifulSoup(html, "lxml")
    starts = set()
    for a in soup.select("a[href*='start=']"):
        for part in a.get("href", "").split("&"):
            if part.startswith("start="):
                try:
                    v = int(part.split("=")[1])
                    if v > 0:
                        starts.add(v)
                except ValueError:
                    pass
    return sorted(starts)


async def rt_fetch_page(client, cookies, forum_id, game_name, platform_key, start=0):
    async with RT_SEM:
        params = {"f": forum_id, "nm": game_name}
        if start:
            params["start"] = start
        await asyncio.sleep(random.uniform(0.1, 0.3))
        resp = await client.get(
            f"https://{RUTRACKER_HOST}/forum/tracker.php",
            params=params,
            cookies=cookies,
        )
        dbg(f"rutracker forum={forum_id} start={start}: {resp.status_code}")
        return resp.text


async def search_rutracker_forum(client, cookies, forum_id, game_name, platform_key):
    html = await rt_fetch_page(client, cookies, forum_id, game_name, platform_key)
    results = rt_parse_page(html, platform_key)
    extra = rt_get_extra_starts(html)
    if extra:
        pages = await asyncio.gather(
            *[
                rt_fetch_page(client, cookies, forum_id, game_name, platform_key, s)
                for s in extra
            ]
        )
        for page_html in pages:
            results.update(rt_parse_page(page_html, platform_key))
    return results


async def search_rutracker(game_name, platform, cookies):
    key = platform or "linux"
    if key not in RUTRACKER_PLATFORMS:
        print(
            f"[!] Unknown platform '{key}'. Available: {', '.join(RUTRACKER_PLATFORMS)}"
        )
        return {}
    async with httpx.AsyncClient(
        headers=HEADERS, timeout=30, follow_redirects=True
    ) as client:
        results_list = await asyncio.gather(
            *[
                search_rutracker_forum(client, cookies, fid, game_name, key)
                for fid in RUTRACKER_PLATFORMS[key]
            ]
        )
    out = {}
    for r in results_list:
        out.update(r)
    return out


# ── login ─────────────────────────────────────────────────────────────────────


async def run_login():
    await ensure_browsers()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(user_agent=HEADERS["User-Agent"])
        page = await context.new_page()
        print("[*] Opening RuTracker login page...")
        print("[*] Log in manually, then press ENTER here to save the session.")
        await page.goto(
            f"https://{RUTRACKER_HOST}/forum/login.php",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        input("")
        storage = await context.storage_state()
        config = load_config()
        config["rutracker_cookies"] = storage
        save_config(config)
        print("[+] Session saved to config.")
        await browser.close()


# ── fast magnet fetch via httpx ───────────────────────────────────────────────


async def _fetch_magnet_httpx(url: str, cookies: dict | None = None) -> str | None:
    """Try to scrape the magnet link with httpx+bs4 — no browser needed."""
    try:
        async with httpx.AsyncClient(
            headers=HEADERS,
            cookies=cookies or {},
            timeout=15,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
        soup = BeautifulSoup(resp.text, "lxml")
        # jc141 / generic
        el = soup.select_one("a[href^='magnet:']")
        if not el:
            # rutracker
            el = soup.select_one("a.magnet-link")
        if el:
            return el.get("href")
    except Exception as e:
        dbg(f"httpx magnet fetch failed for {url}: {e}")
    return None


async def _fetch_magnet_playwright(url: str, storage=None) -> str | None:
    """Playwright fallback — slower but handles JS-rendered pages."""
    await ensure_browsers()
    stealth = Stealth()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx_kwargs = {"user_agent": HEADERS["User-Agent"]}
        if storage:
            ctx_kwargs["storage_state"] = storage
        context = await browser.new_context(**ctx_kwargs)
        page = await context.new_page()
        await stealth.apply_stealth_async(page)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            el = await page.query_selector(
                "a[href^='magnet:']"
            ) or await page.query_selector("a.magnet-link")
            if el:
                return await el.get_attribute("href")
        except Exception as e:
            dbg(f"playwright magnet fetch failed for {url}: {e}")
        finally:
            await page.close()
            await browser.close()
    return None


async def _open_one(
    title: str, meta: dict, rt_cookies: dict | None, rt_storage
) -> None:
    source = meta.get("source", "jc141")
    url = meta["url"]

    # fast path: httpx
    cookies = rt_cookies if source == "rutracker" else None
    magnet = await _fetch_magnet_httpx(url, cookies)

    # slow fallback: playwright
    if not magnet:
        dbg(f"falling back to playwright for {url}")
        storage = rt_storage if source == "rutracker" else None
        magnet = await _fetch_magnet_playwright(url, storage)

    if magnet:
        subprocess.Popen(["xdg-open", magnet])
        print(f"[*] Opened: {title[:60]}")
    else:
        print(f"[X] No magnet found: {url}")


async def open_chosen(chosen: list[tuple[str, dict]], storage) -> None:
    if not chosen:
        return
    rt_cookies = extract_cookies(storage) if storage else None
    await asyncio.gather(
        *[_open_one(title, meta, rt_cookies, storage) for title, meta in chosen]
    )


# ── platform browse ──────────────────────────────────────────────────────────


async def run_platform_browse(platform: str) -> None:
    """tuxoff -p=switch — show all RuTracker entries for a platform in catalog."""
    config = load_config()
    storage = config.get("rutracker_cookies")

    # Start with cache entries for this platform
    index = load_cache()
    matches = {t: m for t, m in index.items() if m.get("platform", "linux") == platform}

    if storage:
        cookies = extract_cookies(storage)
        print(f"[*] Fetching RuTracker listings for '{platform}'...")
        # search with empty string = browse entire forum
        rt_results = await search_rutracker("", platform, cookies)
        print(f"[*] Found {len(rt_results)} entries.")
        matches.update(rt_results)
    else:
        print(
            "[!] No RuTracker session — showing cache only. Run 'tuxoff --login' to enable RT."
        )

    if not matches:
        print(f"[-] No entries for platform '{platform}'.")
        sys.exit(0)

    if NO_CATALOG:
        titles = list(matches.keys())
        raw = curses_select(titles)
        chosen = [(t, matches[t]) for t in raw]
    else:
        from .catalog import run_catalog_async

        chosen = await run_catalog_async(index=matches)

    if not chosen:
        print("[-] Nothing selected.")
        sys.exit(0)

    await open_chosen(chosen, storage)


# ── search ────────────────────────────────────────────────────────────────────


async def run_search(game_name: str, platform: str | None) -> None:
    index = load_cache()
    config = load_config()

    if platform:
        matches = {
            t: m
            for t, m in index.items()
            if game_name.lower() in t.lower() and m.get("platform", "linux") == platform
        }
    else:
        matches = {t: m for t, m in index.items() if game_name.lower() in t.lower()}

    dbg(f"cache entries: {len(index)}, cache matches: {len(matches)}")

    storage = config.get("rutracker_cookies")
    if storage:
        cookies = extract_cookies(storage)
        rt_results = await search_rutracker(game_name, platform, cookies)
        dbg(f"rutracker results: {len(rt_results)}")
        matches.update(rt_results)
    else:
        print(
            "[!] RuTracker session not found. Run 'tuxoff --login' to enable RT search."
        )

    if not matches:
        print(f"[-] No matches for '{game_name}'.")
        sys.exit(0)

    if NO_CATALOG:
        titles = list(matches.keys())
        raw = curses_select(titles)
        chosen = [(t, matches[t]) for t in raw]
    else:
        from .catalog import run_catalog_async

        chosen = await run_catalog_async(index=matches)

    if not chosen:
        print("[-] Nothing selected.")
        sys.exit(0)

    await open_chosen(chosen, storage)


# ── entry point ───────────────────────────────────────────────────────────────


def run():
    try:
        command, game_name, platform = parse_args(sys.argv)

        if command == "--help":
            print("""
tuxoff — torrent search tool for jc141 and RuTracker

COMMANDS
  tuxoff --sync                       sync jc141 index into local cache
  tuxoff --login                      log in to RuTracker (opens browser window)
  tuxoff --catalog                    open interactive catalog browser
  tuxoff --debug <command>            enable verbose debug output
  tuxoff --no-catalog <command>       use simple curses menu instead of TUI
  tuxoff --help                       show this help

  tuxoff <game>                       search by name (linux by default)
  tuxoff <game> -p=<platform>         search on a specific platform
  tuxoff -p=<platform>                browse catalog filtered to platform

PLATFORMS
  linux      GNU/Linux Wine + Native (jc141 + RuTracker)
  ps1        PlayStation 1        ps2       PlayStation 2
  ps3        PlayStation 3        ps4       PlayStation 4
  ps5        PlayStation 5        psp       PlayStation Portable
  psvita     PlayStation Vita     xbox      Xbox (original)
  xbox360    Xbox 360             wii       Wii / Wii U / GameCube
  3ds        3DS / DS             switch    Nintendo Switch
  dreamcast  Sega Dreamcast       other     Other platforms

EXAMPLES
  tuxoff --sync
  tuxoff --login
  tuxoff --catalog
  tuxoff -p=switch
  tuxoff supraland
  tuxoff supraland --no-catalog
  tuxoff "legend of zelda" -p=switch
  tuxoff "god of war" -p=ps4

FILES
  cache    ~/.cache/tuxoff/index.json
  config   ~/.config/tuxoff/config.json
""")
        elif command == "--sync":
            asyncio.run(run_sync())

        elif command == "--login":
            asyncio.run(run_login())

        elif command == "--catalog":
            from .catalog import run_catalog

            config = load_config()
            storage = config.get("rutracker_cookies")
            chosen = run_catalog()
            if chosen:
                asyncio.run(open_chosen(chosen, storage))
            else:
                print("[-] Nothing selected.")

        elif command == "--platform-catalog":
            # tuxoff -p=switch  — fetch live from RuTracker + merge cache
            asyncio.run(run_platform_browse(platform))

        elif game_name:
            asyncio.run(run_search(game_name, platform))

        else:
            print(
                "[!] Usage: tuxoff --help | --sync | --login | --catalog | -p=<platform> | <game> [-p=<platform>]"
            )
            sys.exit(1)

    except KeyboardInterrupt:
        pass
