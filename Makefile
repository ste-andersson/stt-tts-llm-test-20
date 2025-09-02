.PHONY: install run dev clean lint format test test-unit test-api-mock test-full-mock test-elevenlabs test-pipeline clear-output clean-zone-identifiers

# Variabler
TEXT?="Detta är ett test av TTS-systemet med standardtext"

install:
	uv pip install --upgrade pip
	uv pip install -r requirements.txt

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache .venv build dist *.egg-info

# --- TTS-specifika kommandon ---

lint:
	ruff check .

format:
	ruff format .

test:
	python -m pytest tests/ -v

test-unit:
	TEXT="$(TEXT)" python -m pytest tests/test_receive_text.py -v

test-api-mock:
	TEXT="$(TEXT)" python -m pytest tests/test_text_to_audio.py tests/test_send_audio.py -v

test-full-mock:
	TEXT="$(TEXT)" python -m pytest tests/test_full_tts_pipeline.py -v

test-elevenlabs:
	TEXT="$(TEXT)" python -m pytest tests/test_real_elevenlabs.py -v -s

test-pipeline:
	TEXT="$(TEXT)" python -m pytest tests/test_full_chain.py -v -s

clear-output:
	@echo "🧹 Rensar test_output-mappen..."
	@rm -rf test_output
	@echo "✅ test_output rensad!"

clean-zone-identifiers:
	@echo "🧹 Tar bort alla Zone Identifier-filer..."
	@find . -name "*Zone.Identifier" -type f -delete
	@echo "✅ Alla Zone Identifier-filer borttagna!"
