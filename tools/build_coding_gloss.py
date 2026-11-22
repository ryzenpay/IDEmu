#!/usr/bin/env python3
"""Monta idemu/data/coding_gloss.json a partir das definições do NBT EVO Toolkit (MIT).

As definições do toolkit descrevem os parâmetros por coordenada do CAFD e pelo token BMW (ex.:
VIDEO_SPEEDLOCK_CONDITION), com nome/descrição em inglês e rótulo por valor.  O editor do IDEmu
(data/coding_dict.json.z, lido da libhmicoding do firmware) usa os MESMOS tokens e numera os valores
igual: as duas tabelas se juntam por token.  Esta ferramenta copia só o que junta, guarda a largura
do campo e o default para a junção ser checada em tempo de uso (idemu/coding.py: _gloss_get), e
resume os tokens do CAFD que não existem no dicionário em coding_gloss.caf_only.json para comparação
futura com outro SWFL.

    python3 tools/build_coding_gloss.py /path/to/cafd_00001ef6_definitions.json

O arquivo de origem é o de cafd_00001ef6 (v006.048.013), de
https://github.com/vandelayautollc/nbt-evo-toolkit (capabilities/coding/definitions/, MIT License,
(C) the NBT EVO Toolkit contributors) — ver idemu/data/README-coding-gloss.md e NOTICE.
"""
import json, os, sys, zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(src):
    idemu = json.loads(zlib.decompress(open(os.path.join(ROOT, 'idemu', 'data', 'coding_dict.json.z'), 'rb').read()))
    bits = {}
    for e in idemu:
        bits.setdefault(e['name'], bin(e['mask']).count('1'))
    defs = json.load(open(src, encoding='utf-8'))
    gloss, caf_only = {}, []
    for d in defs:
        tok = d.get('token')
        if not tok:
            continue
        try:
            m = str(d.get('mask') or '')
            mask = int(m[:-1], 2) if m.endswith('b') else int(m, 2) if m else 0
        except (ValueError, KeyError, TypeError):
            mask = 0
        try:
            default = int(str(d.get('default')), 16)
        except (ValueError, TypeError):
            default = 0
        rec = {'token': tok, 'name': d.get('name', ''), 'description': d.get('description', ''),
               'values': d.get('values') or {}, 'confidence': d.get('confidence', ''), 'source': d.get('source', ''),
               'coord': d.get('coord', ''), 'byte': d.get('byte'), 'bits': bin(mask).count('1'),
               'default': default}
        if tok in bits:
            gloss[tok] = rec
        else:
            caf_only.append(rec)
    out = {'source': 'NBT EVO Toolkit (github.com/vandelayautollc/nbt-evo-toolkit), capabilities/coding/definitions, '
                     'MIT License, (C) the NBT EVO Toolkit contributors. Join key: BMW token + field width.',
           'cafd': os.path.basename(src), 'defs': gloss}
    dst = os.path.join(ROOT, 'idemu', 'data', 'coding_gloss.json')
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    mism = sum(1 for t, r in gloss.items() if r['bits'] and r['bits'] != bits[t])
    print('%s: %d registros no CAFD -> %d unioes (%d com largura igual), %d so no CAFD -> coding_gloss.caf_only.json'
          % (dst, len(defs), len(gloss), len(gloss) - mism, len(caf_only)))
    with open(os.path.join(ROOT, 'idemu', 'data', 'coding_gloss.caf_only.json'), 'w', encoding='utf-8') as f:
        json.dump(caf_only, f, ensure_ascii=False)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
