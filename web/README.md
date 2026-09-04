# kindred-path2college (web)

React + Vite + Ant Design front end for the Kindred multi-agent college guide.

## Dev

```bash
nvm use 18          # Node 18 required (Vite 5)
npm install
npm run dev         # http://localhost:5173, proxies /api -> 127.0.0.1:8000
```

The FastAPI backend (`../api_server.py`) must be running on port 8000.
`../run_site.sh` starts both.

## Structure

```
src/
  main.jsx              ConfigProvider (theme) + Router
  App.jsx               Layout: sticky header nav, routes, footer
  theme.js              Ant Design tokens — "bold & encouraging" violet/gold
  index.css             global styles, hero, chat bubbles, markdown
  lib/
    api.js              fetch wrapper for /api
    session.js          conversation id (sessionStorage: survives refresh, resets on tab close)
    format.js           pct / money / date / selectivity helpers
  components/
    Logo, PageHeader, LinkGrid, AgentCard, Markdown, SessionSidebar
  pages/
    Home.jsx            hero + 4 pathway cards + advisor intro
    CollegePrep.jsx     timeline + tool links        (GET /api/resources)
    FinancialAid.jsx    steps + aid glossary + links (GET /api/resources)
    Scholarships.jsx    national programs + search tools
    CollegeExplorer.jsx searchable college grid + detail drawer (GET /api/colleges)
    Advisor.jsx         chat UI + live SessionSidebar (POST /api/chat)
```

## How the chat works

`Advisor.jsx` holds a `session_id` (sessionStorage — a refresh keeps the
conversation, closing the tab starts fresh). Every message goes to
`POST /api/chat`; the response carries the reply, which agent answered
(`discovery` / `essay` / `planning`), the classified `intent`, and a trimmed
snapshot of shared state (profile, colleges, essays, timeline) that renders in
the right-hand `SessionSidebar`. "New conversation" rotates the session id.

Agent cards on the home page and "Ask the advisor" buttons in the College
Explorer navigate to `/advisor` with a prefilled prompt via router state.
