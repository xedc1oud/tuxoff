#! /usr/bin/env python3

import sys
import os
import json
import curses
import asyncio
import random
import subprocess

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


def parse_args(argv):
    if len(argv) < 2:
        return None, None, None

    command = argv[1]
    if command.startswith("--"):
        return command, None, None

    game_name_parts = []
    platform = None

    for arg in argv[2:]:
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
            result[title] = {"url": meta, "source": "jc141"}
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


async def run_sync():
    await ensure_browsers()

    stealth = Stealth()
    index = load_cache()
    total_new = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )

        page = await context.new_page()
        await stealth.apply_stealth_async(page)
        await page.route(
            "**/*.{png,jpg,jpeg,gif,css,woff,woff2,svg}", lambda route: route.abort()
        )

        page_number = 1
        seen_urls = set()

        while True:
            url = (
                f"https://www.1337xx.to/user/johncena141/{page_number}/"
                if page_number > 1
                else "https://www.1337xx.to/user/johncena141/"
            )

            print(f"[~] Syncing jc141 page {page_number}...")

            try:
                response = await page.goto(
                    url, wait_until="domcontentloaded", timeout=30000
                )
                if response.status == 404:
                    print("[!] End of jc141 pagination reached.")
                    break

                rows = await page.query_selector_all("table.table-list tbody tr")
                if not rows:
                    break

                page_urls = set()
                for row in rows:
                    link_el = await row.query_selector("td.coll-1 a:nth-child(2)")
                    if not link_el:
                        continue
                    href = await link_el.get_attribute("href")
                    page_urls.add(href)

                if page_urls and page_urls.issubset(seen_urls):
                    print("[!] End of jc141 pagination reached.")
                    break

                seen_urls.update(page_urls)

                for row in rows:
                    link_el = await row.query_selector("td.coll-1 a:nth-child(2)")
                    if not link_el:
                        continue
                    title = (await link_el.inner_text()).strip()
                    href = await link_el.get_attribute("href")
                    torrent_url = "https://www.1337xx.to" + href
                    key = f"[jc141] {title}"
                    if key not in index:
                        index[key] = {
                            "url": torrent_url,
                            "source": "jc141",
                            "platform": "linux",
                        }
                        total_new += 1

                page_number += 1
                await asyncio.sleep(random.uniform(0.5, 1.0))

            except Exception as e:
                print(f"[X] Critical error: {e}")
                break

        await browser.close()

    save_cache(index)
    print(f"[+] jc141 sync complete. {total_new} new entries. Total: {len(index)}.")


async def run_login():
    await ensure_browsers()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
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

        cookies = await context.storage_state()
        config = load_config()
        config["rutracker_cookies"] = cookies
        save_config(config)
        print("[+] Session saved to config.")

        await browser.close()


async def search_rutracker(context, stealth, game_name, platform):
    results = {}
    key = platform if platform else "linux"

    if key not in RUTRACKER_PLATFORMS:
        available = ", ".join(RUTRACKER_PLATFORMS.keys())
        print(f"[!] Unknown platform '{platform}'. Available: {available}")
        return results

    forum_ids = RUTRACKER_PLATFORMS[key]

    for forum_id in forum_ids:
        url = f"https://{RUTRACKER_HOST}/forum/tracker.php?f={forum_id}&nm={game_name}"
        page = await context.new_page()
        await stealth.apply_stealth_async(page)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            rows = await page.query_selector_all("#tor-tbl tbody tr")
            for row in rows:
                title_el = await row.query_selector("td.t-title-col a.tLink")
                if not title_el:
                    continue
                title = (await title_el.inner_text()).strip()
                href = await title_el.get_attribute("href")
                torrent_url = f"https://{RUTRACKER_HOST}/forum/{href}"
                result_key = f"[rutracker/{key}] {title}"
                results[result_key] = {
                    "url": torrent_url,
                    "source": "rutracker",
                    "platform": key,
                }
        except Exception as e:
            print(f"[X] RuTracker error (forum {forum_id}): {e}")
        finally:
            await page.close()

    return results


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

    rutracker_cookies = config.get("rutracker_cookies")
    if rutracker_cookies:
        await ensure_browsers()
        stealth = Stealth()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                storage_state=rutracker_cookies,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            )
            rt_results = await search_rutracker(
                context, stealth, game_name, platform or "linux"
            )
            matches.update(rt_results)
            await browser.close()
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

        jc141_context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )
        rt_context = None
        if rutracker_cookies:
            rt_context = await browser.new_context(
                storage_state=rutracker_cookies,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
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


def run():
    try:
        command, game_name, platform = parse_args(sys.argv)

        if command == "--help":
            print("""
tuxoff — torrent search tool for jc141 and RuTracker

COMMANDS
  tuxoff --sync              index all jc141 pages into local cache
  tuxoff --login             log in to RuTracker (opens browser window)
  tuxoff --help              show this help

  tuxoff <game>              search by name (linux by default)
  tuxoff <game> -p=<platform>  search on specific platform

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
