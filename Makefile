# Atalhos para gerenciar o marketplace de skills.
# Uso:
#   make list
#   make sync SKILL=minha-skill [CATEGORY=development] [BUMP=patch|minor|major]
#   make sync-dry SKILL=minha-skill
#   make import SKILL=minha-skill [FORCE=1]
#   make remove SKILL=minha-skill
#   make readme

PY := python3
SCRIPT := scripts/sync_skill.py
SCAN := scripts/scan_secrets.py

# Flags opcionais montadas a partir de CATEGORY / BUMP / FROM.
FLAGS :=
ifdef CATEGORY
FLAGS += --category $(CATEGORY)
endif
ifdef BUMP
FLAGS += --bump $(BUMP)
endif
ifdef FROM
FLAGS += --from $(FROM)
endif

.PHONY: help list sync sync-dry import remove readme check hooks

help:
	@echo "make list                      - lista skills locais e quais estão publicadas"
	@echo "make sync SKILL=<nome>         - publica/atualiza uma skill (CATEGORY=, BUMP=, FROM= opcionais)"
	@echo "make sync-dry SKILL=<nome>     - prévia do sync, sem escrever"
	@echo "make import SKILL=<nome>       - traz a skill do repo p/ ~/.claude/skills editar (FORCE=1 sobrescreve)"
	@echo "make remove SKILL=<nome>       - remove uma skill do marketplace"
	@echo "make readme                    - regenera a tabela de skills do README"
	@echo "make check                     - gate de segurança: escaneia o staged por segredos/dados pessoais"
	@echo "make hooks                     - instala os git hooks (pre-commit/pre-push) deste repo"

list:
	@$(PY) $(SCRIPT) list

sync:
	@test -n "$(SKILL)" || { echo "Use: make sync SKILL=<nome>"; exit 1; }
	@$(PY) $(SCRIPT) sync $(SKILL) $(FLAGS)

sync-dry:
	@test -n "$(SKILL)" || { echo "Use: make sync-dry SKILL=<nome>"; exit 1; }
	@$(PY) $(SCRIPT) sync $(SKILL) --dry-run $(FLAGS)

import:
	@test -n "$(SKILL)" || { echo "Use: make import SKILL=<nome> [FORCE=1]"; exit 1; }
	@$(PY) $(SCRIPT) import $(SKILL) $(if $(FORCE),--force,)

remove:
	@test -n "$(SKILL)" || { echo "Use: make remove SKILL=<nome>"; exit 1; }
	@$(PY) $(SCRIPT) remove $(SKILL)

readme:
	@$(PY) $(SCRIPT) readme

check:
	@$(PY) $(SCAN) staged

hooks:
	@git config core.hooksPath .githooks
	@chmod +x .githooks/pre-commit .githooks/pre-push
	@echo "✓ git hooks instalados (core.hooksPath=.githooks): pre-commit + pre-push"
