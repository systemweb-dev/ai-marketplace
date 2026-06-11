# Atalhos para gerenciar o marketplace de skills.
# Uso:
#   make list
#   make sync SKILL=minha-skill [CATEGORY=development] [BUMP=patch|minor|major]
#   make sync-dry SKILL=minha-skill
#   make remove SKILL=minha-skill
#   make readme

PY := python3
SCRIPT := scripts/sync_skill.py

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

.PHONY: help list sync sync-dry remove readme

help:
	@echo "make list                      - lista skills locais e quais estão publicadas"
	@echo "make sync SKILL=<nome>         - publica/atualiza uma skill (CATEGORY=, BUMP=, FROM= opcionais)"
	@echo "make sync-dry SKILL=<nome>     - prévia do sync, sem escrever"
	@echo "make remove SKILL=<nome>       - remove uma skill do marketplace"
	@echo "make readme                    - regenera a tabela de skills do README"

list:
	@$(PY) $(SCRIPT) list

sync:
	@test -n "$(SKILL)" || { echo "Use: make sync SKILL=<nome>"; exit 1; }
	@$(PY) $(SCRIPT) sync $(SKILL) $(FLAGS)

sync-dry:
	@test -n "$(SKILL)" || { echo "Use: make sync-dry SKILL=<nome>"; exit 1; }
	@$(PY) $(SCRIPT) sync $(SKILL) --dry-run $(FLAGS)

remove:
	@test -n "$(SKILL)" || { echo "Use: make remove SKILL=<nome>"; exit 1; }
	@$(PY) $(SCRIPT) remove $(SKILL)

readme:
	@$(PY) $(SCRIPT) readme
