"""Locate the external plugin system (the idplugins project) and put it on sys.path.

The plugin loaders and the plugins themselves live in their own project — by default the sibling
folder ../idplugins, overridable with $IDPLUGINS_HOME (see that project's README). The modules
idemu/plugins.py and idemu/guestplugins.py are thin shims that re-export from it, so
`from idemu import plugins, guestplugins` keeps working for the server, the builder and the tests.
"""
import os
import sys


def home_dir():
    h = os.environ.get('IDPLUGINS_HOME') or os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'idplugins'))
    h = os.path.abspath(os.path.expanduser(h))
    if not os.path.isfile(os.path.join(h, 'idplugins', '__init__.py')):
        raise ImportError('idplugins project not found at %s (clone it there or set IDPLUGINS_HOME)' % h)
    return h


def ensure_path():
    h = home_dir()
    if h not in sys.path:
        sys.path.insert(0, h)
    return h
