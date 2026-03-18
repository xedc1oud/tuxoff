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


def dbg(msg):
    if DEBUG:
        print(f"[debug] {msg}")


def parse_args(argv):
    global DEBUG

    if len(argv) < 2:
        return None, None, None

    args = argv[1:]

    if "--debug" in args:
        DEBUG = True
        args = [a for a in args if a != "--debug"]

    if not args:
        return None, None, None

    command = args[0]
    if command.startswith("--"):
        return command, None, None

    game_name_parts = []
    platform = None

    for arg in args[1:]:
        if arg.startswith("-p="):
            platform = arg[3:].lower().replace(" ", "").replace("/", "")
        else:
            game_name_parts.append(arg)

    game_name = " ".join([command] + game_name_parts)
    return None, game_name, platform


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


def interactive_select(stdscr, items):
    curses.curs_set(0)
    curses.start_color()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)

    selected = [False] * len(items)
    cursor = 0

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        stdscr.addstr(
            0, 0, "Select torrents to open  [SPACE toggle, ENTER confirm, Q quit]"
        )
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


async def ensure_browsers():
    try:
        async with async_playwright() as p:
            await p.chromium.launch(headless=True)
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            print(
                "[!] Browsers not found. Starting installation (it will take a couple of minutes)..."
            )
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
    for a in soup.select("ul.pagination li a"):
        t = a.get_text(strip=True)
        if t.isdigit():
            nums.append(int(t))
    return max(nums) if nums else 1


async def jc141_fetch_page(client, page_num):
    async with JC141_SEM:
        url = (
            f"https://www.1337xx.to/user/johncena141/{page_num}/"
            if page_num > 1
            else "https://www.1337xx.to/user/johncena141/"
        )
        await asyncio.sleep(random.uniform(0.1, 0.4))
        resp = await client.get(url)
        dbg(f"jc141 page {page_num}: {resp.status_code}")
        return page_num, jc141_parse_page(resp.text)


async def run_sync():
    index = load_cache()

    async with httpx.AsyncClient(
        headers=HEADERS, timeout=30, follow_redirects=True
    ) as client:
        print("[~] Fetching jc141 page 1...")
        resp = await client.get("https://www.1337xx.to/user/johncena141/")
        first_page_entries = jc141_parse_page(resp.text)
        last_page = jc141_get_last_page(resp.text)
        dbg(f"jc141 total pages: {last_page}")
        print(f"[*] jc141: {last_page} pages found, fetching all in parallel...")

        tasks = [jc141_fetch_page(client, n) for n in range(2, last_page + 1)]
        results = await asyncio.gather(*tasks)

    all_entries = {**first_page_entries}
    for _, page_entries in sorted(results, key=lambda x: x[0]):
        all_entries.update(page_entries)

    total_new = 0
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
            url = f"https://{RUTRACKER_HOST}/forum/{href}"
            results[f"[rutracker/{platform_key}] {title}"] = {
                "url": url,
                "source": "rutracker",
                "platform": platform_key,
            }
    return results


def rt_get_extra_starts(html):
    soup = BeautifulSoup(html, "lxml")
    starts = set()
    for a in soup.select("a[href*='start=']"):
        href = a.get("href", "")
        for part in href.split("&"):
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
    html = await rt_fetch_page(
        client, cookies, forum_id, game_name, platform_key, start=0
    )
    results = rt_parse_page(html, platform_key)

    extra_starts = rt_get_extra_starts(html)
    dbg(f"forum {forum_id}: page 1 done, extra pages at starts {extra_starts}")

    if extra_starts:
        tasks = [
            rt_fetch_page(client, cookies, forum_id, game_name, platform_key, start=s)
            for s in extra_starts
        ]
        pages = await asyncio.gather(*tasks)
        for page_html in pages:
            results.update(rt_parse_page(page_html, platform_key))

    return results


async def search_rutracker(game_name, platform, cookies):
    key = platform or "linux"

    if key not in RUTRACKER_PLATFORMS:
        available = ", ".join(RUTRACKER_PLATFORMS.keys())
        print(f"[!] Unknown platform '{platform}'. Available: {available}")
        return {}

    forum_ids = RUTRACKER_PLATFORMS[key]

    async with httpx.AsyncClient(
        headers=HEADERS, timeout=30, follow_redirects=True
    ) as client:
        tasks = [
            search_rutracker_forum(client, cookies, fid, game_name, key)
            for fid in forum_ids
        ]
        forum_results = await asyncio.gather(*tasks)

    results = {}
    for fr in forum_results:
        results.update(fr)
    return results


# ── Login ─────────────────────────────────────────────────────────────────────


async def run_login():
    await ensure_browsers()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent=HEADERS["User-Agent"],
        )

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


# ── Magnet opening ────────────────────────────────────────────────────────────


