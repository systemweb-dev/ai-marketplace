# Deixa `import lib.x` e `import collect`/`build_report` funcionarem a partir de scripts/
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
# E `from test_adaptador_promql import ...`: o Prometheus de mentira é definido lá, e copiá-lo
# para cada arquivo faria duas versões divergirem — um servidor falso que mente diferente em
# cada teste é pior que não ter servidor falso.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
