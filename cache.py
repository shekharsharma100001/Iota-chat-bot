#!/usr/bin/env python3
"""
Fast in-memory LRU cache with optional periodic persistence.
Drop-in replacement that preserves the original public API.
"""

from __future__ import annotations

import os
import json
import pickle
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from collections import OrderedDict

# Logging
from logging_config import logger  # unchanged import

class ResponseCache:
    """Simple in-memory + optional file persistence cache (LRU)."""

    def __init__(self, cache_file: str = "cache/responses.pkl", max_size: int = 1000, persist_every: int = 50):
        self.cache_file = cache_file
        self.max_size = max_size
        self.persist_every = max(1, persist_every)

        # OrderedDict for O(1) LRU ops
        self.cache: "OrderedDict[str, str]" = OrderedDict()
        self.cache_hits = 0
        self.cache_misses = 0
        self._dirty_writes = 0

        # Ensure directory exists; load if present (non-blocking best effort)
        Path("cache").mkdir(exist_ok=True)
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, "rb") as f:
                    data = pickle.load(f)
                    if isinstance(data, dict):
                        # keep order best-effort
                        self.cache = OrderedDict(data)
                logger.info(f"Loaded {len(self.cache)} cached responses")
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
            self.cache = OrderedDict()

    # ---------- internals ----------
    @staticmethod
    def _normalize(s: str) -> str:
        return (s or "").strip().lower()

    def _generate_cache_key(self, user_input: str, context_hash: str) -> str:
        combined = f"{self._normalize(user_input)}:{context_hash}"
        return hashlib.md5(combined.encode()).hexdigest()

    def _save_cache(self) -> None:
        """Persist to disk (called periodically, not every set)."""
        try:
            tmp = self.cache_file + ".tmp"
            with open(tmp, "wb") as f:
                pickle.dump(dict(self.cache), f, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(tmp, self.cache_file)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    # ---------- public API (unchanged) ----------
    def get(self, user_input: str, context_hash: str) -> Optional[str]:
        """Get cached response if available"""
        cache_key = self._generate_cache_key(user_input, context_hash)
        if cache_key in self.cache:
            self.cache_hits += 1
            # touch LRU
            val = self.cache.pop(cache_key)
            self.cache[cache_key] = val
            # quieter logs on hot path
            return val
        self.cache_misses += 1
        return None

    def set(self, user_input: str, context_hash: str, response: str):
        """Cache a new response (deferred disk write)"""
        cache_key = self._generate_cache_key(user_input, context_hash)

        # insert / update, touch LRU
        if cache_key in self.cache:
            self.cache.pop(cache_key)
        self.cache[cache_key] = response

        # evict oldest 20% when over capacity
        if len(self.cache) > self.max_size:
            remove_count = max(1, int(self.max_size * 0.2))
            for _ in range(remove_count):
                self.cache.popitem(last=False)
            logger.info(f"Cache cleaned: removed ~{remove_count} old entries")

        # deferred persistence
        self._dirty_writes += 1
        if self._dirty_writes >= self.persist_every:
            self._save_cache()
            self._dirty_writes = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics (keys preserved for UI/CLI)"""
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total) if total else 0.0
        return {
            "total_entries": len(self.cache),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": hit_rate,  # 0..1 as your UI expects
        }

    def clear_cache(self):
        """Clear all cached responses"""
        self.cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        try:
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
        except Exception:
            pass
        logger.info("Cache cleared")

    def export_cache_stats(self, filename: str = "cache_stats.json"):
        """Export cache statistics to JSON file"""
        stats = self.get_stats()
        stats["exported_at"] = datetime.now().isoformat()
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(stats, f, indent=2)
            logger.info(f"Cache stats exported to {filename}")
        except Exception as e:
            logger.error(f"Failed to export cache stats: {e}")

# Initialize cache instance (name preserved)
response_cache = ResponseCache()