async def open_magnet_jc141(context, stealth, torrent_page_url):
    page = await context.new_page()
    await stealth.apply_stealth_async(page)
    try:
        await page.goto(torrent_page_url, wait_until="domcontentloaded", timeout=30000)
        magnet_el = await page.query_selector("a[href^='magnet:']")
        if not magnet_el:
            print(f"[X] No magnet link: {torrent_page_url}")
            return
        magnet = await magnet_el.get_attribute("href")
        subprocess.Popen(["xdg-open", magnet])
        print(f"[*] Opened: {torrent_page_url}")
    finally:
        await page.close()


async def open_magnet_rutracker(context, stealth, torrent_page_url):
    page = await context.new_page()
    await stealth.apply_stealth_async(page)
    try:
        await page.goto(torrent_page_url, wait_until="domcontentloaded", timeout=30000)
        magnet_el = await page.query_selector("a.magnet-link")
        if not magnet_el:
            magnet_el = await page.query_selector("a[href^='magnet:']")
        if not magnet_el:
            print(f"[X] No magnet link: {torrent_page_url}")
            return
        magnet = await magnet_el.get_attribute("href")
        subprocess.Popen(["xdg-open", magnet])
        print(f"[*] Opened: {torrent_page_url}")
    finally:
        await page.close()


# ── Search ────────────────────────────────────────────────────────────────────


async def run_search(game_name, platform):
    index = load_cache()
    config = load_config()

    if platform:
        matches = {
            title: meta
            for title, meta in index.items()
            if game_name.lower() in title.lower()
            and meta.get("platform", "linux") == platform
        }
    else:
        matches = {
            title: meta
            for title, meta in index.items()
            if game_name.lower() in title.lower()
        }

    dbg(f"cache entries: {len(index)}, cache matches: {len(matches)}")

    storage = config.get("rutracker_cookies")
    if storage:
        cookies = extract_cookies(storage)
        rt_results = await search_rutracker(game_name, platform, cookies)
        dbg(f"rutracker results: {len(rt_results)}")
        matches.update(rt_results)
    else:
        print(
            "[!] RuTracker session not found. Run 'tuxoff --login' to enable RuTracker search."
        )

    if not matches:
        print(f"[-] No matches for '{game_name}'.")
        sys.exit(0)

    titles = list(matches.keys())
    chosen = curses.wrapper(interactive_select, titles)

    if not chosen:
        print("[-] Nothing selected.")
        sys.exit(0)

    await ensure_browsers()
    stealth = Stealth()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        jc141_context = await browser.new_context(user_agent=HEADERS["User-Agent"])
        rt_context = None
        if storage:
            rt_context = await browser.new_context(
                storage_state=storage,
                user_agent=HEADERS["User-Agent"],
            )

        tasks = []
        for title in chosen:
            meta = matches[title]
            if meta["source"] == "jc141":
                tasks.append(open_magnet_jc141(jc141_context, stealth, meta["url"]))
            elif meta["source"] == "rutracker" and rt_context:
                tasks.append(open_magnet_rutracker(rt_context, stealth, meta["url"]))

        await asyncio.gather(*tasks)
        await browser.close()


# ── Entry point ───────────────────────────────────────────────────────────────


def run():
    try:
        command, game_name, platform = parse_args(sys.argv)

        if command == "--help":
            print("""
tuxoff — torrent search tool for jc141 and RuTracker

COMMANDS
  tuxoff --sync                index all jc141 pages into local cache
  tuxoff --login               log in to RuTracker (opens browser window)
  tuxoff --debug <command>     enable verbose debug output for any command
  tuxoff --help                show this help

  tuxoff <game>                search by name (linux by default)
  tuxoff <game> -p=<platform>  search on a specific platform

PLATFORMS
  linux      GNU/Linux Wine + Native (jc141 + RuTracker)
  ps1        PlayStation 1
  ps2        PlayStation 2
  ps3        PlayStation 3
  ps4        PlayStation 4
  ps5        PlayStation 5
  psp        PlayStation Portable
  psvita     PlayStation Vita
  xbox       Xbox (original)
  xbox360    Xbox 360
  wii        Wii / Wii U / GameCube
  3ds        3DS / DS
  switch     Nintendo Switch
  dreamcast  Sega Dreamcast
  other      Other platforms

EXAMPLES
  tuxoff --sync
  tuxoff --login
  tuxoff Supraland
  tuxoff "The Legend of Zelda" -p=switch
  tuxoff "God of War" -p=ps4
  tuxoff Halo -p=xbox360

FILES
  cache    ~/.cache/tuxoff/index.json
  config   ~/.config/tuxoff/config.json
""")
        elif command == "--sync":
            asyncio.run(run_sync())
        elif command == "--login":
            asyncio.run(run_login())
        elif game_name:
            asyncio.run(run_search(game_name, platform))
        else:
            print(
                "[!] Usage: tuxoff --help | --sync | --login | <game-name> [-p=<platform>]"
            )
            sys.exit(1)

    except KeyboardInterrupt:
        pass
