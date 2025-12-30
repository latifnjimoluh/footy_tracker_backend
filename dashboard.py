"""
dashboard.py
Interface de visualisation ULTIME pour le Bot 1xBet.
VERSION : Ajout Ligue, Pronostic, URL (Cliquable), Heure, Favori, Cote.
"""

import streamlit as st
import pandas as pd
import json
import os
import time
from datetime import datetime

# === CONFIGURATION ===
st.set_page_config(
    page_title="1xBet Command Center",
    page_icon="🦅",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# === CHEMINS DYNAMIQUES ===
DATE_STR = datetime.now().strftime("%Y-%m-%d")
BASE_DIR = os.path.join("match", DATE_STR)

# Mappage des fichiers
FILES = {
    "ALERTES": os.path.join(BASE_DIR, "alertes_opportunites.json"),
    "LIVE": os.path.join(BASE_DIR, "matchs_surveillance_final.json"), 
    "HISTORY": os.path.join(BASE_DIR, "matchs_history_log.jsonl"),
    "RAW_MATCHS": os.path.join(BASE_DIR, "matchs_details.json"),
    "IDS": os.path.join(BASE_DIR, "ids_championnats_24h.json")
}

# === FONCTIONS UTILITAIRES ===

def get_file_age(filepath):
    """Retourne l'heure de dernière modification du fichier"""
    if not os.path.exists(filepath):
        return "❌ Inexistant"
    timestamp = os.path.getmtime(filepath)
    return datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")

def safe_load_json(filepath):
    """Lecture sécurisée JSON standard"""
    if not os.path.exists(filepath): return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def safe_load_jsonl(filepath, limit=1000):
    """Lecture sécurisée JSONL"""
    data = []
    if not os.path.exists(filepath): return pd.DataFrame()
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
            for line in lines:
                try:
                    if line.strip():
                        data.append(json.loads(line))
                except: pass
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def get_color(score):
    if score >= 85: return "🔴"
    if score >= 70: return "🟠"
    if score >= 50: return "🟡"
    return "⚪"

# === CSS ===
st.markdown("""
<style>
    .big-kpi { font-size: 24px; font-weight: bold; }
    .status-live { color: #00FF00; font-weight: bold; }
    .status-finished { color: #888888; }
</style>
""", unsafe_allow_html=True)

# === SIDEBAR ===
st.sidebar.header("🎛️ Contrôle")
auto_refresh = st.sidebar.checkbox("Auto-Refresh (5s)", value=True)
st.sidebar.divider()
st.sidebar.text(f"Dossier : {DATE_STR}")

# === CHARGEMENT DONNÉES ===
alerts_data = safe_load_json(FILES["ALERTES"])
live_data = safe_load_json(FILES["LIVE"])
ids_data = safe_load_json(FILES["IDS"])

# Conversion Live en DF
df_live = pd.DataFrame(live_data)

# === GESTION DES NOMS DE COLONNES (Match Complet) ===
if not df_live.empty:
    if "match" not in df_live.columns and "match_complet" in df_live.columns:
        df_live["match"] = df_live["match_complet"]
    elif "match" not in df_live.columns:
        df_live["match"] = "Nom Inconnu"

# === ENRICHISSEMENT DATA ===
if not df_live.empty:
    # On s'assure que les colonnes existent même si le JSON est partiel
    if "opportunity" in df_live.columns:
        df_live["score_opp"] = df_live["opportunity"].apply(lambda x: x.get("score", 0) if isinstance(x, dict) else 0)
        df_live["conseil"] = df_live["opportunity"].apply(lambda x: x.get("action_suggeree", "") if isinstance(x, dict) else "")
    else:
        df_live["score_opp"] = 0
        df_live["conseil"] = ""

    # Ajout des colonnes demandées : ligue, url, pronostic, etc.
    # On complète aussi l'URL si elle est relative
    if "url" in df_live.columns:
        df_live["url"] = df_live["url"].apply(lambda x: f"https://1xbet.cm{x}" if x and x.startswith("/") else x)

    cols_required = ["league", "heure", "favori", "pronostic", "cote", "url"]
    for col in cols_required:
        if col not in df_live.columns:
            df_live[col] = None

# === INTERFACE PRINCIPALE (ONGLETS) ===
tab1, tab2, tab3, tab4 = st.tabs([
    "🚨 LIVE CENTER", 
    "📈 HISTORIQUE & LOGS", 
    "🗃️ BASES DE DONNÉES", 
    "⚙️ SANTÉ SYSTÈME"
])

# -----------------------------------------------------------------------------
# TAB 1 : LE COCKPIT (ALERTE + LIVE)
# -----------------------------------------------------------------------------
with tab1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Matchs Surveillés", len(df_live))
    c2.metric("Alertes Actives", len(alerts_data), delta_color="inverse")
    c3.metric("Meilleure Confiance", f"{df_live['score_opp'].max() if not df_live.empty else 0}%")
    c4.metric("Dernière MAJ Live", get_file_age(FILES["LIVE"]))
    
    st.divider()

    # SECTION ALERTES
    if alerts_data:
        st.subheader("🔥 OPPORTUNITÉS DÉTECTÉES")
        for alert in reversed(alerts_data[-3:]):
            opp = alert.get("opportunity", {})
            col_a, col_b = st.columns([0.1, 0.9])
            with col_a:
                st.write(f"# {get_color(opp.get('score',0))}")
            with col_b:
                match_name = alert.get('match') or alert.get('match_complet') or "Inconnu"
                st.info(f"**{match_name}** | 📊 Score: {alert.get('score')} | ⏱️ {alert.get('game_time')}\n\n"
                        f"👉 **{opp.get('action_suggeree')}** ({opp.get('score')}%)")

    # SECTION TABLEAU LIVE
    st.subheader("📺 TABLEAU DE BORD LIVE")
    if not df_live.empty:
        mode_view = st.radio("Affichage :", ["Tout", "Seulement LIVE", "Opportunités (>50%)"], horizontal=True)
        
        df_show = df_live.copy()
        
        # Filtrage
        if mode_view == "Seulement LIVE":
            if "status" in df_show.columns:
                df_show = df_show[df_show["status"] == "LIVE"]
        elif mode_view == "Opportunités (>50%)":
            df_show = df_show[df_show["score_opp"] >= 50]
        
        # --- CONFIGURATION DES COLONNES À AFFICHER ---
        # Ordre logique : Ligue > Match > Heure > Fav > Prono > Cote > Score > Chrono > Status > Confiance > Conseil > Lien
        cols_to_show = ["league", "match", "heure", "favori", "pronostic", "cote", "score", "game_time", "status", "score_opp", "conseil", "url"]
        
        # On ne garde que celles qui existent vraiment pour éviter le crash
        cols_final = [c for c in cols_to_show if c in df_show.columns]

        st.dataframe(
            df_show[cols_final],
            column_config={
                "league": st.column_config.TextColumn("Championnat", width="medium"),
                "match": st.column_config.TextColumn("Rencontre", width="medium"),
                "heure": st.column_config.TextColumn("Début", width="small"),
                "favori": st.column_config.TextColumn("Favori", width="small"),
                "pronostic": st.column_config.TextColumn("Prono", width="small"),
                "cote": st.column_config.NumberColumn("Cote Init", format="%.2f"),
                "score": st.column_config.TextColumn("Score", width="small"),
                "game_time": st.column_config.TextColumn("Chrono", width="small"),
                "status": "État",
                "score_opp": st.column_config.ProgressColumn("Confiance", min_value=0, max_value=100, format="%d%%"),
                "conseil": "Action Suggérée",
                "url": st.column_config.LinkColumn("Lien Match", display_text="Voir Match")
            },
            use_container_width=True,
            hide_index=True,
            height=600
        )
    else:
        st.warning("Aucune donnée live disponible.")

# -----------------------------------------------------------------------------
# TAB 2 : HISTORIQUE (JSONL)
# -----------------------------------------------------------------------------
with tab2:
    st.header("📜 Historique des Scans (.jsonl)")
    if st.button("🔄 Charger/Actualiser l'Historique"):
        df_history = safe_load_jsonl(FILES["HISTORY"])
        
        if not df_history.empty:
            if "match" not in df_history.columns and "match_complet" in df_history.columns:
                df_history["match"] = df_history["match_complet"]
                
            st.write(f"Total lignes lues : **{len(df_history)}**")
            st.dataframe(df_history, use_container_width=True)
        else:
            st.warning("Fichier historique vide ou introuvable.")
    else:
        st.info("Clique sur le bouton pour charger l'historique.")

# -----------------------------------------------------------------------------
# TAB 3 : BASES DE DONNÉES
# -----------------------------------------------------------------------------
with tab3:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🗂️ IDs Championnats")
        st.caption(f"Fichier : {os.path.basename(FILES['IDS'])}")
        if ids_data: st.dataframe(pd.DataFrame(ids_data), use_container_width=True)
    with c2:
        st.subheader("🗂️ Détails Matchs")
        st.caption(f"Fichier : {os.path.basename(FILES['RAW_MATCHS'])}")
        raw_matchs = safe_load_json(FILES["RAW_MATCHS"])
        if raw_matchs: st.dataframe(pd.DataFrame(raw_matchs), use_container_width=True)

# -----------------------------------------------------------------------------
# TAB 4 : SANTÉ
# -----------------------------------------------------------------------------
with tab4:
    st.header("⚙️ Diagnostic")
    health_data = []
    for name, path in FILES.items():
        exists = os.path.exists(path)
        size = f"{os.path.getsize(path)/1024:.2f} KB" if exists else "0 KB"
        health_data.append({
            "Fichier": name,
            "Statut": "✅ OK" if exists else "❌ MANQUANT",
            "Taille": size,
            "Dernière Modif": get_file_age(path)
        })
    st.dataframe(pd.DataFrame(health_data), use_container_width=True)

if auto_refresh:
    time.sleep(5)
    st.rerun()