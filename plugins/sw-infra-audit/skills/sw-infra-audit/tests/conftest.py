# Deixa `import lib.x` e `import collect`/`build_report` funcionarem a partir de scripts/
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
