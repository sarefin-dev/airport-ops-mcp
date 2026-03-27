import time

from mcp.server.fastmcp import FastMCP

from opensky.client import OpenSkyClient
from utils.units import m_to_feet, ms_to_knots, unix_to_utc


def register(mcp: FastMCP, client: OpenSkyClient) -> None:

    @mcp.prompt()
    async def disruption_scope(callsign: str) -> str:
        """Assess the operational impact of a specific flight disruption.

        Fetches live position and recent flight history for the aircraft,
        then produces a structured impact assessment template.

        callsign — ICAO callsign (e.g. BG401, EK007).
        """
        callsign = callsign.upper().strip()

        try:
            state = await client.get_aircraft_state_by_callsign(callsign)
            if state:
                pos = (
                    f"Position: {state.latitude:.4f}°, {state.longitude:.4f}°"
                    if state.latitude is not None else "Position: unavailable"
                )
                alt = (
                    f"Altitude: {m_to_feet(state.baro_altitude)} ft"
                    if state.baro_altitude is not None else "Altitude: unavailable"
                )
                spd = (
                    f"Speed: {ms_to_knots(state.velocity)} kts"
                    if state.velocity is not None else "Speed: unavailable"
                )
                hdg = (
                    f"Heading: {state.true_track}°"
                    if state.true_track is not None else "Heading: unavailable"
                )
                vrate = (
                    f"Vertical rate: {ms_to_knots(state.vertical_rate)} kts"
                    if state.vertical_rate is not None else "Vertical rate: unavailable"
                )
                phase = "on ground" if state.on_ground else "airborne"
                live_summary = f"Status: {phase}\n{pos}\n{alt}\n{spd}\n{hdg}\n{vrate}"
                icao24 = state.icao24
            else:
                live_summary = "No live state found — aircraft may be on ground or out of ADS-B coverage."
                icao24 = None
        except Exception as exc:
            live_summary = f"Live state unavailable: {exc}"
            icao24 = None

        history_summary = "Flight history unavailable."
        if icao24:
            try:
                now = int(time.time())
                history = await client.get_aircraft_history(icao24, now - 172800, now)
                if history:
                    recent = history[-3:]
                    lines = []
                    for f in recent:
                        dep = f.est_departure_airport or "?"
                        arr = f.est_arrival_airport or "?"
                        lines.append(
                            f"  {dep} → {arr}  "
                            f"departed {unix_to_utc(f.first_seen)}"
                        )
                    history_summary = f"Recent flights (last 48h):\n" + "\n".join(lines)
                else:
                    history_summary = "No flight history in last 48h."
            except Exception as exc:
                history_summary = f"Flight history unavailable: {exc}"

        return f"""You are an airport operations intelligence assistant assessing the operational impact of a flight disruption.

Flight: {callsign}

LIVE POSITION DATA
{live_summary}

RECENT FLIGHT HISTORY
{history_summary}

---

Produce a structured disruption impact assessment covering:

1. CURRENT POSITION AND FLIGHT PHASE
   Where is this aircraft now? What phase of flight (climb, cruise, descent, holding, ground)? Estimate position relative to likely destination.

2. ESTIMATED ARRIVAL IMPACT
   Based on current position, speed, and heading — is this flight likely to arrive early, on time, or delayed? Quantify if possible.

3. DOWNSTREAM CONNECTION RISK
   What is the risk to connecting passengers? Consider typical connection times at the likely arrival airport. Flag high-risk scenarios.

4. RECOMMENDED ACTIONS
   What should operations do now? Gate holding, connection protection, passenger re-accommodation triggers?

Tone: direct, operational. Assume the reader is a disruption control officer. Flag where data is insufficient for a confident assessment."""
