# Centralized TTL cache management for auth, contacts, events, and CalDAV helpers.

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List

from cachetools import TTLCache
from fastapi import Response

from src.settings import get_settings

DEFAULT_CACHE_TTL = 60
DEFAULT_CACHE_MAXSIZE = 256


def _make_cache(maxsize: int = DEFAULT_CACHE_MAXSIZE, ttl: int = DEFAULT_CACHE_TTL) -> TTLCache:
    return TTLCache(maxsize=maxsize, ttl=ttl)


def build_cache_key(user: str, *parts: str) -> str:
    """Compose a namespaced cache key per user."""
    return "|".join([user] + list(parts))


def cache_ttl(cache: TTLCache, key: str) -> str:
    """
    Return remaining TTL in seconds for the key.

    Supports cachetools versions without get_ttl by falling back to internal expiry map.
    """
    try:
        exp = cache.get_ttl(key)  # type: ignore[attr-defined]
    except Exception:
        exp = None
    if exp is None:
        try:
            exp_time = cache._TTLCache__expires.get(key)  # type: ignore[attr-defined]
            if exp_time is not None:
                exp = exp_time - cache.timer()
        except Exception:
            exp = None
    if exp is None:
        return "0"
    return str(max(0, int(exp)))


def set_cache_headers(response: Response, cache: TTLCache, key: str, hit: bool) -> None:
    """Write cache headers consistently."""
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    response.headers["X-Cache-TTL"] = cache_ttl(cache, key)


def set_cache_bypass(response: Response) -> None:
    """Indicate caching bypass (used after writes)."""
    response.headers["X-Cache"] = "BYPASS"


@dataclass
class AuthCache:
    cache: TTLCache


@dataclass
class ContactCaches:
    by_uid: TTLCache
    list_all: TTLCache
    search: TTLCache


@dataclass
class EventCaches:
    by_uid: TTLCache
    by_range: TTLCache
    calendars: TTLCache


@dataclass
class TaskCaches:
    by_uid: TTLCache
    by_range: TTLCache
    calendars: TTLCache


@dataclass
class CaldavCaches:
    event_url: TTLCache
    event_obj: TTLCache
    calendars: TTLCache
    todo_url: TTLCache
    todo_obj: TTLCache


@lru_cache(maxsize=1)
def get_auth_cache() -> AuthCache:
    settings = get_settings()
    return AuthCache(cache=_make_cache(maxsize=settings.auth_cache_size, ttl=settings.auth_cache_ttl))


@lru_cache(maxsize=1)
def get_contact_caches() -> ContactCaches:
    return ContactCaches(
        by_uid=_make_cache(maxsize=256, ttl=60),
        list_all=_make_cache(maxsize=128, ttl=60),
        search=_make_cache(maxsize=128, ttl=60),
    )


@lru_cache(maxsize=1)
def get_event_caches() -> EventCaches:
    return EventCaches(
        by_uid=_make_cache(maxsize=256, ttl=60),
        by_range=_make_cache(maxsize=128, ttl=60),
        calendars=_make_cache(maxsize=128, ttl=900),
    )


@lru_cache(maxsize=1)
def get_task_caches() -> TaskCaches:
    return TaskCaches(
        by_uid=_make_cache(maxsize=256, ttl=60),
        by_range=_make_cache(maxsize=128, ttl=60),
        calendars=_make_cache(maxsize=128, ttl=900),
    )


@lru_cache(maxsize=1)
def get_caldav_caches() -> CaldavCaches:
    return CaldavCaches(
        event_url=_make_cache(maxsize=512, ttl=600),
        event_obj=_make_cache(maxsize=512, ttl=600),
        calendars=_make_cache(maxsize=256, ttl=900),
        todo_url=_make_cache(maxsize=512, ttl=600),
        todo_obj=_make_cache(maxsize=512, ttl=600),
    )


def invalidate_contact_caches_for_user(username: str) -> None:
    caches = get_contact_caches()
    prefix = f"{username}|"
    for cache in (caches.by_uid, caches.list_all, caches.search):
        keys = [k for k in cache if str(k).startswith(prefix)]
        for k in keys:
            cache.pop(k, None)


def invalidate_event_caches_for_user(username: str) -> None:
    caches = get_event_caches()
    prefix = f"{username}|"
    for cache in (caches.by_uid, caches.by_range, caches.calendars):
        keys = [k for k in cache if str(k).startswith(prefix)]
        for k in keys:
            cache.pop(k, None)


def invalidate_task_caches_for_user(username: str) -> None:
    caches = get_task_caches()
    prefix = f"{username}|"
    for cache in (caches.by_uid, caches.by_range, caches.calendars):
        keys = [k for k in cache if str(k).startswith(prefix)]
        for k in keys:
            cache.pop(k, None)


def clear_all_caches() -> None:
    """For tests: clear all caches."""
    for cache_container in (get_auth_cache(), get_contact_caches(), get_event_caches(), get_task_caches(), get_caldav_caches()):
        for cache in cache_container.__dict__.values():
            cache.clear()
