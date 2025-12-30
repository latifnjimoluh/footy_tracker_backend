"""
monitor/betting_logic.py
Module contenant toute la logique d'analyse et de recommandation de paris.
MISE A JOUR : Extraction des cotes de but (+0.5) et structure d'alerte enrichie (Score/Temps).
"""

from datetime import datetime

class BettingAnalyzer:
    """Analyseur de matchs pour détecter les opportunités de paris"""
    
    # === SEUILS CONFIGURABLES ===
    MIN_MINUTE_TRAILING = 45  # Minute min pour favori perdant
    MIN_MINUTE_DRAW = 45      # Minute min pour match nul
    MIN_MINUTE_LATE_GAME = 60 # Minute pour fin de match
    LATE_GAME_THRESHOLD = 75  # Minute pour actions de dernière minute
    
    DOMINATION_RATIO = 1.5    # Ratio d'attaques pour considérer domination
    MIN_MINUTE_DOMINATION = 45
    
    def __init__(self):
        """Initialise l'analyseur avec une liste d'alertes vide"""
        self.alerts = []

    # ============================================================
    # 🛠️ NOUVELLES FONCTIONS POUR LES COTES DE BUTS
    # ============================================================
    
    def _find_best_odd(self, totals_list, target_threshold):
        """
        Cherche la cote 'Plus' (Over) pour un seuil donné ou le plus proche.
        Ex: Si le score est 1-0, on cherche l'Over 1.5.
        """
        best_odd = "N/A"
        if not totals_list: return best_odd

        for t in totals_list:
            try:
                # On compare avec une petite marge d'erreur pour les float (2.5 vs 2.5)
                if abs(float(t['Seuil']) - target_threshold) < 0.1:
                    return t['Plus']
            except: continue
        return best_odd

    def _extract_target_odds(self, match_data, side_fav):
        """
        Récupère les cotes spécifiques :
        1. Prochain but dans le match (Total actuel + 0.5)
        2. Prochain but du favori (Total favori actuel + 0.5)
        """
        odds_info = {
            "but_match": "N/A",      
            "but_favori": "N/A"      
        }
        
        try:
            # Récupération du score actuel
            score = match_data.get("score", "0-0")
            if "-" in score:
                s1, s2 = map(int, score.replace(" ", "").split("-"))
                total_goals = s1 + s2
                
                # 1. Cote "But en plus dans le match" (Over Total Actuel + 0.5)
                # Ex: Score 1-1 (Total 2) -> On cherche cote Over 2.5
                target_match = total_goals + 0.5
                odds_info["but_match"] = self._find_best_odd(
                    match_data.get("totals", {}).get("global", []), 
                    target_match
                )
                
                # 2. Cote "But équipe favorite" (Over Score Fav + 0.5)
                score_fav = s1 if side_fav == "home" else s2
                target_team = score_fav + 0.5
                
                team_list_key = "team_1" if side_fav == "home" else "team_2"
                odds_info["but_favori"] = self._find_best_odd(
                    match_data.get("totals", {}).get(team_list_key, []),
                    target_team
                )

        except Exception as e:
            pass # Si erreur de calcul, on laisse N/A
            
        return odds_info

    # ============================================================
    # 🧠 LOGIQUE PRINCIPALE
    # ============================================================
    
    def calculate_opportunity_score(self, match_data):
        """
        Calcule une note d'opportunité et propose une ACTION DE PARI.
        """
        opportunity = {
            "score": 0,
            "niveau": "AUCUNE",
            "type": None,
            "raisons": [],
            "recommandation": None,
            "action_suggeree": None,
            "risque": "FAIBLE",
            "cotes_extra": {} # Nouveau champ pour stocker les cotes buts
        }
        
        # 1. Vérifications de base
        if match_data.get("status") != "LIVE":
            return opportunity

        # 2. Parsing des données (Robuste)
        try:
            score = match_data.get("score", "0-0")
            if "-" not in score:
                return opportunity
            home_score, away_score = map(int, score.replace(" ", "").split("-"))
            
            game_time = match_data.get("game_time", "00:00")
            minutes = int(game_time.split(":")[0]) if ":" in game_time else 0
            
            cote_initiale = float(match_data.get("cote", 0))
            favori = match_data.get("favori", "Favori")
            pronostic = match_data.get("pronostic", "")
            
            # Cotes Live
            live_odds = match_data.get("live_odds", {})
            try: c_v1 = float(live_odds.get("V1")) 
            except: c_v1 = None
            try: c_v2 = float(live_odds.get("V2")) 
            except: c_v2 = None

        except:
            return opportunity

        # 3. Définition dynamique du favori
        if pronostic == "V1":
            score_fav = home_score
            score_adv = away_score
            cote_live_fav = c_v1
            side_fav = "home"
        elif pronostic == "V2":
            score_fav = away_score
            score_adv = home_score
            cote_live_fav = c_v2
            side_fav = "away"
        else:
            return opportunity

        # === 4. RECUPERATION DES COTES CIBLÉES (NOUVEAU) ===
        opportunity["cotes_extra"] = self._extract_target_odds(match_data, side_fav)

        # 5. Analyse des scénarios
        ecart = score_adv - score_fav
        
        # --- CAS 1 : FAVORI PERDANT ---
        if score_adv > score_fav and minutes >= self.MIN_MINUTE_TRAILING:
            opportunity = self._analyze_trailing_favorite(
                opportunity, ecart, minutes, favori, pronostic, 
                cote_initiale, score, cote_live_fav
            )
        
        # --- CAS 2 : MATCH NUL TARDIF ---
        elif score_adv == score_fav and minutes >= self.MIN_MINUTE_DRAW:
            opportunity = self._analyze_late_draw(
                opportunity, minutes, score, cote_live_fav
            )
        
        # --- CAS 3 : DOMINATION STATISTIQUE ---
        opportunity = self._analyze_statistical_domination(
            opportunity, match_data, side_fav, minutes, 
            score_adv, score_fav
        )
        
        # 6. Finalisation du message
        if opportunity["action_suggeree"]:
            rec = opportunity.get('recommandation', '')
            opportunity["recommandation"] = f"{rec}\n🔥 <b>{opportunity['action_suggeree']}</b>"

        return opportunity
    
    # ... (Les fonctions d'analyse interne restent inchangées, je les remets pour que le fichier soit complet)
    
    def _analyze_trailing_favorite(self, opp, ecart, minutes, favori, 
                                   pronostic, cote_init, score, cote_live):
        opp["type"] = "FAVORI_PERDANT"
        opp["raisons"].append(
            f"{favori} ({pronostic}) mené {score} (Cote init: {cote_init})"
        )
        
        if ecart == 1 and minutes >= self.MIN_MINUTE_LATE_GAME:
            opp["score"] = 90
            opp["niveau"] = "🔴 ALERTE ROUGE"
            opp["risque"] = "MOYEN"
            opp["recommandation"] = "Le favori n'a qu'un but de retard. Pression maximale attendue."
            
            if minutes < self.LATE_GAME_THRESHOLD:
                opp["action_suggeree"] = "👉 PARIER : Prochain but équipe favori (ou '1X/X2' Double Chance)"
            else:
                opp["action_suggeree"] = "👉 PARIER : But dans le match (Over 0.5 fin de match)"
        
        elif ecart >= 2:
            opp["score"] = 75
            opp["niveau"] = "🟠 ALERTE ORANGE"
            opp["risque"] = "ÉLEVÉ"
            opp["recommandation"] = "Écart important. Le favori va attaquer pour l'honneur."
            opp["action_suggeree"] = "👉 PARIER : Total Buts +0.5 ou But du Favori (si cote > 1.60)"
        
        elif ecart == 1 and self.MIN_MINUTE_TRAILING <= minutes < self.MIN_MINUTE_LATE_GAME:
            opp["score"] = 85
            opp["niveau"] = "🔴 ALERTE ROUGE"
            opp["risque"] = "MOYEN"
            opp["recommandation"] = "Le favori a tout le temps de revenir."
            opp["action_suggeree"] = f"👉 PARIER : Victoire sèche du Favori (Cote boostée : {cote_live})"
        
        return opp
    
    def _analyze_late_draw(self, opp, minutes, score, cote_live):
        opp["type"] = "MATCH_NUL_TARDIF"
        opp["raisons"].append(f"Score de parité {score} à la {minutes}'")
        
        if cote_live and cote_live >= 1.80:
            opp["score"] = 80
            opp["niveau"] = "🟠 ALERTE VALUE"
            opp["risque"] = "MOYEN"
            opp["recommandation"] = "Cote du favori devenue très intéressante."
            opp["action_suggeree"] = "👉 PARIER : Victoire Favori (Remboursé si Nul) ou But fin de match"
        else:
            opp["score"] = 60
            opp["niveau"] = "🟡 SURVEILLANCE"
            opp["action_suggeree"] = "Attendre que la cote monte encore"
        
        return opp
    
    def _analyze_statistical_domination(self, opp, match_data, side_fav, 
                                        minutes, score_adv, score_fav):
        stats = match_data.get("stats", {})
        try:
            def get_stat(k, s):
                val = stats.get(k, {}).get(s, "0")
                return int(val) if isinstance(val, str) and val.isdigit() else 0
            
            att_fav = get_stat("Attaques", side_fav)
            att_adv = get_stat("Attaques", "home" if side_fav == "away" else "away")
            
            if att_fav > att_adv * self.DOMINATION_RATIO and \
               minutes >= self.MIN_MINUTE_DOMINATION and \
               score_adv >= score_fav:
                
                opp["score"] += 10 
                opp["raisons"].append(
                    f"🔥 Domination : {att_fav} attaques vs {att_adv}"
                )
                if opp["action_suggeree"] is None:
                    opp["action_suggeree"] = "👉 PARIER : Prochain but du Favori"
        except: pass
        return opp
    
    def generate_alert_message(self, match_data, opportunity):
        """Génère un message d'alerte pour la CONSOLE uniquement"""
        if opportunity["score"] < 50:
            return None
        return f"ALERTE CONSOLE : {match_data.get('match_complet')} | Score: {opportunity['score']}"
    
    def add_alert(self, match_data, opportunity):
        """
        Ajoute une alerte à la liste interne.
        IMPORTANT : On ajoute explicitement SCORE et GAME_TIME à la racine
        pour que le bot Telegram puisse les lire facilement.
        """
        if opportunity.get("score", 0) >= 50:
            self.alerts.append({
                "match": match_data.get("match_complet"),
                "timestamp": datetime.now().isoformat(),
                # --- AJOUTS CRUCIAUX POUR TELEGRAM ---
                "score": match_data.get("score", "N/A"),
                "game_time": match_data.get("game_time", "N/A"),
                # -------------------------------------
                "opportunity": opportunity
            })
    
    def get_alerts(self):
        return self.alerts
    
    def clear_alerts(self):
        self.alerts = []