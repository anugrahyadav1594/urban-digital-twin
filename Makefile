# Developer entry points. Run from the repo root.
.PHONY: help preflight db-up db-down db-reset db-logs doctor check seed test verify

# Read POSTGIS_PORT from .env if present, else default to 5432.
PORT := $(shell [ -f .env ] && grep -E '^POSTGIS_PORT=' .env | tail -1 | cut -d= -f2 || true)
PORT := $(if $(PORT),$(PORT),5432)

help:
	@echo "  make verify    db-up -> check -> seed -> test  (start here)"
	@echo "  make db-up     start PostGIS in Docker on port $(PORT)"
	@echo "  make db-down   stop it (data survives)"
	@echo "  make db-reset  DESTROY the database and recreate it"
	@echo "  make db-logs   tail the database log"
	@echo "  make preflight check the port is free before starting"
	@echo "  make doctor    diagnose connection problems"
	@echo "  make check     connectivity + schema report"
	@echo "  make seed      load pilot-sector demo data"
	@echo "  make test      run the integration suite"

# Fail with a useful message BEFORE docker emits a raw daemon error.
preflight:
	@if [ -d db/schema.sql ]; then \
		echo ""; \
		echo "  db/schema.sql is a DIRECTORY, not a file."; \
		echo "  Docker created it because the file was missing when you first"; \
		echo "  ran 'docker compose up'. The database was never initialised."; \
		echo ""; \
		echo "  Fix:"; \
		echo "    docker compose down -v"; \
		echo "    rmdir db/schema.sql"; \
		echo "    # restore db/schema.sql, then re-run"; \
		echo ""; \
		exit 1; \
	fi
	@if [ ! -f db/schema.sql ]; then \
		echo ""; \
		echo "  db/schema.sql is MISSING."; \
		echo "  Docker would create a directory in its place. Restore it first."; \
		echo ""; \
		exit 1; \
	fi
	@if [ -n "$$(docker ps -aq -f name=^nagarx-db$$ 2>/dev/null)" ] && \
	    [ -z "$$(docker ps -q -f name=^nagarx-db$$ 2>/dev/null)" ]; then \
		echo "removing a stopped/partial nagarx-db container..."; \
		docker rm -f nagarx-db >/dev/null 2>&1 || true; \
	fi
	@if docker ps -q -f name=^nagarx-db$$ 2>/dev/null | grep -q .; then \
		echo "nagarx-db is already running - reusing it"; \
	elif python3 -c "import socket,sys; s=socket.socket(); s.settimeout(2); sys.exit(0 if s.connect_ex(('127.0.0.1',$(PORT)))==0 else 1)" 2>/dev/null; then \
		echo ""; \
		echo "  PORT $(PORT) IS ALREADY IN USE - not starting Docker."; \
		echo ""; \
		bash scripts/port_owner.sh $(PORT); \
		exit 1; \
	fi

db-up: preflight
	docker compose up -d db
	@echo "waiting for PostGIS to accept queries..."
	@n=0; until [ "$$(docker inspect -f '{{.State.Health.Status}}' nagarx-db 2>/dev/null)" = "healthy" ]; do \
		n=$$((n+1)); \
		if [ $$n -gt 90 ]; then \
			echo ""; echo "  database did not become healthy in 90s. Recent log:"; \
			docker compose logs --tail=30 db; exit 1; \
		fi; \
		printf '.'; sleep 1; \
	done; echo " ready on port $(PORT)"

db-down:
	docker compose down

db-reset:
	docker compose down -v
	$(MAKE) db-up

db-logs:
	docker compose logs -f db

doctor:
	cd backend && python -m app.storage.doctor

check:
	cd backend && python -m app.storage.bootstrap check

seed:
	python db/seed_demo.py
	cd backend && python -m app.storage.bootstrap counts

test:
	cd backend && python -m pytest tests/ -v

verify: db-up check seed test
	@echo ""
	@echo "  Backend and database verified end to end."
