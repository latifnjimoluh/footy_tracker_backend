
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

# ============================================
# 🏆 TABLE LEAGUES
# ============================================

class League(Base):
    """Table des ligues/compétitions de football"""
    __tablename__ = "leagues"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    url = Column(Text, nullable=True)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relations
    matches = relationship("Match", back_populates="league", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<League(id={self.id}, name={self.name})>"


# ============================================
# ⚽ TABLE MATCHES
# ============================================

class Match(Base):
    """Table principale des matchs de football"""
    __tablename__ = "matches"
    
    id = Column(String, primary_key=True, index=True)
    league_id = Column(String, ForeignKey("leagues.id", ondelete="CASCADE"), nullable=True)
    home_team = Column(String, nullable=False, index=True)
    away_team = Column(String, nullable=False, index=True)
    start_time = Column(DateTime, nullable=True, index=True)
    match_url = Column(Text, nullable=True)
    
    # Statut du match: UPCOMING, LIVE, FINISHED, POSTPONED, CANCELLED
    status = Column(String, nullable=True, default="UPCOMING", index=True)
    
    # Score final (rempli après le match)
    score_home = Column(Integer, nullable=True)
    score_away = Column(Integer, nullable=True)
    
    # Relations
    league = relationship("League", back_populates="matches")
    stats = relationship(
        "MatchLiveStat", 
        back_populates="match", 
        order_by="desc(MatchLiveStat.recorded_at)",
        cascade="all, delete-orphan"
    )
    odds_history = relationship(
        "OddsHistory", 
        back_populates="match",
        order_by="desc(OddsHistory.recorded_at)",
        cascade="all, delete-orphan"
    )
    favorite = relationship("Favorite", back_populates="match", uselist=False)
    
    # Index composé pour améliorer les performances des requêtes
    __table_args__ = (
        Index('idx_match_status_start', 'status', 'start_time'),
        Index('idx_match_league_status', 'league_id', 'status'),
    )
    
    def __repr__(self):
        return f"<Match(id={self.id}, {self.home_team} vs {self.away_team}, status={self.status})>"


# ============================================
# 📊 TABLE MATCH_LIVE_STATS
# ============================================

class MatchLiveStat(Base):
    """Statistiques live d'un match (enregistrées périodiquement)"""
    __tablename__ = "match_live_stats"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Statut au moment de l'enregistrement
    status = Column(String, nullable=True)  # LIVE, HT (mi-temps), FT (terminé)
    
    # Scores
    score_home = Column(Integer, default=0)
    score_away = Column(Integer, default=0)
    ht_score = Column(String, nullable=True)  # Ex: "1-0" à la mi-temps
    
    # Horloge du match
    game_clock = Column(String, nullable=True)  # Ex: "45+2", "67'"
    
    # Statistiques d'attaque
    attacks_home = Column(Integer, default=0)
    attacks_away = Column(Integer, default=0)
    dangerous_attacks_home = Column(Integer, default=0)
    dangerous_attacks_away = Column(Integer, default=0)
    
    # Possession
    possession_home = Column(Integer, nullable=True)  # Pourcentage (0-100)
    possession_away = Column(Integer, nullable=True)
    
    # Tirs
    shots_on_target_home = Column(Integer, default=0)
    shots_on_target_away = Column(Integer, default=0)
    
    # Corners
    corners_home = Column(Integer, default=0)
    corners_away = Column(Integer, default=0)
    
    # Probabilités (format JSON string si nécessaire)
    probabilities = Column(Text, nullable=True)  # Ex: '{"home":45,"draw":30,"away":25}'
    
    # Timestamp de l'enregistrement
    recorded_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    
    # Relations
    match = relationship("Match", back_populates="stats")
    
    # Index pour optimiser les requêtes temporelles
    __table_args__ = (
        Index('idx_liveStat_match_recorded', 'match_id', 'recorded_at'),
        Index('idx_liveStat_status', 'status'),
    )
    
    def __repr__(self):
        return f"<MatchLiveStat(match={self.match_id}, score={self.score_home}-{self.score_away}, time={self.game_clock})>"


# ============================================
# 💰 TABLE ODDS_HISTORY
# ============================================

class OddsHistory(Base):
    """Historique des cotes d'un match (1-X-2)"""
    __tablename__ = "odds_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(String, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Cotes 1-X-2
    odd_1 = Column(Float, nullable=False)  # Victoire domicile
    odd_x = Column(Float, nullable=False)  # Match nul
    odd_2 = Column(Float, nullable=False)  # Victoire extérieur
    
    # Timestamp de l'enregistrement
    recorded_at = Column(DateTime, default=datetime.now, nullable=False, index=True)
    
    # Relations
    match = relationship("Match", back_populates="odds_history")
    
    # Index pour optimiser les requêtes de suivi des cotes
    __table_args__ = (
        Index('idx_odds_match_recorded', 'match_id', 'recorded_at'),
    )
    
    def __repr__(self):
        return f"<OddsHistory(match={self.match_id}, odds={self.odd_1}/{self.odd_x}/{self.odd_2})>"


# ============================================
# ⭐ TABLE FAVORITES
# ============================================

class Favorite(Base):
    """Matchs ajoutés aux favoris par l'utilisateur"""
    __tablename__ = "favorites"
    
    match_id = Column(String, ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True)
    
    # Cote initiale au moment de l'ajout (pour tracking)
    initial_odd = Column(Float, default=0.0)
    
    # Type de pari suivi: "1", "X", "2"
    bet_type = Column(String, default="1", nullable=False)
    
    # Timestamp d'ajout aux favoris
    detected_at = Column(DateTime, default=datetime.now, nullable=False)
    
    # Relations
    match = relationship("Match", back_populates="favorite")
    
    def __repr__(self):
        return f"<Favorite(match={self.match_id}, bet={self.bet_type}, odd={self.initial_odd})>"


# ============================================
# 📝 NOTES SUR L'ARCHITECTURE
# ============================================
