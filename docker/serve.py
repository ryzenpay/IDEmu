"""Entrypoint do container: mesmo `idemu gui`, mas ouvindo em todas as interfaces.

O `python3 -m idemu gui` amarra o servidor em 127.0.0.1 (ok no desktop); num container
precisa aceitar o tráfego publicado pelo docker. IDEMU_HOST/IDEEMU_PORT sobrescrevem.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from idemu import server

server.serve(host=os.environ.get('IDEEMU_HOST', '0.0.0.0'),
             port=int(os.environ.get('IDEEMU_PORT', '8765')),
             open_browser=False)
