import streamlit as st
import json
import os
import time
import pandas as pd
from datetime import datetime

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Monitor 1xBet - Dashboard Pro",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS PERSONNALISÉ ---
st.markdown("""
    <style>
    .big-score { font-size: 2.5rem; font-weight: 800; color: #4CAF50; text-align: center; margin: 0; }
    .live-badge { background-color: #ff4b4b; color: white; padding: 4px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; animation: pulse 1.5s infinite; }
    .status-badge { background-color: #43A047; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; }
    .stat-box { background-color: #262730; padding: 8px; border-radius: 8px; text-align: center; border: 1px solid #444; margin-bottom: 5px; }
    .stat-label { font-size: 0.75rem; color: #aaa; text-transform: uppercase; letter-spacing: 0.5px; }
    .stat-value { font-size: 1.1rem; font-weight: bold; color: #fff; }
    .alert-box { padding: 15px; border-radius: 8px; margin-bottom: 10px; border-left: 5px solid; }
    .alert-red { background-color: #3a1c1c; border-color: #ff4b4b; }
    .alert-orange { background-color: #3a2e1c; border-color: #ffa726; }
    
    @keyframes pulse {
        0% { opacity: 1; box-shadow: 0 0 0 0 rgba(255, 75, 75, 0.7); }
        70% { opacity: 1; box-shadow: 0 0 0 5px rgba(255, 75, 75, 0); }
        100% { opacity: 1; box-shadow: 0 0 0 0 rgba(255, 75, 75, 0); }
    }
    </style>
""", unsafe_allow_html=True)

# --- FONCTIONS ---
DATE_STR = datetime.now().strftime("%Y-%m-%d")
BASE_DIR = os.path.join("match", DATE_STR)
DATA_FILE = os.path.join(BASE_DIR, "matchs_surveillance_final.json")

def load_data():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def format_stats(stats_dict):
    """Formate les stats pour affichage (ex: T1-T2)"""
    if not stats_dict: return "0-0"
    if isinstance(stats_dict, dict):
        return f"{stats_dict.get('T1', 0)} - {stats_dict.get('T2', 0)}"
    return str(stats_dict)

# --- SIDEBAR ---
st.sidebar.title("🎛️ Filtres")
auto_refresh = st.sidebar.checkbox("🔄 Rafraîchissement Auto (5s)", value=True)
filter_status = st.sidebar.multiselect("Statut", ["LIVE", "UPCOMING", "FINISHED"], default=["LIVE", "UPCOMING"])
show_alerts_only = st.sidebar.checkbox("🚨 Afficher opportunités seulement", value=False)

# --- MAIN LOOP ---
placeholder = st.empty()

