"""Scraper package for the Intelligent Procurement Platform."""

from scrapers.base_scraper import BaseScraper, DownloadResult
from scrapers.txdot_scraper import TxDOTScraper

__all__ = ["BaseScraper", "DownloadResult", "TxDOTScraper"]
