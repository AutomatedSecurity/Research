PROJECT_PATH ?=
ENTRY_PREFIX ?= server/api
TOP ?= 25
FANIN_ENGINE ?= codeql
CODEQL_DB_DIR ?=
VULN_TOP ?= 25
VULN_MAX_FINDINGS ?= 300
SKIP_VULN ?= 0
PRIORITIZE_TOP ?= 25
SKIP_PRIORITIZE ?= 0
LLM_MODEL ?= gpt-5.3-codex
LLM_PROVIDER ?= openai-compatible
LLM_AUTH_FILE ?=
LLM_AUTH_PROFILE ?=
LLM_MAX_FILES ?= 80
LLM_MAX_CHARS ?= 5000
LLM_MAX_TREE ?= 250
LLM_USE_TOOLS ?= 1
INCLUDE_SIGNALS ?= 1
SKIP_LLM ?= 0

# make test PROJECT_PATH=../WackoPicko ENTRY_PREFIX=website TOP=20

.PHONY: test fanin git-history vuln llm connect

test:
	@if [ -z "$(PROJECT_PATH)" ]; then \
		 echo "Usage: make test PROJECT_PATH=/absolute/path/to/project [ENTRY_PREFIX=server/api] [TOP=25] [FANIN_ENGINE=codeql|heuristic] [SKIP_VULN=0|1] [SKIP_PRIORITIZE=0|1] [LLM_PROVIDER=openai-compatible] [LLM_MODEL=gpt-5.3-codex]"; \
		exit 1; \
	fi
	python3 run_pipeline.py "$(PROJECT_PATH)" --entry-prefix "$(ENTRY_PREFIX)" --top "$(TOP)" --fanin-engine "$(FANIN_ENGINE)" $$( [ -n "$(CODEQL_DB_DIR)" ] && echo "--codeql-db-dir $(CODEQL_DB_DIR)" ) --vuln-top "$(VULN_TOP)" --vuln-max-findings "$(VULN_MAX_FINDINGS)" --$$( [ "$(SKIP_VULN)" = "1" ] && echo skip-vuln || echo no-skip-vuln ) --llm-provider "$(LLM_PROVIDER)" --llm-model "$(LLM_MODEL)" $$( [ -n "$(LLM_AUTH_FILE)" ] && echo "--llm-auth-file $(LLM_AUTH_FILE)" ) $$( [ -n "$(LLM_AUTH_PROFILE)" ] && echo "--llm-auth-profile $(LLM_AUTH_PROFILE)" ) --llm-max-files "$(LLM_MAX_FILES)" --llm-max-chars "$(LLM_MAX_CHARS)" --llm-max-tree "$(LLM_MAX_TREE)" --$$( [ "$(LLM_USE_TOOLS)" = "1" ] && echo llm-use-tools || echo no-llm-use-tools ) --$$( [ "$(INCLUDE_SIGNALS)" = "1" ] && echo include-signals || echo no-include-signals ) --$$( [ "$(SKIP_LLM)" = "1" ] && echo skip-llm || echo no-skip-llm ) --prioritize-top "$(PRIORITIZE_TOP)" --$$( [ "$(SKIP_PRIORITIZE)" = "1" ] && echo skip-prioritize || echo no-skip-prioritize )

fanin:
	@if [ -z "$(PROJECT_PATH)" ]; then \
		echo "Usage: make fanin PROJECT_PATH=/absolute/path/to/project [ENTRY_PREFIX=server/api] [TOP=25] [FANIN_ENGINE=codeql|heuristic]"; \
		exit 1; \
	fi
	python3 fanin_rank.py "$(PROJECT_PATH)" --engine "$(FANIN_ENGINE)" --entry-prefix "$(ENTRY_PREFIX)" --top "$(TOP)" $$( [ -n "$(CODEQL_DB_DIR)" ] && echo "--codeql-db-dir $(CODEQL_DB_DIR)" )

git-history:
	@if [ -z "$(PROJECT_PATH)" ]; then \
		echo "Usage: make git-history PROJECT_PATH=/absolute/path/to/project [TOP=25]"; \
		exit 1; \
	fi
	python3 git_history_rank.py "$(PROJECT_PATH)" --top "$(TOP)"

vuln:
	@if [ -z "$(PROJECT_PATH)" ]; then \
		echo "Usage: make vuln PROJECT_PATH=/absolute/path/to/project [VULN_TOP=25] [VULN_MAX_FINDINGS=300]"; \
		exit 1; \
	fi
	python3 vulnerability_scan.py "$(PROJECT_PATH)" --top "$(VULN_TOP)" --max-findings "$(VULN_MAX_FINDINGS)"

llm:
	@if [ -z "$(PROJECT_PATH)" ]; then \
		 echo "Usage: make llm PROJECT_PATH=/absolute/path/to/project [LLM_PROVIDER=openai-compatible] [LLM_MODEL=gpt-5.3-codex] [LLM_AUTH_PROFILE=name]"; \
		exit 1; \
	fi
	python3 llm_reachability_scan.py "$(PROJECT_PATH)" --provider "$(LLM_PROVIDER)" --model "$(LLM_MODEL)" $$( [ -n "$(LLM_AUTH_FILE)" ] && echo "--auth-file $(LLM_AUTH_FILE)" ) $$( [ -n "$(LLM_AUTH_PROFILE)" ] && echo "--auth-profile $(LLM_AUTH_PROFILE)" ) --max-files "$(LLM_MAX_FILES)" --max-chars "$(LLM_MAX_CHARS)" --max-tree "$(LLM_MAX_TREE)" --$$( [ "$(LLM_USE_TOOLS)" = "1" ] && echo use-tools || echo no-use-tools ) --$$( [ "$(INCLUDE_SIGNALS)" = "1" ] && echo include-signals || echo no-include-signals )

connect:
	python3 connect_provider.py login $$( [ -n "$(LLM_AUTH_FILE)" ] && echo "--auth-file $(LLM_AUTH_FILE)" ) $$( [ -n "$(LLM_AUTH_PROFILE)" ] && echo "--profile $(LLM_AUTH_PROFILE)" )
