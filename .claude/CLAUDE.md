# Airport Ops MCP — Project Guidelines

## Project overview

An MCP (Model Context Protocol) server exposing live aviation data from the OpenSky Network API to Claude. The server is operations-facing — departure briefings, congestion analysis, disruption scoping — not a consumer flight-search wrapper.

**Stack:** Python 3.11+, FastMCP (`mcp[cli]`), httpx, pydantic, uv

**Run:** `uv run python main.py` (stdio transport for Claude Desktop)  
**Dev:** `uv run mcp dev main.py` (opens MCP Inspector at localhost:5173)  
**Tests:** `uv run pytest`

---

## Architecture

Three MCP primitives are exposed. Every new feature must be assigned to exactly one:

| Primitive | Decorator | When to use |
|-----------|-----------|-------------|
| Resource | `@mcp.resource("scheme://path/{param}")` | Read-only, URI-addressable, no side effects. Claude reads passively before reasoning. |
| Tool | `@mcp.tool()` | Callable with user-provided input at invocation time. No state mutation in this project — all tools are read-only. |
| Prompt | `@mcp.prompt()` | Slash commands that inject live data into a structured template. These encode ops domain intelligence, not just raw data. |

Registration pattern — each module exposes a `register_*(mcp)` function called from `main.py`:

```python
# main.py
from resources.airport_flights import register_resources
from tools.track_aircraft     import register_tools
from prompts.departure_brief  import register_prompts

mcp = FastMCP("Airport Operations Intelligence")
register_resources(mcp)
register_tools(mcp)
register_prompts(mcp)
```

---

## File structure

```
airport-ops-mcp/
├── main.py                  # Server entry — only wires primitives, no logic here
├── opensky/
│   ├── client.py            # OpenSkyClient + TokenManager (write first, everything depends on this)
│   ├── types.py             # StateVector, Flight dataclasses
│   └── airports.py          # ICAO → bbox dict + congestion thresholds
├── resources/               # @mcp.resource() handlers
├── tools/                   # @mcp.tool() handlers
├── prompts/                 # @mcp.prompt() handlers
└── utils/
    ├── cache.py             # TTLCache (async-safe, in-memory)
    └── units.py             # Unit converters
```

`main.py` must stay thin — no business logic. All logic lives in the module that owns it.

---

## OpenSky API — critical rules

### Authentication — OAuth2 only

Basic auth (username/password) was deprecated on **18 March 2026** and returns 401. Every request must use a Bearer token obtained via the client credentials flow.

The `TokenManager` in `opensky/client.py` handles this automatically. Never bypass it. Never hardcode tokens. Never use `requests` — use `httpx.AsyncClient` for all API calls.

```python
# Always use the shared OpenSkyClient instance — never instantiate per-call
client = OpenSkyClient(
    client_id=os.environ["OPENSKY_CLIENT_ID"],
    client_secret=os.environ["OPENSKY_CLIENT_SECRET"],
)
```

Token endpoint:
```
POST https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token
```

### Base URL

```
https://opensky-network.org/api
```

### Endpoints in use

| Endpoint | Purpose | Credits |
|----------|---------|---------|
| `GET /states/all?icao24={hex}` | Single aircraft state | 1 |
| `GET /states/all?lamin=&lomin=&lamax=&lomax=` | All aircraft in bbox | 1 (if bbox < 25 sq deg) |
| `GET /flights/departure?airport={ICAO}&begin={unix}&end={unix}` | Departures in window | 2–4 |
| `GET /flights/arrival?airport={ICAO}&begin={unix}&end={unix}` | Arrivals in window | 2–4 |
| `GET /flights/aircraft?icao24={hex}&begin={unix}&end={unix}` | Aircraft history | 2 |

### Time constraints

- `/flights/departure` and `/flights/arrival`: window must be **≤ 2 days**
- `/flights/aircraft`: window must be **≤ 2 days**
- `/flights/departure` and `/flights/arrival` are **batch-updated nightly** — today's data is incomplete. Always note this in tool docstrings and prompt templates.

### Rate limit handling

Always handle these HTTP status codes in `_get()`:

```python
if r.status_code == 404:
    return []   # No data for this window — not an error
if r.status_code == 429:
    wait = r.headers.get("X-Rate-Limit-Retry-After-Seconds", "60")
    raise RuntimeError(f"OpenSky rate limited — retry in {wait}s")
```

Never propagate raw httpx exceptions to the MCP layer — wrap and re-raise with a human-readable message.

### StateVector field index map

The `/states/all` endpoint returns states as raw arrays. Always use `_parse_state(row)` from `opensky/client.py` — never index the raw array directly in business logic:

```python
# index → field
0  icao24        # hex string
1  callsign      # 8 chars, strip whitespace
2  origin_country
5  longitude     # float, can be None
6  latitude      # float, can be None
7  baro_altitude # metres, can be None
8  on_ground     # bool
9  velocity      # m/s, can be None
10 true_track    # degrees from north, can be None
11 vertical_rate # m/s, negative = descending, can be None
14 squawk        # string, can be None
```