while True:
    with placeholder.container():
        matches = load_data()
        
        if not matches:
            st.info(f"⏳ En attente de données pour {DATE_STR}...")
        else:
            # 1. HEADER & KPI
            nb_live = sum(1 for m in matches if m.get("status") == "LIVE")
            nb_alerts = sum(1 for m in matches if m.get("opportunity", {}).get("score", 0) >= 50)
            
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.title("🎯 1xBet Hunter Dashboard")
            c2.metric("Matchs en cours", nb_live)
            c3.metric("Opportunités", nb_alerts, delta_color="inverse")
            
            st.divider()

            # 2. SECTION ALERTES (PRIORITAIRE)
            alerts = [m for m in matches if m.get("opportunity", {}).get("score", 0) >= 50]
            if alerts:
                st.subheader("🚨 Opportunités Détectées")
                for m in alerts:
                    opp = m["opportunity"]
                    color_class = "alert-red" if opp.get("score") >= 80 else "alert-orange"
                    icon = "🔥" if opp.get("score") >= 80 else "⚠️"
                    
                    st.markdown(f"""
                    <div class="alert-box {color_class}">
                        <h4>{icon} {m['match_complet']}</h4>
                        <p><strong>{opp.get('niveau')}</strong> (Score: {opp.get('score')})</p>
                        <p>{opp.get('recommandation', '')}</p>
                        <ul>
                            {''.join([f'<li>{r}</li>' for r in opp.get('raisons', [])])}
                        </ul>
                    </div>
                    """, unsafe_allow_html=True)
                st.divider()

            # 3. LISTE DES MATCHS
            st.subheader("📡 Radar des Matchs")
            
            # Filtrage
            filtered_matches = [m for m in matches if m.get("status", "UNKNOWN") in filter_status]
            if show_alerts_only:
                filtered_matches = [m for m in filtered_matches if m.get("opportunity", {}).get("score", 0) >= 50]
            
            # Tri : LIVE d'abord, puis par heure
            filtered_matches.sort(key=lambda x: (x.get("status") != "LIVE", x.get("heure")))

            for match in filtered_matches:
                status = match.get("status")
                score = match.get("score", "N/A")
                time_game = match.get("game_time", "N/A")
                
                # Titre de l'expander
                header_icon = "🔴" if status == "LIVE" else "📅"
                header_text = f"{header_icon} {match['match_complet']} | {score}"
                if status == "LIVE": header_text += f" ({time_game})"
                
                with st.expander(header_text, expanded=(status=="LIVE")):
                    
                    # Colonnes : Info | Score | Cotes
                    c1, c2, c3 = st.columns([3, 2, 3])
                    
                    with c1:
                        st.caption(f"🏆 {match.get('league')}")
                        st.markdown(f"**Favori :** {match.get('favori')}")
                        st.markdown(f"**Prono Initial :** `{match.get('pronostic')}` @ {match.get('cote')}")
                        if status == "LIVE":
                            st.markdown(f"<span class='live-badge'>LIVE {time_game}</span>", unsafe_allow_html=True)
                    
                    with c2:
                        st.markdown(f"<div class='big-score'>{score}</div>", unsafe_allow_html=True)
                        ht = match.get("half_time_score", {})
                        if isinstance(ht, dict) and ht.get("home") is not None:
                            st.caption(f"MT: {ht.get('home')}-{ht.get('away')}")
                        elif isinstance(ht, str) and ht != "N/A":
                            st.caption(f"MT: {ht}")

                    with c3:
                        odds = match.get("live_odds", {})
                        st.markdown("##### 💰 Cotes Live")
                        co1, co2, co3 = st.columns(3)
                        co1.metric("1", odds.get("V1", "-"))
                        co2.metric("X", odds.get("X", "-"))
                        co3.metric("2", odds.get("V2", "-"))
                        
                        bts = f"Oui: {odds.get('BTS_Oui', '-')} | Non: {odds.get('BTS_Non', '-')}"
                        st.caption(f"⚽ BTS: {bts}")

                    # STATS VISUELLES
                    live_stats = match.get("live_stats", {})
                    if status == "LIVE" and live_stats:
                        st.markdown("---")
                        st.caption("📊 STATISTIQUES MATCH")
                        ks = ["Attaques", "Attaques dangereuses", "Tirs cadrés", "Corners", "Possession"]
                        k_cols = st.columns(len(ks))
                        for i, k in enumerate(ks):
                            val = live_stats.get(k, "0-0")
                            if isinstance(val, dict): val = f"{val.get('T1',0)}-{val.get('T2',0)}"
                            k_cols[i].markdown(f"""
                                <div class="stat-box">
                                    <div class="stat-label">{k}</div>
                                    <div class="stat-value">{val}</div>
                                </div>
                            """, unsafe_allow_html=True)

                    # TOTAUX
                    totals = match.get("totals", {})
                    if totals.get("global") or totals.get("team_1"):
                        st.markdown("---")
                        t1, t2 = st.tabs(["📈 Totaux Match", "🏠/✈️ Totaux Équipes"])
                        
                        with t1:
                            if totals.get("global"):
                                df_glob = pd.DataFrame(totals["global"])
                                st.dataframe(
                                    df_glob.style.highlight_between(subset=["Plus", "Moins"], left=1.5, right=2.0, color="#1b5e20"),
                                    use_container_width=True, hide_index=True
                                )
                        
                        with t2:
                            col_t1, col_t2 = st.columns(2)
                            with col_t1:
                                st.caption("Domicile")
                                if totals.get("team_1"):
                                    st.dataframe(pd.DataFrame(totals["team_1"]), use_container_width=True, hide_index=True)
                            with col_t2:
                                st.caption("Extérieur")
                                if totals.get("team_2"):
                                    st.dataframe(pd.DataFrame(totals["team_2"]), use_container_width=True, hide_index=True)

    if not auto_refresh: break
    time.sleep(5)