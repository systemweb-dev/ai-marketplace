#!/usr/bin/env bash
# Testa o fixer da systemweb: as fixtures (antes/depois) e a idempotência. Com arquivos como argumento,
# formata cópias deles e mostra o diff. O php-cs-fixer fica num cache fora do repo.
set -euo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/sw-standards-php/php-cs-fixer"
if [ ! -x "$CACHE/vendor/bin/php-cs-fixer" ]; then
    mkdir -p "$CACHE" && (cd "$CACHE" && composer init -n --name=sw/fixer-cache >/dev/null && composer require -n --dev -q friendsofphp/php-cs-fixer:^3.95)
fi
FIXER="$CACHE/vendor/bin/php-cs-fixer"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/tools/php-cs-fixer" "$WORK/src"
cp "$SKILL/assets/php-cs-fixer/Fixers.php" "$SKILL/assets/php-cs-fixer/autoload.php" "$WORK/tools/php-cs-fixer/"
cp "$SKILL/assets/php-cs-fixer/.php-cs-fixer.dist.php" "$WORK/"
falhas=0
if [ "$#" -gt 0 ]; then
    # prefixo numérico: dois arquivos com o mesmo nome (Rotas.php de temas diferentes) não se sobrescrevem
    i=0
    for f in "$@"; do i=$((i + 1)); cp "$f" "$WORK/src/$i-$(basename "$f")"; done
    # mostra o diff e sai com código diferente de 0 quando algum arquivo está fora do estilo
    (cd "$WORK" && "$FIXER" fix --dry-run --diff --using-cache=no 2>/dev/null)
    exit $?
fi
for entrada in "$SKILL"/assets/php-cs-fixer/fixtures/*.in.php; do
    nome="$(basename "$entrada" .in.php)"
    cp "$entrada" "$WORK/src/$nome.php"
done
(cd "$WORK" && "$FIXER" fix -q --using-cache=no)
for entrada in "$SKILL"/assets/php-cs-fixer/fixtures/*.in.php; do
    nome="$(basename "$entrada" .in.php)"
    if ! diff -u "$SKILL/assets/php-cs-fixer/fixtures/$nome.out.php" "$WORK/src/$nome.php"; then
        echo "FALHOU: $nome"; falhas=$((falhas + 1))
    fi
done
# sem cache: com ele, a segunda rodada pularia os arquivos e sempre daria 0
if ! (cd "$WORK" && "$FIXER" fix --dry-run -q --using-cache=no); then
    echo "FALHOU: segunda rodada mudou arquivos (não é idempotente)"; falhas=$((falhas + 1))
fi
[ "$falhas" -eq 0 ] && echo "fixer ok" || { echo "$falhas falha(s)"; exit 1; }
