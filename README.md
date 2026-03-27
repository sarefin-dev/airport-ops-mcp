# Airport Operations Intelligence MCP

A Model Context Protocol server that connects Claude to live aviation data via the [OpenSky Network API](https://opensky-network.org). Built for operations-side use cases — departure briefings, congestion analysis, disruption scoping — not consumer flight search.

> **Ecosystem gap:** Every aviation MCP on Smithery is a consumer flight-search wrapper. This one is operations-facing, encoding real ops domain knowledge in its Prompts layer.

---

## What it does

| Primitive | Name | Description |
|-----------|------|-------------|
| Resource | `airport://departures/{icao}/{date}` | Historical departures from an airport on a given date |
| Resource | `airport://arrivals/{icao}/{date}` | Historical arrivals for an airport on a given date |
| Resource | `aircraft://state/{icao24}` | Live position, altitude, speed, and heading for a specific aircraft |
| Tool | `track_aircraft` | Track any aircraft by callsign or ICAO24 transponder address |
| Tool | `get_airport_traffic` | Live snapshot of aircraft on ground vs airborne within airport boundary |
| Tool | `check_congestion` | Returns LOW / MODERATE / HIGH density with counts, calibrated per airport type |
| Tool | `delay_pattern` | Analyses recent departure history to surface avg delay and per-airline breakdown |
| Prompt | `/departure-brief {ICAO}` | Structured ops briefing: traffic density, schedule health, risk flags, recommended actions |
| Prompt | `/disruption-scope {callsign}` | Live position + estimated arrival impact + downstream connection risk |
| Prompt | `/congestion-check {ICAO}` | Current density explained in ops context with recommended ground actions |

---

## Prerequisites

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/) (recommended) — or pip
- [Claude Desktop](https://claude.ai/download)
- A free [OpenSky Network](https://opensky-network.org) account

---

## OpenSky setup — OAuth2 (required)

> **Important:** OpenSky deprecated basic authentication on **18 March 2026**. This server uses the OAuth2 client credentials flow exclusively. Username/password will return 401.

1. Log in at [opensky-network.org](https://opensky-network.org) and go to **Account → API Clients**
2. Create a new client — copy the `client_id` and `client_secret`
3. Paste them into your `.env` file (see below)

Token refresh is handled automatically by the built-in `TokenManager`. Tokens expire after 30 minutes and are refreshed silently before expiry.

---

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/airport-ops-mcp.git
cd airport-ops-mcp
uv sync
```

Or with pip:

```bash
pip install -e .
```

### Environment variables

Copy the example and fill in your OpenSky credentials:

```bash
cp .env.example .env
```

`.env`:

```
OPENSKY_CLIENT_ID=your_client_id_here
OPENSKY_CLIENT_SECRET=your_client_secret_here
```

---

## Claude Desktop integration

Add the following to your Claude Desktop configuration file.

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "airport-ops": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/airport-ops-mcp",
        "python",
        "main.py"
      ],
      "env": {
        "OPENSKY_CLIENT_ID": "your_client_id_here",
        "OPENSKY_CLIENT_SECRET": "your_client_secret_here"
      }
    }
  }
}
```

Restart Claude Desktop. A plug icon will appear at the bottom-right of the input box when the server connects.

### Test the connection

Ask Claude:

```
Track aircraft with ICAO24 3c6444
```

You should receive a live position, altitude, and speed for that aircraft.

---

## Resources

Resources are read-only, URI-addressed data that Claude reads passively before answering questions. They do not require approval.

### `airport://departures/{icao}/{date}`

Returns all departures from an airport for a given date.

- `icao` — ICAO airport code (e.g. `EGLL`, `EDDF`, `VGHS`)
- `date` — date in `YYYY-MM-DD` format

> Note: OpenSky departure/arrival data is batch-updated nightly. Today's data will be incomplete. Use yesterday's date for full results.

### `airport://arrivals/{icao}/{date}`

Same as departures, but for arrivals.

### `aircraft://state/{icao24}`

Returns the current live state vector for a specific aircraft transponder.

- `icao24` — 6-character hex transponder address (e.g. `3c6444`, `47818c`)

Returns: callsign, position (lat/lon), altitude (ft), velocity (knots), heading, vertical rate, on-ground flag, squawk.

---

## Tools

Tools are callable functions. Claude invokes them on your behalf with your approval.

### `track_aircraft(callsign?, icao24?)`

Locate an aircraft by callsign (e.g. `"BG401"`) or ICAO24 transponder address. At least one must be provided.

Returns: full state vector with human-readable units.

### `get_airport_traffic(icao)`

Live snapshot of aircraft within the airport's bounding box.

Returns:
- Count of aircraft on ground (taxiing, parked, pushback)
- Count of aircraft airborne within the boundary zone
- Breakdown by airline callsign prefix (top 5)

### `check_congestion(icao)`

Assesses current traffic density at the airport using calibrated per-airport thresholds.

Returns: `level` (LOW / MODERATE / HIGH), `aircraft_on_ground`, `aircraft_airborne`, `summary` string.

> Thresholds reflect real operational norms — EGLL at 30 aircraft on ground is normal; the same count at VGHS is a critical overload situation.

### `delay_pattern(icao, hours_back=24)`

Analyses recent departure history (up to 24h back) to surface delay patterns.

Returns: average delay minutes, on-time percentage, top 3 airlines by delay, worst single flight.

> Uses the `/flights/departure` endpoint which is batch-updated nightly. Set `hours_back` to cover yesterday's full operation window for reliable results.

---

## Prompts

Prompts are pre-designed slash commands that encode operational domain knowledge. Invoke them from the prompt menu in Claude Desktop.

### `/departure-brief {ICAO} [date]`

Generates a structured operations briefing for an airport. Internally fetches live congestion and recent departure data, then asks Claude to produce:

1. Traffic density assessment and operational implications
2. Departure schedule health — delays, gaps, bunching
3. Operational risk flags requiring attention
4. Recommended actions for the ground ops team

Example:

```
/departure-brief EGLL
/departure-brief VGHS 2024-03-26
```

### `/disruption-scope {callsign}`

Provides an impact assessment for a specific flight. Fetches live position data and recent flight history, then asks Claude to assess:

- Current position and phase of flight
- Estimated arrival impact (early / on-time / delayed)
- Downstream connection risk for connecting passengers

Example:

```
/disruption-scope BG401
/disruption-scope EK007
```

### `/congestion-check {ICAO}`

Fetches current ground and airborne traffic density, then asks Claude to explain the situation in operational context and recommend appropriate ground actions (hold at gate, expedite boarding, coordinate slot management, etc).

Example:

```
/congestion-check OMDB
/congestion-check EDDF
```

---

## Supported airports

The following airports have calibrated congestion thresholds and pre-configured bounding boxes.

| ICAO | IATA | Airport | Hub type |
|------|------|---------|----------|
| VGHS | DAC  | Hazrat Shahjalal International, Dhaka | Regional hub |
| EGLL | LHR  | London Heathrow | Mega hub |
| EDDF | FRA  | Frankfurt International | Mega hub |
| OMDB | DXB  | Dubai International | Mega hub |
| VHHH | HKG  | Hong Kong International | Mega hub |
| YSSY | SYD  | Sydney Kingsford Smith | Regional hub |

To add an airport, add an entry to `opensky/airports.py` with the bounding box coordinates and congestion thresholds appropriate for that airport's traffic volume.

---

## Rate limits and credit budget

OpenSky issues API credits per day. Anonymous users receive 400 credits/day; authenticated users receive 4,000 credits/day.

| Call | Endpoint | Credits | Cache TTL |
|------|----------|---------|-----------|
| Single aircraft state | `/states/all?icao24=` | 1 | 10s |
| Airport bounding box | `/states/all?lamin=...` | 1 | 30s |
| Departures / arrivals | `/flights/departure` or `/arrival` | 2–4 | 5 min |
| Aircraft history | `/flights/aircraft` | 2 | 2 min |

With 4,000 credits/day and the caching strategy above, normal interactive use stays well within budget. The TTL cache is in-memory and resets when the server restarts.

If a 429 rate-limit response is received, the server reads the `X-Rate-Limit-Retry-After-Seconds` header and returns a descriptive error indicating how long to wait.

---

## Project structure

```
airport-ops-mcp/
├── main.py                  # FastMCP server entry point
├── opensky/
│   ├── client.py            # TokenManager + async httpx API wrapper
│   ├── types.py             # StateVector, Flight dataclasses
│   └── airports.py          # ICAO → bounding box + congestion thresholds
├── resources/
│   ├── airport_flights.py   # Departure and arrival resources
│   └── aircraft_state.py    # Live aircraft state resource
├── tools/
│   ├── track_aircraft.py
│   ├── airport_traffic.py
│   ├── congestion_check.py
│   └── delay_pattern.py
├── prompts/
│   ├── departure_brief.py
│   ├── disruption_scope.py
│   └── congestion_check.py
├── utils/
│   ├── cache.py             # Async TTL cache
│   └── units.py             # m/s→knots, m→ft, unix→UTC
├── .env.example
├── pyproject.toml
└── README.md
```

---

## Development

Run the server in development mode with the MCP Inspector:

```bash
uv run mcp dev main.py
```

This opens the Inspector UI at `http://localhost:5173` where you can browse resources, call tools, and test prompts interactively without Claude Desktop.

Run tests:

```bash
uv run pytest
```

---

## Background

This server was built as a portfolio project to demonstrate operations-side MCP design — not consumer tooling. The key design decisions:

- **Resources vs Tools**: Historical flight data (departures, arrivals, aircraft state) is exposed as Resources because Claude reads it passively before reasoning. Live interactive queries (track, traffic, congestion) are Tools because they require user input at invocation time.
- **Prompts encode domain intelligence**: The `/departure-brief` prompt doesn't just dump raw data at Claude — it frames the question the way an ops controller would ask it. That framing requires understanding what an ops team actually needs, which is the moat that a generic developer cannot replicate.
- **Congestion thresholds are calibrated**: A hub like EGLL with 30 aircraft on ground is within normal bounds. The same count at VGHS is a critical situation. These thresholds are encoded in `opensky/airports.py` and reflect real operational norms.

---

## Data source

Live and historical flight data is provided by the [OpenSky Network](https://opensky-network.org), a community-based receiver network for air traffic surveillance. Data is provided under the [OpenSky Network Terms of Use](https://opensky-network.org/about/terms-of-use).

---

## License

MIT
