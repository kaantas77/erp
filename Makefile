.PHONY: help install test lint format check migrate run superuser clean

PY := .venv/bin/python
PIP := .venv/bin/pip
RUFF := .venv/bin/ruff

help:
	@echo "Kullanim:"
	@echo "  make install   Bagimliliklari kurar"
	@echo "  make test      Testleri calistirir"
	@echo "  make lint      Lint + format kontrolu"
	@echo "  make format    Kodu bicimlendirir"
	@echo "  make check     PR oncesi tam kontrol (CI'in yerli karsiligi)"
	@echo "  make migrate   Veritabani migration'larini uygular"
	@echo "  make run       Gelistirme sunucusunu baslatir"
	@echo "  make superuser Yonetici kullanicisi olusturur"

install:
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

test:
	$(PY) -m pytest -q

lint:
	$(RUFF) check .
	$(RUFF) format --check .

format:
	$(RUFF) format .
	$(RUFF) check --fix .

check:
	@echo "== Lint =="
	$(RUFF) check .
	@echo "== Format =="
	$(RUFF) format --check .
	@echo "== Migration tutarliligi =="
	$(PY) manage.py makemigrations --check --dry-run
	@echo "== Django kontrol =="
	$(PY) manage.py check
	@echo "== Testler =="
	$(PY) -m pytest -q
	@echo "Tum kontroller gecti."

migrate:
	$(PY) manage.py migrate

run:
	$(PY) manage.py runserver

superuser:
	$(PY) manage.py createsuperuser

clean:
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache staticfiles
