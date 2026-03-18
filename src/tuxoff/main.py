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


def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    with open(CACHE_FILE, "r") as f:
        return json.load(f)


def save_cache(data):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w") as f:
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


async def open_magnet(context, stealth, torrent_page_url):
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

            print(f"[~] Syncing page {page_number}...")

            try:
                response = await page.goto(
                    url, wait_until="domcontentloaded", timeout=30000
                )
                if response.status == 404:
                    print("[!] End of pagination reached.")
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
                    print("[!] End of pagination reached.")
                    break

                seen_urls.update(page_urls)

                for row in rows:
                    link_el = await row.query_selector("td.coll-1 a:nth-child(2)")
                    if not link_el:
                        continue
                    title = (await link_el.inner_text()).strip()
                    href = await link_el.get_attribute("href")
                    torrent_url = "https://www.1337xx.to" + href
                    if title not in index:
                        index[title] = torrent_url
                        total_new += 1

                page_number += 1
                await asyncio.sleep(random.uniform(0.5, 1.0))

            except Exception as e:
                print(f"[X] Critical error: {e}")
                break

        await browser.close()

    save_cache(index)
    print(f"[+] Sync complete. {total_new} new entries. Total: {len(index)}.")


async def run_search(game_name):
    index = load_cache()

    if not index:
        print("[!] Cache is empty. Run 'tuxoff --sync' first.")
        sys.exit(1)

    matches = {
        title: url for title, url in index.items() if game_name.lower() in title.lower()
    }

    if not matches:
        print(f"[-] No matches for '{game_name}' in cache.")
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
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )

        await asyncio.gather(
            *[open_magnet(context, stealth, matches[title]) for title in chosen]
        )

        await browser.close()


def run():
    try:
        if len(sys.argv) < 2:
            print("[!] Usage: tuxoff --sync | tuxoff <game-name>")
            sys.exit(1)

        if sys.argv[1] == "--sync":
            asyncio.run(run_sync())
        else:
            asyncio.run(run_search(sys.argv[1]))

    except KeyboardInterrupt:
        pass