**Null handling is mandatory.** Indices 5, 6, 7, 9, 10, 11, 14 can all be `None`. Every accessor must guard:

```python
"altitude_ft": round(row[7] * 3.28084) if row[7] is not None else None,
```

---

## Caching rules

All OpenSky calls must go through `TTLCache` in `utils/cache.py`. Never hit the API twice for the same data within the TTL window.

| Call type | TTL |
|-----------|-----|
| `/states/all` single aircraft | 10s |
| `/states/all` bbox (congestion / traffic) | 30s |
| `/flights/departure` or `/arrival` | 300s (5 min) |
| `/flights/aircraft` history | 120s |

The cache is in-memory and resets on server restart — this is intentional. Do not add persistence.

Cache key convention: `"{endpoint}:{sorted_params_json}"` — see `OpenSkyClient._get()` for the canonical implementation.

---

## Unit conventions

All units exposed to Claude must be human-readable aviation units. Raw SI values from OpenSky are for internal use only.

| Conversion | Function |
|------------|----------|
| m/s → knots | `ms_to_knots(v)` in `utils/units.py` |
| metres → feet | `m_to_feet(v)` in `utils/units.py` |
| Unix timestamp → UTC string | `unix_to_utc(ts)` in `utils/units.py` |

All converters accept `None` and return `None` — no need for guards at the call site.

---

## Tool return types — always use Pydantic

All tools must return a Pydantic `BaseModel` subclass. FastMCP generates the JSON schema and structured output automatically. Never return raw dicts from tools.

```python
from pydantic import BaseModel

class CongestionResult(BaseModel):
    icao: str
    level: str          # "LOW" | "MODERATE" | "HIGH"
    aircraft_on_ground: int
    aircraft_airborne: int
    summary: str

@mcp.tool()
async def check_congestion(icao: str) -> CongestionResult:
    ...
```

---

## Airport bounding boxes and congestion thresholds

All airports are registered in `opensky/airports.py`. Two things live there:

**1. Bounding boxes** used for `/states/all` bbox queries. Keep boxes tight — under 25 square degrees to stay at 1 credit per call. Airport-only boxes are always well under this.

**2. Congestion thresholds** — on-ground aircraft counts that define LOW / MODERATE / HIGH. These are calibrated per airport type and must not be changed without ops domain justification:

```python
THRESHOLDS = {
    "VGHS": {"moderate": 8,  "high": 15},  # regional hub
    "EGLL": {"moderate": 30, "high": 55},  # mega hub
    ...
    "default": {"moderate": 15, "high": 30},
}
```

The function `classify_congestion(icao, count)` in `airports.py` is the single source of truth for level classification. Do not replicate this logic elsewhere.

To add an airport: add a bbox entry and a threshold entry. Never add one without the other.

---

## Prompt design rules

Prompts must follow this pattern:

1. Fetch live data by calling tools/resources internally (not via MCP — direct function calls)
2. Format data into a concise summary string
3. Return a structured natural-language template that tells Claude what to reason about and how to frame the output

The framing is the moat. A prompt that dumps raw JSON at Claude is not better than calling the tool directly. Every prompt must specify the output structure expected — sections, priorities, tone (ops-context, not consumer).

Example structure:
```python
@mcp.prompt()
async def departure_brief(icao: str, date: str = "") -> str:
    """Generate an operational departure briefing for an airport."""
    # 1. fetch
    traffic = await check_congestion(icao)
    departures = await opensky.get_departures(...)
    # 2. format
    dep_summary = format_departures(departures)
    # 3. template — ops framing
    return f"""
You are an airport operations intelligence assistant.
Analyse the following live data for {icao} on {target_date}: ...
Provide a structured ops briefing covering:
1. Traffic density assessment and implications
2. Departure schedule health ...
"""
```

---

## ICAO code conventions

- Airport codes: always uppercase (`EGLL`, `VGHS`) — normalise with `.upper()` before any API call
- ICAO24 transponder addresses: always lowercase hex (`3c6444`) — normalise with `.lower()` before any API call
- Callsigns: strip whitespace — OpenSky pads to 8 characters with trailing spaces

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENSKY_CLIENT_ID` | Yes | OAuth2 client ID from OpenSky account page |
| `OPENSKY_CLIENT_SECRET` | Yes | OAuth2 client secret |

Always load via `python-dotenv` in development. In production (Claude Desktop), passed via `env` in `claude_desktop_config.json`. Never hardcode or commit credentials.

---

## What not to build

- No write operations to OpenSky (the API is read-only anyway)
- No Sampling primitive — the server does not need to call Claude autonomously
- No Elicitation — all inputs are provided upfront via tool arguments or prompt args
- No Roots — no filesystem access needed
- No persistent storage — cache is in-memory only
- No web framework (Flask, FastAPI) — this is a stdio MCP server, not an HTTP service