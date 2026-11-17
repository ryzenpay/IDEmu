#!/usr/bin/env python3
"""Gera o índice `bin/shader_index.txt` (hash fnv1a do SGX shader binário -> caminho do arquivo no firmware).

O glhost procura o substituto de um shader por esse hash (src/glhost/shgen.c -> load_glsl): sem o índice, um
shader corrigido à mão (bin/glsl/<hash>.frag) não seria achado. Os binários vêm da árvore SWFL descompactada
do ambiente (mesmo formato de `*.shd` que o HMI carrega), então o índice é reprodutível a partir do próprio
firmware do dono — nada da BMW entra no repositório.

Uso:
    python3 tools/shaders/index.py <arvore do SWFL> [saida]
    python3 tools/shaders/index.py /tmp/opencode/hmi_swfl          # escreve bin/shader_index.txt

O parse de símbolos é o mesmo do gerador (src/glhost/shgen.c): no fim do bloco há um par (contagem u16,
depois contagem×(nome NUL + 19 bytes de descrição); `kind` = 2 vertex / 3 fragment). Um arquivo que não tem
essa cauda não é shader e é ignorado.
"""
import os, sys

def fnv1a(b):
    h = 0x811c9dc5
    for x in b:
        h = ((h ^ x) * 0x01000193) & 0xffffffff
    return h

def parse_syms(b):
    """(kind, símbolos) se o bloco termina na tabela de símbolos do SGX; None caso contrário."""
    L = len(b)
    if L < 0x44:
        return None
    kind = (b[0x20] << 24) | (b[0x21] << 16) | (b[0x22] << 8) | b[0x23]
    p = L - 3
    while p > 0x40:                                     # a cauda pode começar até 19 bytes antes do fim
        n = (b[p] << 8) | b[p + 1]
        if n == 0 or n > 160:
            p -= 1
            continue
        q = p + 2
        syms = []
        ok = True
        for _ in range(n):
            e = q
            while e < L and 32 < b[e] < 127:
                e += 1
            if not (e < L and e != q and e - q < 64 and e + 19 <= L):
                ok = False
                break
            syms.append((b[q:e], e))
            q = e + 19
        if ok and q == L:
            return kind, [nm.decode('latin1') for nm, _ in syms]
        p -= 1
    return None

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    root = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'bin', 'shader_index.txt')
    found = {}
    n = 0
    for dirpath, dirs, fs in os.walk(root):
        for f in fs:
            p = os.path.join(dirpath, f)
            try:
                sz = os.path.getsize(p)
                if not (64 <= sz <= 500000):
                    continue
                b = open(p, 'rb').read()
            except OSError:
                continue
            r = parse_syms(b)
            if not r:
                continue
            n += 1
            found.setdefault(fnv1a(b), os.path.relpath(p, root))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w') as f:
        for h, rel in sorted(found.items()):
            f.write('%08x\t%s\n' % (h, rel))
    print('%d shaders lidos, %d hashes únicos -> %s' % (n, len(found), out))

if __name__ == '__main__':
    main()
