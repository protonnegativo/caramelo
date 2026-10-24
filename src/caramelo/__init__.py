"""Caramelo: passive username OSINT across hundreds of sites, no API keys required.

    >>> from caramelo import investigate
    >>> dossier = investigate("johndoe")
    >>> dossier.profiles[0].url
"""
from .engine import investigate, investigate_async
from .models import Dossier, Profile
from .sites import available_categories, list_info, load_sites, update_sites
from .variants import username_variants

__all__ = [
    "Dossier", "Profile", "investigate", "investigate_async",
    "available_categories", "list_info", "load_sites", "update_sites", "username_variants",
]
__version__ = "0.1.0"
