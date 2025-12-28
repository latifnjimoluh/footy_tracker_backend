import asyncio
import json
import os
import random
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from datetime import datetime

# --- CONFIGURATION ---
BASE_URL = "https://1xbet.cm"
DATE_STR = datetime.now().strftime("%Y-%m-%d")
INPUT_FILE = os.path.join("match", DATE_STR, "favoris_1xbet.json")
OUTPUT_FILE = os.path.join("match", DATE_STR, "live_tracking_results.json")

async def check_for_popup(page):
    try:
        popup_selector = ".notification-age-restriction__actions button"
        popup_btn = page.locator(popup_selector).first
        if await popup_btn.is_visible(timeout=1000):
            print("      🔞 Popup détecté. Fermeture...")
            await popup_btn.click(force=True)
            await asyncio.sleep(1)
            return True
    except: pass
    return False

async def wait_for_page_readiness(page):
    selectors = [".scoreboard-stats__body", ".scoreboard-countdown", ".game-over-loaders-progress", ".scoreboard-scores"]
    combined_selector = ", ".join(selectors)
    print("      ⏳ Attente de stabilité du tableau de bord...")
    try:
        await page.wait_for_selector(combined_selector, state="visible", timeout=15000)
        return True
    except: return False

async def extract_live_stats(page, match_info):
    match_url = match_info['url']
    full_url = BASE_URL + match_url if not match_url.startswith("http") else match_url
    print(f"\n⚽ Analyse : {match_info['home']} vs {match_info['away']}")
    
    result = {
        "id": match_info['id'],
        "teams": f"{match_info['home']} vs {match_info['away']}",
        "status": "UNKNOWN",
        "timestamp": datetime.now().isoformat(),
        "score": {"home": 0, "away": 0},
        "half_time_score": {"home": None, "away": None},
        "game_time": "00:00",
        "data": {}
    }

    try:
        await page.goto(full_url, wait_until="domcontentloaded", timeout=60000)
        await check_for_popup(page)
        await asyncio.sleep(3) # Laisser le temps au scoreboard de s'animer

        if not await wait_for_page_readiness(page):
            result["status"] = "NOT_READY"
            return result

        # --- 1. ÉTAT TERMINÉ ---
        if await page.locator(".game-over-loaders-progress").is_visible(timeout=500):
            result["status"] = "FINISHED"
            return result

        # --- 2. ÉTAT À VENIR ---
        if await page.locator(".scoreboard-countdown").is_visible(timeout=500):
            result["status"] = "UPCOMING"
            return result

        # --- 3. ÉTAT LIVE (Extraction du Score et Temps) ---
        result["status"] = "LIVE"
        
        # A. Extraction du Score Actuel
        score_loc = page.locator(".scoreboard-scores__score")
        if await score_loc.count() >= 2:
            scores = await score_loc.all_inner_texts()
            result["score"]["home"] = scores[0].strip()
            result["score"]["away"] = scores[1].strip()

        # B. Extraction du Temps de jeu
        time_loc = page.locator(".ui-game-timer__time")
        if await time_loc.is_visible():
            result["game_time"] = await time_loc.inner_text()

        # C. Extraction du Score Mi-Temps (via le tableau des périodes)
        # On cherche la ligne qui contient "Mi-temps 1"
        try:
            period_rows = await page.locator(".scoreboard-table-row").all()
            for row in period_rows:
                row_text = await row.inner_text()
                if "Mi-temps 1" in row_text:
                    # Dans 1xBet, les buts sont souvent dans des spans avec l'icône football-goals
                    # On va utiliser BeautifulSoup pour parser cette ligne précise
                    row_html = await row.inner_html()
                    row_soup = BeautifulSoup(row_html, 'html.parser')
                    # Les buts sont dans les cellules 5 (Home) et 6 (Away) du tableau periodes
                    cells = row_soup.select(".scoreboard-table-cell")
                    if len(cells) >= 6:
                        result["half_time_score"]["home"] = cells[4].get_text(strip=True)
                        result["half_time_score"]["away"] = cells[5].get_text(strip=True)
        except: pass

        # D. Extraction des Statistiques détaillées (Attaques, etc.)
        if await page.locator(".scoreboard-stats__body").is_visible(timeout=1000):
            stats_html = await page.inner_html(".scoreboard-stats__body")
            soup = BeautifulSoup(stats_html, 'html.parser')
            rows = soup.select(".scoreboard-list__item")
            for row in rows:
                label_el = row.select_one(".scoreboard-stats-table-view-name__label")
                if label_el:
                    label = label_el.get_text(strip=True)
                    v1 = row.select_one(".scoreboard-stats-value--team-1").get_text(strip=True)
                    v2 = row.select_one(".scoreboard-stats-value--team-2").get_text(strip=True)
                    result["data"][label] = {"home": v1, "away": v2}
        
        print(f"      📊 Score: {result['score']['home']}-{result['score']['away']} ({result['game_time']})")
        if result["half_time_score"]["home"] is not None:
            print(f"      HT Score: {result['half_time_score']['home']}-{result['half_time_score']['away']}")
            
        return result

    except Exception as e:
        print(f"      ❌ Erreur : {e}")
        return None

async def run_live_tracker():
    if not os.path.exists(INPUT_FILE): return
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        favorites = json.load(f)

    all_results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        for match_info in favorites:
            if match_info.get("status") == "FINISHED":
                continue

            data = await extract_live_stats(page, match_info)
            if data:
                all_results.append(data)
            
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(all_results, f, indent=4, ensure_ascii=False)
            
            await asyncio.sleep(random.uniform(3, 5))

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_live_tracker())