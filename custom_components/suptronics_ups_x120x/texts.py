"""Texts shown to the user outside the entity layer.

Entity names and states come from ``strings.json`` and are translated by Home
Assistant itself. Persistent notifications are not: their text is whatever the
integration passes in, so the translations live here, keyed by the language
configured in Home Assistant (``hass.config.language``). Anything that is not
covered falls back to English.
"""

from __future__ import annotations

from typing import Final

NOTIFICATIONS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "shutdown_soon_title": "UPS: shutting down soon",
        "shutdown_soon_level": (
            "The UPS is on battery at {capacity:.0f}%, at or below the "
            "{threshold:.0f}% threshold. The Raspberry Pi will be shut down in "
            "{seconds} seconds unless mains power returns.\n\n"
            "To stop it, turn off **Shutdown on low battery** on the UPS device."
        ),
        "shutdown_soon_time": (
            "The UPS has been on battery for {minutes} minutes, which is the "
            "configured limit. The Raspberry Pi will be shut down in {seconds} "
            "seconds unless mains power returns.\n\n"
            "To stop it, turn off **Shutdown on low battery** on the UPS device."
        ),
        "shutdown_impossible_title": "UPS: shutdown not possible",
        "shutdown_impossible": (
            "The battery is at {capacity:.0f}% and the Raspberry Pi should be "
            "shut down now, but this installation type cannot shut its own host "
            "down. A `{event}` event has been fired: an automation can react "
            "to it."
        ),
    },
    "cs": {
        "shutdown_soon_title": "UPS: brzy dojde k vypnutí",
        "shutdown_soon_level": (
            "UPS běží na baterii s kapacitou {capacity:.0f} %, což je na prahu "
            "{threshold:.0f} % nebo pod ním. Raspberry Pi bude za {seconds} "
            "sekund vypnuto, pokud se neobnoví síťové napájení.\n\n"
            "Vypnutí zastavíte přepínačem **Vypnout při slabé baterii** na "
            "zařízení UPS."
        ),
        "shutdown_soon_time": (
            "UPS běží na baterii už {minutes} minut, což je nastavený limit. "
            "Raspberry Pi bude za {seconds} sekund vypnuto, pokud se neobnoví "
            "síťové napájení.\n\n"
            "Vypnutí zastavíte přepínačem **Vypnout při slabé baterii** na "
            "zařízení UPS."
        ),
        "shutdown_impossible_title": "UPS: vypnutí není možné",
        "shutdown_impossible": (
            "Baterie je na {capacity:.0f} % a Raspberry Pi by se teď mělo "
            "vypnout, ale tento typ instalace neumí vypnout vlastního hostitele. "
            "Byla vyvolána událost `{event}`, na kterou může reagovat "
            "automatizace."
        ),
    },
}


def notification_text(language: str | None, key: str, **values: object) -> str:
    """Return the notification text for the language, English when unknown."""
    lang = (language or "en").split("-")[0].lower()
    texts = NOTIFICATIONS.get(lang, NOTIFICATIONS["en"])
    return texts.get(key, NOTIFICATIONS["en"][key]).format(**values)
