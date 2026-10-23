# KOPS local stack with Docker (D-07, F-06). Needs Docker (Desktop) and raw-docs/ next to this file.
#   make up        build image kops-app, build the DW + checks + dashboards, start the app on http://127.0.0.1:8765 (demo data on)
#   make up-real   same without synthetic demo data (KOPS_SIM=0)
#   make refresh   add new KLMAS files: incremental build + checks + dashboards, the open page picks it up (no restart)
#   make check     run every check inside the container
#   make check-ui  UI test in image kops-tools (Playwright + Chromium): login, every page x theme x desktop/mobile x VI/KO
#                  x synthetic off/on, bell, chatbot; screenshots into UI_OUT (default /tmp/kops-ui, outside the repo)
#   make report SEASON=27SS REPORT_LANG=ko   PDF of the action list + overview into ./reports (git-ignored, KLMAS data)
#   make logs      follow the logs
#   make down      stop (volumes are kept)
#   make rebuild   rebuild the images without cache and start again (the DW and the app state are kept)
#   make clean     stop and delete the DW build volume (next `make up` parses everything again); app state is kept
#   make admin-reset   admin password back to KOPS_ADMIN_PASSWORD in .env (must be changed at next login)
#   make backup-state  copy the app state (users, notifications, chat, settings) to ./backups/ (git-ignored)
#   make reset-state   delete the app state volume (asks for confirmation; users and notification history are lost)
COMPOSE = docker compose
# app version shown in the footer: short git hash of this checkout
export KOPS_VERSION := $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)

SEASON ?=
REPORT_LANG ?= vi
UI_OUT ?= /tmp/kops-ui

.PHONY: env-admin up up-real down rebuild refresh check tools-image check-ui report logs clean admin-reset backup-state reset-state

# first admin of the web app: when .env has no KOPS_ADMIN_PASSWORD, append a random one (never printed; read it in .env)
env-admin:
	@test -f .env || (touch .env && chmod 600 .env)
	@grep -q '^KOPS_ADMIN_USER=' .env || echo 'KOPS_ADMIN_USER=admin' >> .env
	@grep -q '^KOPS_ADMIN_PASSWORD=.' .env || (sed -i.bak '/^KOPS_ADMIN_PASSWORD=$$/d' .env && rm -f .env.bak && \
	  echo '# first admin password (generated; change it at first login)' >> .env && \
	  echo "KOPS_ADMIN_PASSWORD=$$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 24)" >> .env && \
	  echo 'Admin password generated: see KOPS_ADMIN_PASSWORD in .env')

up: env-admin
	KOPS_SIM=1 $(COMPOSE) up -d --build
	@echo "KOPS: http://127.0.0.1:8765/  (first login: user KOPS_ADMIN_USER, password KOPS_ADMIN_PASSWORD in .env; logs: make logs)"

up-real: env-admin
	KOPS_SIM=0 $(COMPOSE) up -d --build --force-recreate
	@echo "KOPS (real data only): http://127.0.0.1:8765/"

down:
	$(COMPOSE) down

rebuild:
	$(COMPOSE) build --no-cache
	$(COMPOSE) up -d --force-recreate

refresh:
	$(COMPOSE) run --rm --no-deps kops-build
	@echo "Data updated: http://127.0.0.1:8765/ (the open page reloads its data within a minute)"

check:
	$(COMPOSE) run --rm --no-deps kops-build python -m kops_dw test

tools-image:
	$(COMPOSE) --profile tools build kops-tools

check-ui: tools-image
	mkdir -p "$(UI_OUT)"
	$(COMPOSE) --profile tools run --rm --no-deps -v "$(UI_OUT):/out" kops-tools python -m kops_dw check-ui --out /out

report: tools-image
	mkdir -p reports
	$(COMPOSE) --profile tools run --rm --no-deps -v "$(CURDIR)/reports:/out" kops-tools \
	  python -m kops_dw report $(if $(SEASON),--season $(SEASON)) --lang $(REPORT_LANG) --out /out

admin-reset: env-admin
	$(COMPOSE) run --rm --no-deps kops-build python -m kops_dw admin-reset

backup-state:
	mkdir -p backups
	$(COMPOSE) run --rm --no-deps -v "$(CURDIR)/backups:/backups" kops-build python -m kops_dw backup-state /backups

reset-state:
	@printf 'Delete ALL app state (users, sessions, notification status, chat history, settings)? Type YES: '; \
	  read a; [ "$$a" = YES ] || (echo cancelled; exit 1)
	$(COMPOSE) down
	docker volume rm kops_kops_state
	@echo "App state deleted; make up creates the admin from .env again"

logs:
	$(COMPOSE) logs -f --tail=100

clean:
	$(COMPOSE) down
	-docker volume rm kops_kops_build
