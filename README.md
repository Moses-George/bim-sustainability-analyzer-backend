# BIM Sustainability Analyzer — Backend (FastAPI)

## Run
```
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```
Docs: http://localhost:8000/docs
