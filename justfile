# Tareas comunes (usa `just` y `uv`)
default:
    @just --list

# Levanta la app en http://localhost:8000
app:
    uv run shiny run app.py --reload

# Tests unitarios (no necesitan API key)
test:
    uv run pytest -q

# Evaluación con juez LLM (necesita GEMINI_API_KEY, consume tokens)
eval:
    uv run python -m evals.run_eval
