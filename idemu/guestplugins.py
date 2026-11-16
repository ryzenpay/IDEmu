"""Shim: the in-car loader now lives in the idplugins project (../idplugins or $IDPLUGINS_HOME).

Everything real is in <idplugins>/idplugins/guestplugins.py — this module re-exports it (so
`from idemu import guestplugins` keeps working) and injects IDEmu's console transport
(idemu/guestfs) into it, which is what the live push to a running head unit talks through.
"""
from ._plugins_home import ensure_path

try:
    ensure_path()
    from idplugins import guestplugins as _real
    from . import guestfs as _guestfs
    _real.set_guestfs(_guestfs)                         # live paths (install/run/hmi_restart) talk through our console codec
    from idplugins.guestplugins import *                # noqa: F401,F403
    from idplugins.guestplugins import _is_host_file
except ImportError as _e:                               # idplugins project absent: baking/listing behave as "no plugins"
    class PluginError(Exception):
        pass

    _MISSING = str(_e)

    def _missing(*a, **k):
        raise PluginError(_MISSING)

    list_plugins = plugin_dir = guest_files = push_text = _missing
    install = uninstall = run = guest_list = hmi_restart = _missing

    def public_dir():
        return None
