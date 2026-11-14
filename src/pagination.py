"""Pagination traversal and page discovery manager."""
from __future__ import annotations

import logging
import re
from collections import deque
from typing import Iterator
from src.database import DatabaseManager
from src.utils import normalize_url


class PaginationTraverser:
    """Manages discovery and traversal of all pagination pages without hardcoded limits."""

    def __init__(
        self,
        db: DatabaseManager,
        start_urls: list[str],
        max_pages: int | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.db = db
        self.max_pages = max_pages
        self.logger = logger or logging.getLogger("amar_scraper.pagination")
        self.queue: deque[str] = deque()
        self.enqueued: set[str] = set()
        self.consecutive_empty_pages = 0
        self.max_consecutive_empty = 3

        # Enqueue seed URLs
        for url in start_urls:
            norm = normalize_url(url)
            self._add_to_queue(norm)

    def _add_to_queue(self, url: str) -> None:
        """Add URL to queue if not already seen or visited."""
        if url not in self.enqueued and not self.db.is_page_visited(url):
            self.enqueued.add(url)
            self.queue.append(url)

    def add_discovered_urls(self, urls: list[str]) -> None:
        """Add newly discovered pagination URLs from a parsed page."""
        for u in urls:
            norm = normalize_url(u)
            self._add_to_queue(norm)

    def generate_next_sequential_page(self, current_url: str) -> str | None:
        """Dynamically probe next sequential page number e.g. currentpage/4 -> currentpage/5."""
        match = re.search(r"/currentpage/(\d+)", current_url)
        if match:
            current_num = int(match.group(1))
            next_num = current_num + 1
            next_url = re.sub(r"/currentpage/\d+", f"/currentpage/{next_num}", current_url)
            return normalize_url(next_url)
        return None

    def record_page_result(self, page_url: str, records_count: int) -> None:
        """Record visited page and track consecutive empty pages to detect end of pagination."""
        self.db.record_visited_page(page_url, records_count)
        if records_count == 0:
            self.consecutive_empty_pages += 1
            self.logger.info(
                f"Page {page_url} yielded 0 records (empty count: {self.consecutive_empty_pages})"
            )
        else:
            self.consecutive_empty_pages = 0
            # If valid records were found and sequential url exists, ensure next sequential page is enqueued
            seq_next = self.generate_next_sequential_page(page_url)
            if seq_next:
                self._add_to_queue(seq_next)

    def has_next_page(self) -> bool:
        """Check if there are more pages to visit and termination conditions not met."""
        if self.consecutive_empty_pages >= self.max_consecutive_empty:
            self.logger.info("Reached end of pagination: consecutive empty pages threshold met.")
            return False
        return len(self.queue) > 0

    def get_next_page_url(self) -> str | None:
        """Pop next page URL from the discovery queue."""
        while self.queue:
            candidate = self.queue.popleft()
            if not self.db.is_page_visited(candidate):
                return candidate
        return None
