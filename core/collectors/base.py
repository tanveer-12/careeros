"""Scraper interface for CareerOS. All ATS scrapers (Greenhouse, Lever, Ashby, etc.) implement BaseScraper."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawJob:
    source: str          # "greenhouse", "lever", "ashby"
    external_id: str     # ATS-native job ID, always a string
    source_url: str      # direct link to the job posting
    raw_payload: dict    # the full raw API response, unmodified
    company_slug: str    # the company identifier used in the API call
    scraped_at: datetime # UTC timestamp, set at scrape time


class BaseScraper(ABC):

    @property
    def source_name(self) -> str:
        """Returns the scraper's source identifier. Override as a class-level attribute."""
        raise NotImplementedError

    @abstractmethod
    async def scrape_company(self, company_slug: str) -> list[RawJob]:
        """Fetch all open jobs for one company. Returns empty list if company not found."""

    @abstractmethod
    async def scrape_companies(self, company_slugs: list[str]) -> list[RawJob]:
        """Fetch jobs for multiple companies."""


class ScraperRegistry:
    """
    Central registry of source_name → scraper class.
    Adding a new source requires one registry.register() call and nothing else.
    """

    def __init__(self) -> None:
        self._registry: dict[str, type[BaseScraper]] = {}

    def register(self, name: str, cls: type[BaseScraper]) -> None:
        self._registry[name] = cls

    def get(self, name: str) -> type[BaseScraper]:
        if name not in self._registry:
            available = ", ".join(sorted(self._registry)) or "<none registered>"
            raise KeyError(f"Unknown scraper '{name}'. Available: {available}")
        return self._registry[name]

    def all_names(self) -> list[str]:
        return list(self._registry)


registry = ScraperRegistry()
