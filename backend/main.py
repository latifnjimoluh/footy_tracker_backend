import os
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, func, and_
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, timedelta
import uvicorn # Nécessaire pour le lancement automatique

# Chargement des variables d'environnement
load_dotenv()

from . import models, database

app = FastAPI(
    title="Football Scraper API",
    version="2.0",
    description="API complète pour scraping et analyse de matchs de football"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# 📦 SCHEMAS (Modèles de données Pydantic)
# ============================================

class OddsOut(BaseModel):
    """Représentation d'une cote à un instant T"""
    odd_1: float
    odd_x: float
    odd_2: float
    recorded_at: datetime
    model_config = ConfigDict(from_attributes=True)

class OddsHistoryOut(BaseModel):
    """Historique complet d'une cote"""
    id: int
    match_id: str
    odd_1: float
    odd_x: float
    odd_2: float
    recorded_at: datetime
    model_config = ConfigDict(from_attributes=True)

class LiveStatOut(BaseModel):
    """Statistiques live d'un match"""
    status: str
    score_home: int
    score_away: int
    game_clock: Optional[str] = None
    attacks_home: Optional[int] = 0
    attacks_away: Optional[int] = 0
    dangerous_attacks_home: int
    dangerous_attacks_away: int
    possession_home: Optional[int] = None
    possession_away: Optional[int] = None
    shots_on_target_home: Optional[int] = None
    shots_on_target_away: Optional[int] = None
    corners_home: Optional[int] = None
    corners_away: Optional[int] = None
    recorded_at: datetime
    model_config = ConfigDict(from_attributes=True)

class LeagueOut(BaseModel):
    """Informations sur une ligue"""
    id: str
    name: str
    url: Optional[str] = None
    last_updated: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class MatchOut(BaseModel):
    """Informations complètes sur un match"""
    id: str
    home_team: str
    away_team: str
    start_time: Optional[datetime] = None
    status: Optional[str] = None
    score_home: Optional[int] = None
    score_away: Optional[int] = None
    league: Optional[LeagueOut] = None
    stats: List[LiveStatOut] = []
    model_config = ConfigDict(from_attributes=True)

class FavoriteCreate(BaseModel):
    """Données pour créer un favori"""
    match_id: str
    initial_odd: Optional[float] = 0.0
    bet_type: Optional[str] = "1"

class FavoriteOut(BaseModel):
    """Favori avec ses données de match"""
    match_id: str
    initial_odd: float
    bet_type: str
    detected_at: Optional[datetime] = None
    match: MatchOut
    model_config = ConfigDict(from_attributes=True)

class AlertMatch(BaseModel):
    """Match avec alerte d'activité"""
    match: MatchOut
    alert_type: str
    alert_value: float
    message: str

class OddMovement(BaseModel):
    """Mouvement significatif de cote"""
    match_id: str
    match: MatchOut
    old_odd_1: float
    new_odd_1: float
    old_odd_x: float
    new_odd_x: float
    old_odd_2: float
    new_odd_2: float
    change_1: float
    change_x: float
    change_2: float
    time_diff_minutes: float
    movement_type: str

# ============================================
# 🏆 ROUTES LEAGUES
# ============================================

@app.get("/leagues", response_model=List[LeagueOut])
def get_all_leagues(db: Session = Depends(database.get_db)):
    """Liste toutes les ligues disponibles"""
    return db.query(models.League).order_by(models.League.name).all()

@app.get("/leagues/{league_id}", response_model=LeagueOut)
def get_league_details(league_id: str, db: Session = Depends(database.get_db)):
    """Détails d'une ligue spécifique"""
    league = db.query(models.League).filter(models.League.id == league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="Ligue non trouvée")
    return league

@app.get("/leagues/{league_id}/matches", response_model=List[MatchOut])
def get_league_matches(
    league_id: str,
    status: Optional[str] = Query(None, description="Filtrer par statut: LIVE, UPCOMING, FINISHED"),
    db: Session = Depends(database.get_db)
):
    """Tous les matchs d'une ligue (filtrable par statut)"""
    query = db.query(models.Match).filter(models.Match.league_id == league_id)
    if status:
        query = query.filter(models.Match.status == status.upper())
    return query.order_by(desc(models.Match.start_time)).all()

# ============================================
# ⚽ ROUTES MATCHES
# ============================================

@app.get("/matches", response_model=List[MatchOut])
def get_all_matches(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="LIVE, UPCOMING, FINISHED"),
    league_id: Optional[str] = None,
    db: Session = Depends(database.get_db)
):
    """Tous les matchs avec pagination et filtres"""
    query = db.query(models.Match)
    
    if status:
        query = query.filter(models.Match.status == status.upper())
    
    if league_id:
        query = query.filter(models.Match.league_id == league_id)
    
    return query.order_by(desc(models.Match.start_time)).offset(skip).limit(limit).all()

