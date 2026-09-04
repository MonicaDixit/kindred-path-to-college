# Kindred

A web app that helps students with the college application process.

## Tech stack

- **Backend:** Python (FastAPI)
- **Frontend:** React (Vite)

## Requirements

- Python 3.10+
- Node.js 18+
- An OpenRouter API key ([sign up free](https://openrouter.ai/))

## Setup

1. Install backend dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment variables:

   ```bash
   cp .env.template .env
   ```

   Open `.env` and set `OPENROUTER_API_KEY` to your key. The other variables
   in `.env.template` are optional and have working defaults.

3. Install frontend dependencies:

   ```bash
   cd web
   npm install
   ```

## Running locally

From the project root, start both the backend and frontend together:

```bash
./run_site.sh
```

- API: http://localhost:8000
- Web app: http://localhost:5173

Or run each one separately:

```bash
# backend
python3 -m uvicorn api_server:app --port 8000

# frontend
cd web
npm run dev
```

Then open http://localhost:5173 in your browser.

> Note: Node 18+ is required for the frontend build tooling. If your default
> `node` is older, switch versions first (e.g. `nvm use 18`).

## License

All rights reserved.
