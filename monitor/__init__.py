"""
monitor/__init__.py
Package de monitoring de matchs avec détection d'opportunités de paris.

Ce package contient deux modules principaux :
- betting_logic : Analyse et détection d'opportunités de pari
- scraper_engine : Extraction de données depuis 1xbet.cm
"""

from .betting_logic import BettingAnalyzer
from .scraper_engine import MatchScraper

__version__ = "1.0.0"
__author__ = "Votre Nom"

__all__ = ["BettingAnalyzer", "MatchScraper"]