@app.get("/matches/{match_id}", response_model=MatchOut)
def get_match_details(match_id: str, db: Session = Depends(database.get_db)):
    """Fiche complète d'un match avec toutes ses stats"""
    match = db.query(models.Match).filter(models.Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match non trouvé")
    return match

@app.get("/matches/live", response_model=List[MatchOut])
def get_live_matches(db: Session = Depends(database.get_db)):
    """Tous les matchs en cours (status = LIVE)"""
    return db.query(models.Match).filter(
        models.Match.status == "LIVE"
    ).order_by(models.Match.start_time).all()

@app.get("/matches/upcoming", response_model=List[MatchOut])
def get_upcoming_matches(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(database.get_db)
):
    """Matchs à venir (triés par date)"""
    return db.query(models.Match).filter(
        models.Match.status == "UPCOMING"
    ).order_by(models.Match.start_time).limit(limit).all()

@app.get("/matches/finished", response_model=List[MatchOut])
def get_finished_matches(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(database.get_db)
):
    """Matchs terminés (paginés)"""
    return db.query(models.Match).filter(
        models.Match.status == "FINISHED"
    ).order_by(desc(models.Match.start_time)).offset(skip).limit(limit).all()

@app.get("/matches/search", response_model=List[MatchOut])
def search_matches(
    q: str = Query(..., min_length=2, description="Recherche par équipe ou ligue"),
    db: Session = Depends(database.get_db)
):
    """Recherche de matchs par nom d'équipe ou ligue"""
    search_term = f"%{q}%"
    return db.query(models.Match).join(
        models.League, models.Match.league_id == models.League.id, isouter=True
    ).filter(
        or_(
            models.Match.home_team.ilike(search_term),
            models.Match.away_team.ilike(search_term),
            models.League.name.ilike(search_term)
        )
    ).order_by(desc(models.Match.start_time)).limit(30).all()

# ============================================
# 📊 ROUTES LIVE STATS
# ============================================

@app.get("/matches/{match_id}/live", response_model=Optional[LiveStatOut])
def get_latest_live_stat(match_id: str, db: Session = Depends(database.get_db)):
    """Dernières stats live d'un match"""
    stat = db.query(models.MatchLiveStat).filter(
        models.MatchLiveStat.match_id == match_id
    ).order_by(desc(models.MatchLiveStat.recorded_at)).first()
    
    if not stat:
        raise HTTPException(status_code=404, detail="Aucune stat live pour ce match")
    return stat

@app.get("/matches/{match_id}/live/history", response_model=List[LiveStatOut])
def get_match_live_history(
    match_id: str,
    limit: int = Query(100, le=500),
    db: Session = Depends(database.get_db)
):
    """Historique complet des stats live (timeline)"""
    return db.query(models.MatchLiveStat).filter(
        models.MatchLiveStat.match_id == match_id
    ).order_by(models.MatchLiveStat.recorded_at).limit(limit).all()

@app.get("/matches/live/alerts")
def get_live_alerts(
    min_attacks: int = Query(15, description="Seuil attaques dangereuses"),
    min_shots: int = Query(8, description="Seuil tirs cadrés"),
    min_possession_gap: int = Query(20, description="Écart possession minimum"),
    db: Session = Depends(database.get_db)
):
    """Détecte les matchs avec activité anormale (opportunités de paris)"""
    
    # Récupère les dernières stats de chaque match live
    subquery = db.query(
        models.MatchLiveStat.match_id,
        func.max(models.MatchLiveStat.recorded_at).label("max_time")
    ).group_by(models.MatchLiveStat.match_id).subquery()
    
    latest_stats = db.query(models.MatchLiveStat).join(
        subquery,
        and_(
            models.MatchLiveStat.match_id == subquery.c.match_id,
            models.MatchLiveStat.recorded_at == subquery.c.max_time
        )
    ).filter(models.MatchLiveStat.status == "LIVE").all()
    
    alerts = []
    
    for stat in latest_stats:
        match = db.query(models.Match).filter(models.Match.id == stat.match_id).first()
        if not match:
            continue
            
        # Détection d'attaques dangereuses élevées
        if stat.dangerous_attacks_home >= min_attacks:
            alerts.append({
                "match": match,
                "alert_type": "HIGH_ATTACKS_HOME",
                "alert_value": stat.dangerous_attacks_home,
                "message": f"{match.home_team} a {stat.dangerous_attacks_home} attaques dangereuses"
            })
        
        if stat.dangerous_attacks_away >= min_attacks:
            alerts.append({
                "match": match,
                "alert_type": "HIGH_ATTACKS_AWAY",
                "alert_value": stat.dangerous_attacks_away,
                "message": f"{match.away_team} a {stat.dangerous_attacks_away} attaques dangereuses"
            })
        
        # Détection de tirs cadrés élevés
        if stat.shots_on_target_home and stat.shots_on_target_home >= min_shots:
            alerts.append({
                "match": match,
                "alert_type": "HIGH_SHOTS_HOME",
                "alert_value": stat.shots_on_target_home,
                "message": f"{match.home_team} domine avec {stat.shots_on_target_home} tirs cadrés"
            })
        
        if stat.shots_on_target_away and stat.shots_on_target_away >= min_shots:
            alerts.append({
                "match": match,
                "alert_type": "HIGH_SHOTS_AWAY",
                "alert_value": stat.shots_on_target_away,
                "message": f"{match.away_team} domine avec {stat.shots_on_target_away} tirs cadrés"
            })
        
        # Détection de domination possession
        if stat.possession_home and stat.possession_away:
            poss_gap = abs(stat.possession_home - stat.possession_away)
            if poss_gap >= min_possession_gap:
                dominator = match.home_team if stat.possession_home > stat.possession_away else match.away_team
                dominant_poss = max(stat.possession_home, stat.possession_away)
                alerts.append({
                    "match": match,
                    "alert_type": "POSSESSION_DOMINATION",
                    "alert_value": poss_gap,
                    "message": f"{dominator} domine la possession ({dominant_poss}%)"
                })
    
    return {
        "timestamp": datetime.now(),
        "total_alerts": len(alerts),
        "alerts": alerts
    }

# ============================================
# 💰 ROUTES ODDS / COTES
# ============================================

@app.get("/matches/{match_id}/odds", response_model=Optional[OddsOut])
def get_latest_odds(match_id: str, db: Session = Depends(database.get_db)):
    """Dernières cotes enregistrées pour un match"""
    odd = db.query(models.OddsHistory).filter(
        models.OddsHistory.match_id == match_id
    ).order_by(desc(models.OddsHistory.recorded_at)).first()
    
    if not odd:
        raise HTTPException(status_code=404, detail="Aucune cote disponible")
    return odd

@app.get("/matches/{match_id}/odds/history", response_model=List[OddsHistoryOut])
def get_match_odds_history(
    match_id: str,
    limit: int = Query(100, le=500),
    db: Session = Depends(database.get_db)
):
    """Historique complet des cotes d'un match"""
    return db.query(models.OddsHistory).filter(
        models.OddsHistory.match_id == match_id
    ).order_by(models.OddsHistory.recorded_at).limit(limit).all()

@app.get("/odds/drops")
def get_odds_drops(
    min_drop_percentage: float = Query(10.0, description="Baisse minimum en %"),
    time_window_minutes: int = Query(60, description="Fenêtre temporelle"),
    db: Session = Depends(database.get_db)
):
    """Baisses de cotes significatives (value betting)"""
    
    time_threshold = datetime.now() - timedelta(minutes=time_window_minutes)
    
    # Récupère les deux dernières cotes pour chaque match
    subquery_latest = db.query(
        models.OddsHistory.match_id,
        func.max(models.OddsHistory.recorded_at).label("latest_time")
    ).filter(
        models.OddsHistory.recorded_at >= time_threshold
    ).group_by(models.OddsHistory.match_id).subquery()
    
    latest_odds = db.query(models.OddsHistory).join(
        subquery_latest,
        and_(
            models.OddsHistory.match_id == subquery_latest.c.match_id,
            models.OddsHistory.recorded_at == subquery_latest.c.latest_time
        )
    ).all()
    
    drops = []
    
    for latest_odd in latest_odds:
        # Récupère la cote précédente
        previous_odd = db.query(models.OddsHistory).filter(
            models.OddsHistory.match_id == latest_odd.match_id,
            models.OddsHistory.recorded_at < latest_odd.recorded_at
        ).order_by(desc(models.OddsHistory.recorded_at)).first()
        
        if not previous_odd:
            continue
        
        # Calcul des baisses en pourcentage
        drop_1 = ((previous_odd.odd_1 - latest_odd.odd_1) / previous_odd.odd_1) * 100 if previous_odd.odd_1 > 0 else 0
        drop_x = ((previous_odd.odd_x - latest_odd.odd_x) / previous_odd.odd_x) * 100 if previous_odd.odd_x > 0 else 0
        drop_2 = ((previous_odd.odd_2 - latest_odd.odd_2) / previous_odd.odd_2) * 100 if previous_odd.odd_2 > 0 else 0
        
        match = db.query(models.Match).filter(models.Match.id == latest_odd.match_id).first()
        
        if drop_1 >= min_drop_percentage:
            drops.append({
                "match": match,
                "bet_type": "1 (Victoire domicile)",
                "old_odd": previous_odd.odd_1,
                "new_odd": latest_odd.odd_1,
                "drop_percentage": round(drop_1, 2),
                "time_diff": (latest_odd.recorded_at - previous_odd.recorded_at).total_seconds() / 60
            })
        
        if drop_x >= min_drop_percentage:
            drops.append({
                "match": match,
                "bet_type": "X (Match nul)",
                "old_odd": previous_odd.odd_x,
                "new_odd": latest_odd.odd_x,
                "drop_percentage": round(drop_x, 2),
                "time_diff": (latest_odd.recorded_at - previous_odd.recorded_at).total_seconds() / 60
            })
        
        if drop_2 >= min_drop_percentage:
            drops.append({
                "match": match,
                "bet_type": "2 (Victoire extérieur)",
                "old_odd": previous_odd.odd_2,
                "new_odd": latest_odd.odd_2,
                "drop_percentage": round(drop_2, 2),
                "time_diff": (latest_odd.recorded_at - previous_odd.recorded_at).total_seconds() / 60
            })
    
    return {
        "timestamp": datetime.now(),
        "total_drops": len(drops),
        "drops": sorted(drops, key=lambda x: x["drop_percentage"], reverse=True)
    }

@app.get("/odds/movements")
def get_odds_movements(
    min_change_percentage: float = Query(5.0, description="Variation minimum en %"),
    time_window_minutes: int = Query(120, description="Fenêtre temporelle"),
    db: Session = Depends(database.get_db)
):
    """Variations anormales de cotes (odd swing detection)"""
    
    time_threshold = datetime.now() - timedelta(minutes=time_window_minutes)
    
    subquery_latest = db.query(
        models.OddsHistory.match_id,
        func.max(models.OddsHistory.recorded_at).label("latest_time")
    ).filter(
        models.OddsHistory.recorded_at >= time_threshold
    ).group_by(models.OddsHistory.match_id).subquery()
    
    latest_odds = db.query(models.OddsHistory).join(
        subquery_latest,
        and_(
            models.OddsHistory.match_id == subquery_latest.c.match_id,
            models.OddsHistory.recorded_at == subquery_latest.c.latest_time
        )
    ).all()
    
    movements = []
    
    for latest_odd in latest_odds:
        previous_odd = db.query(models.OddsHistory).filter(
            models.OddsHistory.match_id == latest_odd.match_id,
            models.OddsHistory.recorded_at < latest_odd.recorded_at
        ).order_by(desc(models.OddsHistory.recorded_at)).first()
        
        if not previous_odd:
            continue
        
        # Calcul des variations (peut être positif ou négatif)
        change_1 = ((latest_odd.odd_1 - previous_odd.odd_1) / previous_odd.odd_1) * 100 if previous_odd.odd_1 > 0 else 0
        change_x = ((latest_odd.odd_x - previous_odd.odd_x) / previous_odd.odd_x) * 100 if previous_odd.odd_x > 0 else 0
        change_2 = ((latest_odd.odd_2 - previous_odd.odd_2) / previous_odd.odd_2) * 100 if previous_odd.odd_2 > 0 else 0
        
        max_change = max(abs(change_1), abs(change_x), abs(change_2))
        
        if max_change >= min_change_percentage:
            match = db.query(models.Match).filter(models.Match.id == latest_odd.match_id).first()
            time_diff = (latest_odd.recorded_at - previous_odd.recorded_at).total_seconds() / 60
            
            movement_type = "DROP" if change_1 < 0 or change_x < 0 or change_2 < 0 else "RISE"
            
            movements.append({
                "match_id": latest_odd.match_id,
                "match": match,
                "old_odd_1": previous_odd.odd_1,
                "new_odd_1": latest_odd.odd_1,
                "old_odd_x": previous_odd.odd_x,
                "new_odd_x": latest_odd.odd_x,
                "old_odd_2": previous_odd.odd_2,
                "new_odd_2": latest_odd.odd_2,
                "change_1": round(change_1, 2),
                "change_x": round(change_x, 2),
                "change_2": round(change_2, 2),
                "time_diff_minutes": round(time_diff, 2),
                "movement_type": movement_type
            })
    
    return {
        "timestamp": datetime.now(),
        "total_movements": len(movements),
        "movements": sorted(movements, key=lambda x: max(abs(x["change_1"]), abs(x["change_x"]), abs(x["change_2"])), reverse=True)
    }

# ============================================
# ⭐ ROUTES FAVORITES
# ============================================

@app.get("/favorites", response_model=List[FavoriteOut])
def get_favorites(db: Session = Depends(database.get_db)):
    """Tous les matchs favoris"""
    return db.query(models.Favorite).all()

@app.post("/favorites", status_code=status.HTTP_201_CREATED)
def add_favorite(fav_data: FavoriteCreate, db: Session = Depends(database.get_db)):
    """Ajouter un match en favori"""
    match_exists = db.query(models.Match).filter(models.Match.id == fav_data.match_id).first()
    if not match_exists:
        raise HTTPException(status_code=404, detail="Match non trouvé")
    
    existing = db.query(models.Favorite).filter(models.Favorite.match_id == fav_data.match_id).first()
    if existing:
        return {"message": "Match déjà en favori", "favorite": existing}
    
    new_fav = models.Favorite(
        match_id=fav_data.match_id,
        initial_odd=fav_data.initial_odd,
        bet_type=fav_data.bet_type,
        detected_at=datetime.now()
    )
    db.add(new_fav)
    db.commit()
    db.refresh(new_fav)
    return {"status": "success", "favorite": new_fav}

@app.delete("/favorites/{match_id}")
def delete_favorite(match_id: str, db: Session = Depends(database.get_db)):
    """Supprimer un favori"""
    fav = db.query(models.Favorite).filter(models.Favorite.match_id == match_id).first()
    if not fav:
        raise HTTPException(status_code=404, detail="Favori non trouvé")
    
    db.delete(fav)
    db.commit()
    return {"status": "success", "message": "Favori supprimé"}

@app.get("/favorites/live", response_model=List[FavoriteOut])
def get_live_favorites(db: Session = Depends(database.get_db)):
    """Favoris actuellement en live"""
    return db.query(models.Favorite).join(
        models.Match
    ).filter(
        models.Match.status == "LIVE"
    ).all()

# ============================================
# 📈 ROUTES DASHBOARD / GLOBAL
# ============================================

@app.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(database.get_db)):
    """Résumé ultra-rapide pour les compteurs du Dashboard"""
    return {
        "counters": {
            "total_matches": db.query(models.Match).count(),
            "live": db.query(models.Match).filter(models.Match.status == "LIVE").count(),
            "upcoming": db.query(models.Match).filter(models.Match.status == "UPCOMING").count(),
            "finished": db.query(models.Match).filter(models.Match.status == "FINISHED").count(),
            "leagues": db.query(models.League).count(),
            "favorites": db.query(models.Favorite).count()
        },
        "system_time": datetime.now()
    }

