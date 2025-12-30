"""
monitor/scraper_engine.py
Module contenant toute la logique technique de scraping.
Gère Playwright, popups, extraction HTML et parsing API.
"""

import asyncio
import time
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


class MatchScraper:
    """Moteur de scraping pour extraire les données de matchs sur 1xbet"""
    
    def __init__(self, base_url="https://1xbet.cm", headless=False):
        """
        Initialise le scraper.
        
        Args:
            base_url (str): URL de base du site
            headless (bool): Mode sans interface graphique
        """
        self.base_url = base_url
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
    
    async def start(self):
        """Initialise et démarre le navigateur Chromium"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=["--start-maximized"]
        )
        self.context = await self.browser.new_context(no_viewport=True)
        self.page = await self.context.new_page()
        print("🌐 Navigateur initialisé")
    
    async def stop(self):
        """Ferme proprement le navigateur et libère les ressources"""
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
        print("🔌 Navigateur fermé")
    
    async def check_for_popup(self, page):
        """
        Ferme le popup d'âge de manière robuste.
        
        Args:
            page: Instance de la page Playwright
            
        Returns:
            bool: True si un popup a été fermé
        """
        try:
            popup_button = page.locator(".notification-age-restriction__actions button")
            if await popup_button.is_visible(timeout=3000):
                print("      🔞 Popup d'âge détecté. Fermeture...")
                await popup_button.click(force=True)
                await asyncio.sleep(1.5)
                return True
        except:
            pass
        return False
    
    async def continuous_popup_checker(self, page, duration=15):
        """
        Surveille et ferme les popups en continu pendant une durée donnée.
        
        Args:
            page: Instance de la page Playwright
            duration (int): Durée de surveillance en secondes
            
        Returns:
            bool: True si au moins un popup a été fermé
        """
        end_time = time.time() + duration
        popup_closed = False
        
        while time.time() < end_time:
            try:
                popup_button = page.locator(".notification-age-restriction__actions button")
                if await popup_button.is_visible(timeout=500):
                    if not popup_closed:
                        print("      🔞 Popup d'âge détecté. Fermeture...")
                        popup_closed = True
                    await popup_button.click(force=True)
                    await asyncio.sleep(0.5)
            except:
                pass
            await asyncio.sleep(0.5)
        
        return popup_closed
    
    async def wait_for_page_readiness(self, page, timeout=20000):
        """
        Attend que les éléments clés du scoreboard soient visibles.
        
        Args:
            page: Instance de la page Playwright
            timeout (int): Timeout en millisecondes
            
        Returns:
            bool: True si la page est prête
        """
        selectors = [
            ".scoreboard-stats__body",
            ".scoreboard-countdown",
            ".game-over-loaders-progress",
            ".scoreboard-scores",
            ".ui-game-timer"
        ]
        combined_selector = ", ".join(selectors)
        
        try:
            await page.wait_for_selector(
                combined_selector,
                state="visible",
                timeout=timeout
            )
            await asyncio.sleep(2)
            return True
        except:
            return False
    
    async def determine_match_status(self, page):
        """
        Détermine le statut visuel du match.
        
        Args:
            page: Instance de la page Playwright
            
        Returns:
            str: FINISHED, UPCOMING, LIVE ou UNKNOWN
        """
        try:
            if await page.locator(".game-over-loaders-progress").is_visible(timeout=500):
                return "FINISHED"
            if await page.locator(".scoreboard-countdown").is_visible(timeout=500):
                return "UPCOMING"
            if await page.locator(".ui-game-timer").is_visible(timeout=500):
                return "LIVE"
        except:
            pass
        return "UNKNOWN"
    
    def fix_url_for_live_match(self, url, is_live):
        """
        Corrige l'URL en remplaçant 'line' par 'live' ou inversement.
        
        Args:
            url (str): URL à corriger
            is_live (bool): True si le match est en direct
            
        Returns:
            str: URL corrigée
        """
        if is_live:
            if "/line/" in url:
                url = url.replace("/line/", "/live/")
                print("      🔄 URL corrigée : line → live")
        else:
            if "/live/" in url:
                url = url.replace("/live/", "/line/")
                print("      🔄 URL corrigée : live → line")
        return url
    
    async def extract_current_score_and_time(self, page):
        """
        Extrait le score et le temps de jeu depuis le DOM.
        
        Args:
            page: Instance de la page Playwright
            
        Returns:
            dict: {"home": str, "away": str, "time": str}
        """
        score_info = {"home": "0", "away": "0", "time": "00:00"}
        
        try:
            score_loc = page.locator(".scoreboard-scores__score")
            if await score_loc.count() >= 2:
                scores = await score_loc.all_inner_texts()
                score_info["home"] = scores[0].strip()
                score_info["away"] = scores[1].strip()
            
            time_loc = page.locator(".ui-game-timer__time")
            if await time_loc.is_visible():
                score_info["time"] = await time_loc.inner_text()
        except:
            pass
        
        return score_info
    
    async def get_half_time_score(self, page):
        """
        Récupère le score de la 1ère mi-temps.
        
        Args:
            page: Instance de la page Playwright
            
        Returns:
            dict: {"home": str or None, "away": str or None}
        """
        ht_score = {"home": None, "away": None}
        
        try:
            period_rows = await page.locator(".scoreboard-table-row").all()
            for row in period_rows:
                row_text = await row.inner_text()
                if "Mi-temps 1" in row_text:
                    row_html = await row.inner_html()
                    row_soup = BeautifulSoup(row_html, 'html.parser')
                    cells = row_soup.select(".scoreboard-table-cell")
                    if len(cells) >= 6:
                        ht_score["home"] = cells[4].get_text(strip=True)
                        ht_score["away"] = cells[5].get_text(strip=True)
                    break
        except:
            pass
        
        return ht_score
    
    async def extract_detailed_stats(self, page):
        """
        Extrait les statistiques détaillées du match.
        
        Args:
            page: Instance de la page Playwright
            
        Returns:
            dict: Statistiques par catégorie {"Attaques": {"home": "50", "away": "30"}, ...}
        """
        stats = {}
        
        try:
            if await page.locator(".scoreboard-stats__body").is_visible(timeout=1000):
                stats_html = await page.inner_html(".scoreboard-stats__body")
                soup = BeautifulSoup(stats_html, 'html.parser')
                rows = soup.select(".scoreboard-list__item")
                
                for row in rows:
                    label_el = row.select_one(".scoreboard-stats-table-view-name__label")
                    if label_el:
                        label = label_el.get_text(strip=True)
                        v1 = row.select_one(".scoreboard-stats-value--team-1")
                        v2 = row.select_one(".scoreboard-stats-value--team-2")
                        
                        if v1 and v2:
                            val1 = v1.get_text(strip=True).replace('%', '')
                            val2 = v2.get_text(strip=True).replace('%', '')
                            stats[label] = {"home": val1, "away": val2}
        except:
            pass
        
        return stats
    
    def organize_totals(self, raw_list):
        """
        Organise les totaux de buts par seuil.
        
        Args:
            raw_list (list): Liste brute de totaux
            
        Returns:
            list: Liste organisée [{"Seuil": 2.5, "Plus": 1.80, "Moins": 2.10}, ...]
        """
        mapped = {}
        for item in raw_list:
            threshold = item.get("P")
            type_pari = item.get("Type")
            cote = item.get("Cote")
            
            if threshold is not None:
                if threshold not in mapped:
                    mapped[threshold] = {"Plus": "-", "Moins": "-"}
                mapped[threshold][type_pari] = cote
        
        sorted_result = []
        for threshold in sorted(mapped.keys()):
            sorted_result.append({
                "Seuil": threshold,
                "Plus": mapped[threshold]["Plus"],
                "Moins": mapped[threshold]["Moins"]
            })
        
        return sorted_result
    
    def process_event_item(self, item, info, raw_totals_global, 
                          raw_totals_t1, raw_totals_t2):
        """
        Traite un élément d'événement et extrait les cotes/totaux.
        
        Args:
            item (dict): Item d'événement de l'API
            info (dict): Objet info à enrichir
            raw_totals_global (list): Liste des totaux globaux
            raw_totals_t1 (list): Liste des totaux équipe 1
            raw_totals_t2 (list): Liste des totaux équipe 2
        """
        if not isinstance(item, dict):
            return
        
        t = item.get("T")  # Type d'événement
        c = item.get("C")  # Cote
        p = item.get("P")  # Paramètre (seuil pour les totaux)
        
        if t is None or c is None:
            return
        
        # Mapping des types d'événements
        event_mapping = {
            1: ("live_odds", "V1"),
            2: ("live_odds", "X"),
            3: ("live_odds", "V2"),
            180: ("live_odds", "BTS_Oui"),
            181: ("live_odds", "BTS_Non")
        }
        
        if t in event_mapping:
            category, key = event_mapping[t]
            info[category][key] = c
        
        # Totaux de buts
        elif t == 9 and p is not None:
            raw_totals_global.append({"P": p, "Type": "Plus", "Cote": c})
        elif t == 10 and p is not None:
            raw_totals_global.append({"P": p, "Type": "Moins", "Cote": c})
        elif t == 11 and p is not None:
            raw_totals_t1.append({"P": p, "Type": "Plus", "Cote": c})
        elif t == 12 and p is not None:
            raw_totals_t1.append({"P": p, "Type": "Moins", "Cote": c})
        elif t == 13 and p is not None:
            raw_totals_t2.append({"P": p, "Type": "Plus", "Cote": c})
        elif t == 14 and p is not None:
            raw_totals_t2.append({"P": p, "Type": "Moins", "Cote": c})
    
    def parse_api_data(self, json_data):
        """
        Parse les données capturées de l'API.
        
        Args:
            json_data (dict): Réponse JSON de l'API
            
        Returns:
            dict: Données parsées structurées
        """
        info = {
            "current_score": None,
            "current_time": None,
            "probabilities": {},
            "live_odds": {
                "V1": "N/A", "V2": "N/A", "X": "N/A",
                "BTS_Oui": "N/A", "BTS_Non": "N/A"
            },
            "totals": {"global": [], "team_1": [], "team_2": []}
        }
        
        try:
            val = json_data.get("Value", {})
            
            # Score et temps
            if "SC" in val:
                sc = val["SC"]
                if "FS" in sc:
                    info["current_score"] = f"{sc['FS'].get('S1', 0)}-{sc['FS'].get('S2', 0)}"
                if "TS" in sc:
                    minutes = sc['TS'] // 60
                    seconds = sc['TS'] % 60
                    info["current_time"] = f"{minutes}:{seconds:02d}"
            
            # Probabilités
            if "WP" in val:
                info["probabilities"] = {
                    "P1": f"{val['WP'].get('P1', 0)*100:.0f}%",
                    "PX": f"{val['WP'].get('PX', 0)*100:.0f}%",
                    "P2": f"{val['WP'].get('P2', 0)*100:.0f}%"
                }
            
            # Cotes et totaux
            raw_totals_global, raw_totals_t1, raw_totals_t2 = [], [], []
            game_events = val.get("GE", [])
            
            for group in game_events:
                events = group.get("E", [])
                if isinstance(events, list):
                    for event_group in events:
                        if isinstance(event_group, list):
                            for item in event_group:
                                self.process_event_item(
                                    item, info, raw_totals_global,
                                    raw_totals_t1, raw_totals_t2
                                )
                        elif isinstance(event_group, dict):
                            self.process_event_item(
                                event_group, info, raw_totals_global,
                                raw_totals_t1, raw_totals_t2
                            )
            
            info["totals"]["global"] = self.organize_totals(raw_totals_global)
            info["totals"]["team_1"] = self.organize_totals(raw_totals_t1)
            info["totals"]["team_2"] = self.organize_totals(raw_totals_t2)
        
        except Exception as e:
            print(f"      ⚠️ Erreur parsing API: {e}")
        
        return info
    
    async def extract_match_data(self, match_info):
        """
        Extrait toutes les données d'un match (méthode principale).
        
        Args:
            match_info (dict): Informations de base du match (url, nom, pronostic, etc.)
            
        Returns:
            dict: Données complètes du match incluant:
                - status, score, game_time
                - half_time_score, stats
                - live_odds, probabilities, totals
        """
        match_url = match_info.get('url', '')
        original_url = self.base_url + match_url if not match_url.startswith("http") else match_url
        
        print(f"\n⚽ Analyse : {match_info.get('match_complet', 'Match inconnu')}")
        
        result = {
            **match_info,
            "status": "UNKNOWN",
            "timestamp": datetime.now().isoformat(),
            "last_update": datetime.now().strftime("%H:%M:%S"),
            "score": "0-0",
            "half_time_score": {"home": None, "away": None},
            "game_time": "00:00",
            "stats": {},
            "live_odds": {},
            "probabilities": {},
            "totals": {}
        }
        
        captured_data = {}
        api_captured = False
        
        async def handle_response(response):
            """Handler pour intercepter les réponses API"""
            nonlocal api_captured, captured_data
            if "GetGameZip" in response.url or "GetGame" in response.url:
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    try:
                        data = await response.json()
                        if "Value" in data and ("GE" in data["Value"] or "SC" in data["Value"]):
                            captured_data = data
                            api_captured = True
                            print("      📡 Données API capturées")
                    except:
                        pass
        
        self.page.on("response", handle_response)
        
        try:
            current_url = original_url
            print(f"      🌐 Chargement: {current_url}")
            
            await self.page.goto(current_url, wait_until="load", timeout=60000)
            
            print("      ⏳ Surveillance des popups et chargement...")
            popup_task = asyncio.create_task(
                self.continuous_popup_checker(self.page, duration=15)
            )
            
            # Attente de capture API
            start_wait = time.time()
            while not api_captured and time.time() - start_wait < 10:
                await asyncio.sleep(0.5)
            
            await popup_task
            print("      ✅ Page chargée et stabilisée")
            
            page_ready = await self.wait_for_page_readiness(self.page, timeout=20000)
            
            if not page_ready:
                status = await self.determine_match_status(self.page)
                if status == "UNKNOWN":
                    result["status"] = "NOT_READY"
                    return result
            else:
                status = await self.determine_match_status(self.page)
            
            result["status"] = status
            print(f"      📊 Statut initial: {status}")
            
            # Gestion des différents statuts
            if status == "FINISHED":
                result = await self._handle_finished_match(
                    result, original_url, current_url,
                    api_captured, captured_data
                )
                return result
            
            if status == "UPCOMING":
                if api_captured:
                    api_data = self.parse_api_data(captured_data)
                    result["live_odds"] = api_data.get("live_odds", {})
                    result["probabilities"] = api_data.get("probabilities", {})
                    result["totals"] = api_data.get("totals", {})
                return result
            
            if status == "LIVE":
                result = await self._handle_live_match(
                    result, api_captured, captured_data
                )
            
            return result
        
        except Exception as e:
            print(f"      ❌ Erreur : {e}")
            return result
        
        finally:
            self.page.remove_listener("response", handle_response)
    
    async def _handle_finished_match(self, result, original_url, 
                                     current_url, api_captured, captured_data):
        """
        Gère un match terminé avec vérification en mode LIVE.
        
        Args:
            result (dict): Résultat à enrichir
            original_url (str): URL originale
            current_url (str): URL actuelle
            api_captured (bool): Données API capturées
            captured_data (dict): Données API
            
        Returns:
            dict: Résultat mis à jour
        """
        print("      🔍 Vérification en mode LIVE...")
        live_url = original_url.replace("/line/", "/live/")
        
        if live_url != current_url:
            api_captured = False
            captured_data = {}
            
            try:
                await self.page.goto(live_url, wait_until="load", timeout=60000)
                popup_task = asyncio.create_task(
                    self.continuous_popup_checker(self.page, duration=12)
                )
                
                start_wait = time.time()
                while not api_captured and time.time() - start_wait < 10:
                    await asyncio.sleep(0.5)
                
                await popup_task
                
                page_ready_live = await self.wait_for_page_readiness(
                    self.page, timeout=20000
                )
                
                if page_ready_live:
                    status_live = await self.determine_match_status(self.page)
                    print(f"      📊 Statut en mode live: {status_live}")
                    
                    if status_live == "LIVE":
                        result["status"] = "LIVE"
                        print("      ✅ Match LIVE détecté")
                        return await self._handle_live_match(
                            result, api_captured, captured_data
                        )
                    elif status_live == "FINISHED":
                        print("      ✅ Match confirmé terminé")
                        score_data = await self.extract_current_score_and_time(self.page)
                        result["score"] = f"{score_data['home']}-{score_data['away']}"
                        return result
            
            except Exception as e:
                print(f"      ⚠️ Erreur vérification live: {e}")
        
        score_data = await self.extract_current_score_and_time(self.page)
        result["score"] = f"{score_data['home']}-{score_data['away']}"
        return result
    
    async def _handle_live_match(self, result, api_captured, captured_data):
        """
        Extrait les données d'un match en direct.
        
        Args:
            result (dict): Résultat à enrichir
            api_captured (bool): Données API capturées
            captured_data (dict): Données API
            
        Returns:
            dict: Résultat mis à jour
        """
        score_data = await self.extract_current_score_and_time(self.page)
        result["score"] = f"{score_data['home']}-{score_data['away']}"
        result["game_time"] = score_data["time"]
        
        ht_score = await self.get_half_time_score(self.page)
        result["half_time_score"] = ht_score
        
        result["stats"] = await self.extract_detailed_stats(self.page)
        
        if api_captured:
            api_data = self.parse_api_data(captured_data)
            
            if api_data["current_score"]:
                result["score"] = api_data["current_score"]
            if api_data["current_time"]:
                result["game_time"] = api_data["current_time"]
            
            result["live_odds"] = api_data.get("live_odds", {})
            result["probabilities"] = api_data.get("probabilities", {})
            result["totals"] = api_data.get("totals", {})
        
        print(f"      ⚽ Score: {result['score']} ({result['game_time']})")
        if ht_score["home"] is not None:
            print(f"      📍 HT: {ht_score['home']}-{ht_score['away']}")
        
        return result