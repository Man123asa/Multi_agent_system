# Hold'em Royale - casino-style poker table

Run locally (no Docker):
    pip install -r requirements.txt
    uvicorn app.main:app --reload        # http://localhost:8000

Docker:
    docker build -t holdem .
    docker run --rm -p 8000:8000 holdem   # http://localhost:8000

Docker Compose:
    docker compose up --build -d
    docker compose logs -f
    docker compose down

LLM agents (optional):
    docker build --build-arg INSTALL_LLM=1 -t holdem .
    docker run --rm -p 8000:8000 -e OPENAI_API_KEY=sk-... holdem

Cloud (Render / Railway / Fly.io): point the service at this repo's Dockerfile.
The container reads the PORT env var; health check path is /health.
Never commit API keys; set them as platform secrets.
