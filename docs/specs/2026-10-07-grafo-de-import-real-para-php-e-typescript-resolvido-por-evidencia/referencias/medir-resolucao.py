"""Mede a resolução de import por EVIDÊNCIA: sem ler configuração nenhuma, casando
cada import contra o índice de sufixos dos arquivos que existem.

Rode: python3 medir-resolucao.py <raiz-de-projeto> [outra-raiz …]

Duas passadas, como o spec:
  1. relativo resolve contra a origem; qualificado casa como sufixo (único vale)
  2. uma BASE é provada para um prefixo quando >= MIN_PROVAS imports daquele prefixo
     resolveram sozinhos sob ela; o ambíguo resolve se EXATAMENTE UM dos seus
     candidatos está sob base provada. Sem voto de maioria.
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

IGNORAR = {'vendor', 'node_modules', '.git', 'dist', 'build', '.next', 'coverage', '.nuxt'}
EXTS = ['', '.ts', '.tsx', '.js', '.jsx', '.vue', '.mjs',
        '/index.ts', '/index.js', '/index.vue', '/index.tsx']
IMPORT = re.compile(
    r"""(?:^|\n)\s*(?:import\s[^'"]*from\s*|import\s*|require\()\s*['"]([^'"]+)['"]""")
MIN_PROVAS = 5


def indexar(raiz):
    idx, arqs = defaultdict(set), []
    for p in Path(raiz).rglob('*'):
        if any(x in IGNORAR for x in p.parts) or not p.is_file():
            continue
        if p.suffix not in {'.ts', '.tsx', '.js', '.jsx', '.vue', '.mjs'}:
            continue
        rel = p.relative_to(raiz).as_posix()
        arqs.append(p)
        partes = rel.split('/')
        for i in range(len(partes)):
            idx['/'.join(partes[i:])].add(rel)
    return arqs, idx


def casar(alvo, idx):
    for ext in EXTS:
        achados = idx.get(alvo + ext)
        if achados:
            return [(d, alvo + ext) for d in sorted(achados)]
    return []


def base_de(destino, sufixo):
    return destino[:len(destino) - len(sufixo)].rstrip('/')


for raiz in sys.argv[1:]:
    arqs, idx = indexar(raiz)
    bases, pendentes, c = defaultdict(Counter), [], Counter()
    for p in arqs:
        for m in IMPORT.finditer(p.read_text('utf-8', 'replace')):
            alvo = m.group(1)
            if alvo.startswith('.'):
                base = (p.parent / alvo).resolve()
                existe = any(Path(str(base) + e).exists() for e in EXTS)
                c['relativo resolvido' if existe else 'PENDURADO'] += 1
            elif alvo.startswith(('@', '~')) and '/' in alvo:
                pref, resto = alvo.split('/', 1)
                achados = casar(resto, idx)
                if len(achados) == 1:
                    c['sufixo único'] += 1
                    bases[pref][base_de(*achados[0])] += 1
                elif achados:
                    pendentes.append((pref, resto, achados))
                else:
                    c['externo (não casa com arquivo)'] += 1
            else:
                c['nome puro (externo por regra)'] += 1

    provadas = {pref: {b for b, n in cont.items() if n >= MIN_PROVAS}
                for pref, cont in bases.items()}
    for pref, resto, achados in pendentes:
        sob = [d for d, s in achados if base_de(d, s) in provadas.get(pref, set())]
        c['base provada' if len(sob) == 1 else 'NÃO RESOLVIDO'] += 1

    print(f'\n{raiz}')
    for k, v in sorted(c.items(), key=lambda kv: -kv[1]):
        print(f'   {v:5}  {k}')
    print(f'   bases provadas: { {k: sorted(v) for k, v in provadas.items() if v} }')
