# embodi. — Backend

![banner](docs/banner.svg)

The API for the BIM Sustainability Analyzer: parses uploaded IFC models with **IfcOpenShell**, computes embodied carbon per element, runs operational-energy simulations, and powers a data-grounded streaming AI assistant. Paired with the [frontend](../frontend/README.md).

![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-D71F00?logo=sqlalchemy&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-database-4169E1?logo=postgresql&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-async%20jobs-37814A?logo=celery&logoColor=white)
![Cloudinary](https://img.shields.io/badge/Cloudinary-file%20storage-3448C5?logo=cloudinary&logoColor=white)
![IfcOpenShell](https://img.shields.io/badge/IfcOpenShell-BIM%20parsing-orange)

## Contents
- [Architecture](#architecture)
- [Features](#features)
- [IFC ingestion pipeline](#ifc-ingestion-pipeline)
- [Getting started](#getting-started)
- [Environment variables](#environment-variables)
- [API reference](#api-reference)
- [Project structure](#project-structure)
- [Running the Celery worker](#running-the-celery-worker)

## Architecture

![architecture](docs/architecture.svg)

- **FastAPI** serves the REST + Server-Sent-Events API consumed by the Next.js frontend.
- **PostgreSQL** stores users, projects, extracted IFC elements, and energy results.
- **Cloudinary** is the only persistent home for uploaded `.ifc` files — nothing is written to app-managed disk storage (see [IFC ingestion pipeline](#ifc-ingestion-pipeline)).
- **Redis + Celery** run IFC parsing and energy simulations in the background when `USE_CELERY=true`, so large models don't block the request.
- **DeepSeek / OpenRouter** provide the LLM completions behind the streaming chat assistant (falls back to canned hints if no key is set).

## Features

- JWT auth (register / login / `/me`)
- Project CRUD, owner-scoped on every route
- IFC upload → Cloudinary storage → IfcOpenShell parsing → per-element embodied carbon
- 3D-viewer-ready geometry: bounding boxes and materials extracted per element
- Operational energy simulation (EnergyPlus if available, ISO 13790-style fallback otherwise)
- Rule-based + ML carbon prediction (`/api/ifc/predict-carbon`, retrainable against real parsed projects)
- Quantified carbon-reduction recommendations per project
- Streaming chat assistant grounded in the requesting project's own data

## IFC ingestion pipeline

![ifc pipeline](docs/ifc-pipeline.svg)

`POST /api/projects/{id}/upload-ifc` reads the upload straight into memory and sends it to **Cloudinary** (`app/services/cloud_storage.py`) — the raw bytes are never written to a permanent, app-managed directory. IfcOpenShell's parser only accepts a filesystem path, so a short-lived temp file is created purely as its working copy:

- **Inline mode** (`USE_CELERY=false`): the bytes already in memory are written to a temp file, parsed, and the temp file is deleted immediately after.
- **Celery mode** (`USE_CELERY=true`): the task is handed the Cloudinary URL (not a local path, since the worker may run in a different process/container) and downloads its own temp copy, which it deletes once parsing finishes.

Either way, Cloudinary is the single source of truth for the stored file; the project's `ifc_url` column points at it.

## Getting started

### Prerequisites
- Python 3.11+
- PostgreSQL
- Redis (only if running with `USE_CELERY=true`)
- A [Cloudinary](https://cloudinary.com) account (cloud name, API key, API secret)
- `ifcopenshell` installed in your environment (see note below)

### Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn sqlalchemy psycopg2-binary pydantic-settings \
            bcrypt pyjwt python-multipart cloudinary \
            celery redis openai ifcopenshell xgboost numpy
```

> **Note:** `ifcopenshell` has platform-specific wheels. If `pip install ifcopenshell` fails on your machine, run the backend inside a container with it preinstalled — without it, `/upload-ifc` returns a clear error rather than crashing.

### Configure

Copy the variables below into a `.env` file in the project root, then:

```bash
uvicorn app.main:app --reload --port 8000
```

The API is now at `http://localhost:8000`, with interactive docs at `http://localhost:8000/docs`.

### Seed sample data (optional)

```bash
python -m app.seed
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string, e.g. `postgresql://user:pass@localhost/embodi` |
| `SECRET_KEY` | Yes | JWT signing secret |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Default `10080` (7 days) |
| `CLOUDINARY_CLOUD_NAME` | Yes* | Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | Yes* | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Yes* | Cloudinary API secret |
| `CLOUDINARY_URL` | Yes* | Alternative to the three values above, in `cloudinary://key:secret@cloud_name` form |
| `USE_CELERY` | No | `true` to parse IFC files / run simulations asynchronously via Celery |
| `CELERY_BROKER_URL` | If `USE_CELERY=true` | Default `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | If `USE_CELERY=true` | Default `redis://localhost:6379/1` |
| `EPW_FILE` | No | Path to an `.epw` weather file for EnergyPlus; falls back to the ISO 13790 model if unset |
| `CORS_ORIGINS` | No | Comma-separated allowed origins, default `*` |
| `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL` | No | Enables DeepSeek-backed chat completions |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` | No | Enables OpenRouter-backed chat completions |

*Either the three discrete `CLOUDINARY_*` values or a single `CLOUDINARY_URL` is required — the discrete values take priority if both are set.

## API reference

All routes are prefixed as shown; owner-scoped routes require `Authorization: Bearer <token>`.

### `/api/auth`
| Method | Path | Description |
|---|---|---|
| POST | `/register` | Create an account, returns a JWT |
| POST | `/login` | Email + password login, returns a JWT |
| POST | `/token` | OAuth2 password-flow login (for Swagger's "Authorize" button) |
| GET | `/me` | Current user |

### `/api/projects`
| Method | Path | Description |
|---|---|---|
| GET | `/` | List the current user's projects |
| POST | `/` | Create a project |
| GET | `/{pid}` | Project detail, including elements |
| DELETE | `/{pid}` | Delete a project |
| POST | `/{pid}/upload-ifc` | Upload an `.ifc` file → Cloudinary → parse pipeline |
| GET | `/{pid}/status` | Parse status: `idle · queued · running · done · failed` |

### `/api/energy`
| Method | Path | Description |
|---|---|---|
| GET | `/{pid}` | Latest energy simulation result |
| POST | `/{pid}/simulate` | Run a new simulation |
| GET | `/engine/info` | Whether EnergyPlus is available, and the fallback engine name |

### `/api/materials`
| Method | Path | Description |
|---|---|---|
| GET | `/` | List materials with embodied-carbon coefficients |
| POST | `/` | Add a material |

### `/api/recommendations`
| Method | Path | Description |
|---|---|---|
| POST | `/` | Get quantified carbon-reduction recommendations for a project |

### `/api/chat`
| Method | Path | Description |
|---|---|---|
| POST | `/` | Non-streaming chat completion |
| POST | `/stream` | Server-Sent-Events streaming chat, grounded in project context |

### `/api/ifc`
| Method | Path | Description |
|---|---|---|
| POST | `/predict-carbon` | Estimate embodied carbon from area/floors/material ratios (ML model) |
| POST | `/predict-carbon/retrain` | Retrain the estimator against real parsed projects |

## Project structure

```
app/
├── main.py                    # FastAPI app, router registration, CORS
├── api/
│   ├── auth.py                # register / login / me
│   ├── projects.py            # project CRUD + IFC upload (Cloudinary)
│   ├── energy.py               # simulation endpoints
│   ├── materials.py            # materials database
│   ├── recommendations.py      # AI recommendation endpoint
│   ├── chat.py                  # streaming + non-streaming chat
│   └── ifc.py                   # ML carbon prediction
├── core/
│   ├── config.py                # Settings (env vars)
│   ├── database.py              # SQLAlchemy engine/session
│   ├── deps.py                  # auth + owned-project dependencies
│   └── security.py              # password hashing (bcrypt), JWT (pyjwt)
├── models/                      # SQLAlchemy models (User, Project, Element, EnergyResult, Material)
├── schemas/                     # Pydantic request/response schemas
├── services/
│   ├── cloud_storage.py         # Cloudinary upload/download
│   ├── ifc_parser.py            # IfcOpenShell extraction
│   ├── pipeline.py              # IFC → DB ingestion, shared by API + Celery
│   ├── carbon.py                 # embodied-carbon calculation
│   ├── energy.py                  # EnergyPlus / ISO 13790 simulation
│   └── recommender.py             # recommendation generation
├── ml/predictor.py              # XGBoost carbon estimator
├── worker/
│   ├── celery_app.py
│   └── tasks.py                  # ifc.parse, energy.simulate
└── seed.py                        # sample data loader
```

## Running the Celery worker

Only needed when `USE_CELERY=true`:

```bash
celery -A app.worker.celery_app worker --loglevel=info
```

The worker downloads its own temp copy of the IFC file from Cloudinary per job (see [IFC ingestion pipeline](#ifc-ingestion-pipeline)) — it does not need to share a filesystem with the API process.
