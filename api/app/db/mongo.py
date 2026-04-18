"""Typed collection accessors."""

from app.core.database import get_collection


def search_cache():
    return get_collection("search_cache")


def courses():
    return get_collection("courses")


def glass_sets():
    return get_collection("glass_sets")


def game_sessions():
    return get_collection("game_sessions")


def players():
    return get_collection("players")


def scores():
    return get_collection("scores")


def design_settings():
    return get_collection("design_settings")


def preorders():
    return get_collection("preorders")
