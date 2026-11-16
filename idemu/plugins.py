"""Shim: the plugin loader now lives in the idplugins project (../idplugins or $IDPLUGINS_HOME).

Everything real is in <idplugins>/idplugins/plugins.py — this module only re-exports it so
`from idemu import plugins` keeps working (server, builder, tests are unchanged). If the project
is missing, the emulator still runs and the plugin list simply reports why as a problem.
"""
from ._plugins_home import ensure_path

try:
    ensure_path()
    from idplugins.plugins import *                     # noqa: F401,F403
    from idplugins.plugins import _check_member, _import_py
except ImportError as _e:                               # idplugins project absent: the IDE opens without extensions
    DROP = None
    _MISSING = str(_e)

    def scan(app=None, base=None, log=lambda m: None):
        return public()

    def public():
        return []

    def problems():
        return [{'id': 'idplugins', 'name': 'idplugins (plugin system)', 'version': '',
                 'error': _MISSING, 'source': ''}]

    def file_for(pid, rel):
        return None

    def _check_member(name):
        return None

    _import_py = None
