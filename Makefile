# KOPS local stack with Docker (D-07). Needs Docker (Desktop) and raw-docs/ next to this file.
#   make up        build the image, build the DW + checks + dashboards, serve http://127.0.0.1:8765 (demo data on)
#   make up-real   same without synthetic demo data (KOPS_SIM=0)
#   make check     run every check inside the container
#   make logs      follow the logs
#   make down      stop (the build volume is kept)
#   make rebuild   rebuild the image without cache and start again
#   make clean     stop and delete the build volume (next `make up` parses everything again)
COMPOSE = docker compose

.PHONY: up up-real down rebuild check logs clean

up:
	KOPS_SIM=1 $(COMPOSE) up -d --build
	@echo "Dashboard: http://127.0.0.1:8765/  (logs: make logs)"

up-real:
	KOPS_SIM=0 $(COMPOSE) up -d --build --force-recreate
	@echo "Dashboard (real data only): http://127.0.0.1:8765/"

down:
	$(COMPOSE) down

rebuild:
	$(COMPOSE) build --no-cache
	$(COMPOSE) up -d --force-recreate

check:
	$(COMPOSE) run --rm --no-deps kops-build python -m kops_dw test

logs:
	$(COMPOSE) logs -f --tail=100

clean:
	$(COMPOSE) down -v
