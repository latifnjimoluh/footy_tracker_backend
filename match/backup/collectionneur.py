import asyncio
import json
import re
import os
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
BASE_URL_LIVESCORE = "https://www.livescore.com/fr/football/"

async def collect_all_matches():
    # 1. Gestion des dossiers (Structure: match/YYYY-MM-DD/fichier.json)
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Création du chemin : dossier "match" -> dossier "date"
    output_dir = os.path.join("match", today_str)
    os.makedirs(output_dir, exist_ok=True)
    
    file_path = os.path.join(output_dir, "matchs_du_jour.json")
    
    # URL spécifique à la date du jour
    target_url = f"{BASE_URL_LIVESCORE}{today_str}/"

    # 2. Charger les données existantes (Mémoire)
    existing_data = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if content:
                    old_list = json.loads(content)
                    # On indexe par match_id pour un accès rapide
                    existing_data = {str(m.get("match_id")): m for m in old_list}
            print(f"📖 Fichier existant chargé ({len(existing_data)} matchs).")
        except Exception as e:
            print(f"⚠️ Erreur lecture fichier existant (sera recréé) : {e}")

    async with async_playwright() as p:
        # Mode headless=True pour ne pas voir le navigateur
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 1000})
        page = await context.new_page()

        print(f"🌐 [LIVESCORE] Connexion à {target_url} ...")

        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5) # Attente chargement liste

            # Gestion Cookies
            try:
                if await page.locator("#onetrust-accept-btn-handler").is_visible(timeout=3000):
                    await page.click("#onetrust-accept-btn-handler")
            except: pass

            current_country = "International"
            current_league = "Unknown"
            
            # Compteurs pour le rapport
            processed_ids = set()
            updated_count = 0
            new_count = 0

            # On boucle plusieurs fois pour scroller et tout récupérer
            for _ in range(15):
                content = await page.content()
                soup = BeautifulSoup(content, "html.parser")
                
                # On récupère tous les blocs intéressants (Headers de ligue et Matchs)
                elements = soup.find_all(["div", "a"])

                for el in elements:
                    # --- A. Détection Header Ligue/Pays ---
                    if el.name == "div" and el.get("class") and "bm" in el.get("class"):
                        try:
                            # Extraction sécurisée des textes
                            c_tag = el.find(attrs={"data-id": "ct-hdr_ctg"})
                            l_tag = el.find(attrs={"data-id": "ct-hdr_stg"})
                            
                            if c_tag: 
                                current_country = c_tag.get_text(strip=True)
                            if l_tag: 
                                current_league = l_tag.get_text(strip=True)
                        except: pass
                        continue

                    # --- B. Détection Match ---
                    href = el.get("href")
                    if el.name == "a" and href and "/football/" in href and "vs" in href:
                        try:
                            # 1. Extraction ID Match
                            match_id = None
                            m = re.search(r'/(\d+)(?:/|$)', href)
                            if m: match_id = m.group(1)
                            
                            if not match_id: continue
                            match_id = str(match_id)

                            # 2. Extraction Noms Équipes (Version Longue via div.vp)
                            home_tag = el.find("div", class_="vp", attrs={"data-id": re.compile(r".*_mtc-r_hm-tm-nm$")})
                            away_tag = el.find("div", class_="vp", attrs={"data-id": re.compile(r".*_mtc-r_aw-tm-nm$")})
                            
                            # Si on ne trouve pas les div.vp, on cherche les span simples (fallback)
                            if not home_tag: home_tag = el.find(attrs={"data-id": re.compile(r".*hm-tm-nm$")})
                            if not away_tag: away_tag = el.find(attrs={"data-id": re.compile(r".*aw-tm-nm$")})

                            if not home_tag or not away_tag: continue

                            home_team = home_tag.get_text(strip=True)
                            away_team = away_tag.get_text(strip=True)

                            # 3. Extraction Heure / Statut
                            time_tag = el.find("span", attrs={"data-id": re.compile(r".*_mtc-r_st-tm$")})
                            if not time_tag: time_tag = el.find("span", class_="uu")
                            start_time = time_tag.get_text(strip=True) if time_tag else "N/A"

                            # 4. Extraction ID Ligue (depuis l'URL)
                            league_slug = "unknown"
                            parts = href.strip("/").split("/")
                            if len(parts) >= 4:
                                league_slug = parts[3]

                            # --- CONSTRUCTION DE L'OBJET ---
                            match_entry = {
                                "match_id": match_id,
                                "livescore_league_slug": league_slug,
                                "country": current_country,
                                "league": current_league,
                                "home": home_team,
                                "away": away_team,
                                "start_time": start_time,
                                "original_teams": f"{home_team} vs {away_team}",
                                "link": "https://www.livescore.com" + href,
                                "collected_at": datetime.now().strftime("%H:%M:%S")
                            }

                            # --- LOGIQUE DE MISE À JOUR INTELLIGENTE ---
                            if match_id in existing_data:
                                old_entry = existing_data[match_id]
                                
                                # On PRESERVE les cotes si elles existent déjà
                                if "odds_1xbet" in old_entry:
                                    match_entry["odds_1xbet"] = old_entry["odds_1xbet"]
                                if "1xbet_id" in old_entry:
                                    match_entry["1xbet_id"] = old_entry["1xbet_id"]
                                if "1xbet_league_id" in old_entry:
                                    match_entry["1xbet_league_id"] = old_entry["1xbet_league_id"]
                                if "odds_betpawa" in old_entry:
                                    match_entry["odds_betpawa"] = old_entry["odds_betpawa"]
                                if "betpawa_id" in old_entry:
                                    match_entry["betpawa_id"] = old_entry["betpawa_id"]
                                
                                # On remplace l'ancienne entrée par la nouvelle (mise à jour du temps/score)
                                existing_data[match_id] = match_entry
                                
                                if match_id not in processed_ids:
                                    updated_count += 1
                            else:
                                # Nouveau match
                                existing_data[match_id] = match_entry
                                new_count += 1

                            processed_ids.add(match_id)

                        except Exception as e:
                            continue

                # Scroll pour charger la suite
                await page.mouse.wheel(0, 3000)
                await asyncio.sleep(2)

            # --- SAUVEGARDE FINALE ---
            final_list = list(existing_data.values())
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(final_list, f, indent=4, ensure_ascii=False)

            print("✅ Mise à jour terminée !")
            print(f"   ➕ Nouveaux matchs : {new_count}")
            print(f"   🔄 Matchs mis à jour : {updated_count}")
            print(f"   📂 Total dans le fichier : {len(final_list)}")
            print(f"   💾 Chemin : {file_path}")

        except Exception as e:
            print(f"❌ Erreur critique : {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(collect_all_matches())