@app.get("/dashboard/live-summary", response_model=List[MatchOut])
def get_live_summary(db: Session = Depends(database.get_db)):
    """Résumé de tous les matchs LIVE avec leurs dernières stats"""
    return db.query(models.Match).filter(
        models.Match.status == "LIVE"
    ).order_by(models.Match.start_time).all()

@app.get("/dashboard/favorites-summary", response_model=List[FavoriteOut])
def get_favorites_summary(db: Session = Depends(database.get_db)):
    """État actuel de tous les favoris (Live en premier)"""
    return db.query(models.Favorite).join(models.Match).order_by(
        desc(models.Match.status == "LIVE"),
        models.Match.start_time
    ).all()

# ============================================
# 🔧 ROUTES MAINTENANCE / TECH
# ============================================

@app.get("/health")
def health_check(db: Session = Depends(database.get_db)):
    """Vérifie si l'API et la DB sont en ligne"""
    try:
        # Test de connexion DB
        db.execute("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "uptime": "online",
        "version": "2.0",
        "database": db_status,
        "timestamp": datetime.now()
    }

@app.get("/sync/status")
def get_sync_status(db: Session = Depends(database.get_db)):
    """Vérifie la fraîcheur des données (Dernière stat live reçue)"""
    last_stat = db.query(models.MatchLiveStat).order_by(
        desc(models.MatchLiveStat.recorded_at)
    ).first()
    
    last_odd = db.query(models.OddsHistory).order_by(
        desc(models.OddsHistory.recorded_at)
    ).first()
    
    is_syncing = False
    if last_stat:
        is_syncing = last_stat.recorded_at > (datetime.now() - timedelta(minutes=10))
    
    return {
        "last_live_stat": last_stat.recorded_at if last_stat else None,
        "last_odds_update": last_odd.recorded_at if last_odd else None,
        "is_syncing": is_syncing,
        "sync_health": "active" if is_syncing else "stale",
        "checked_at": datetime.now()
    }
    
if __name__ == "__main__":
    # Récupération du port depuis le .env (défaut 8000 si non trouvé)
    app_port = int(os.getenv("PORT", 8000))
    app_host = os.getenv("HOST", "127.0.0.1")
    
    print(f"🚀 Backend démarré sur http://{app_host}:{app_port}")
    
    uvicorn.run(
        "backend.main:app", 
        host=app_host, 
        port=app_port, 
        reload=True if os.getenv("DEBUG") == "True" else False
    )