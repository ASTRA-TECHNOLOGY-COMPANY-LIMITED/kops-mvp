# KOPS local stack with Docker (D-07). Needs Docker (Desktop) and raw-docs/ next to this file.
#   make up        build the image, build the DW + checks + dashboards, serve http://127.0.0.1:8765 (demo data on)
#   make up-real   same without synthetic demo data (KOPS_SIM=0)
#   make check     run every check inside the container
#   make logs      follow the logs
#   make down      stop (the build volume is kept)
#   make rebuild   rebuild the image without cache and start again
#   make clean     stop and delete the build volume (next `make up` parses everything again)
#   make report SEASON=27SS REPORT_LANG=ko   PDF of the action list + overview into ./reports (git-ignored, KLMAS data)
#   make refresh   add new KLMAS files: incremental build + checks + dashboards, the open page picks it up (no restart)
#   make check-ui  UI test (Playwright + Chromium): every page x theme x desktop/mobile x VI/KO x synthetic off/on;
#                  screenshots into UI_OUT (default /tmp/kops-ui, outside the repo)
COMPOSE = docker compose

SEASON ?=
REPORT_LANG ?= vi
UI_OUT ?= /tmp/kops-ui

.PHONY: env-admin up up-real down rebuild refresh check check-ui logs clean report

# first admin of the web app: when .env has no KOPS_ADMIN_PASSWORD, append a random one (never printed; read it in .env)
env-admin:
	@test -f .env || (touch .env && chmod 600 .env)
	@grep -q '^KOPS_ADMIN_USER=' .env || echo 'KOPS_ADMIN_USER=admin' >> .env
	@grep -q '^KOPS_ADMIN_PASSWORD=' .env || (echo '# first admin password (generated; change it at first login)' >> .env && \
	  echo "KOPS_ADMIN_PASSWORD=$$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 24)" >> .env && \
	  echo 'Admin password generated: see KOPS_ADMIN_PASSWORD in .env')

up: env-admin
	KOPS_SIM=1 $(COMPOSE) up -d --build
	@echo "Dashboard: http://127.0.0.1:8765/  (logs: make logs)"

up-real: env-admin
	KOPS_SIM=0 $(COMPOSE) up -d --build --force-recreate
	@echo "Dashboard (real data only): http://127.0.0.1:8765/"

down:
	$(COMPOSE) down

rebuild:
	$(COMPOSE) build --no-cache
	$(COMPOSE) up -d --force-recreate

refresh:
	$(COMPOSE) run --rm --no-deps kops-build
	@echo "Dashboard updated: http://127.0.0.1:8765/ (the open page reloads its data within a minute)"

check:
	$(COMPOSE) run --rm --no-deps kops-build python -m kops_dw test

check-ui:
	mkdir -p "$(UI_OUT)"
	$(COMPOSE) run --rm --no-deps -v "$(UI_OUT):/out" kops-build python -m kops_dw check-ui --out /out

report:
	mkdir -p reports
	$(COMPOSE) run --rm --no-deps -v "$(CURDIR)/reports:/out" kops-build \
	  python -m kops_dw report $(if $(SEASON),--season $(SEASON)) --lang $(REPORT_LANG) --out /out

logs:
	$(COMPOSE) logs -f --tail=100

clean:
	$(COMPOSE) down -v
