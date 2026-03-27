import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from opensky.client import OpenSkyClient
import resources.airport_flights as airport_flights_resource
import resources.aircraft_state as aircraft_state_resource
import tools.track_aircraft as track_aircraft_tool
import tools.airport_traffic as airport_traffic_tool
import tools.congestion_check as congestion_check_tool
import tools.delay_pattern as delay_pattern_tool
import prompts.departure_brief as departure_brief_prompt
import prompts.disruption_scope as disruption_scope_prompt
import prompts.congestion_check as congestion_check_prompt

load_dotenv()

mcp = FastMCP("Airport Operations Intelligence")

client = OpenSkyClient(
    client_id=os.environ["OPENSKY_CLIENT_ID"],
    client_secret=os.environ["OPENSKY_CLIENT_SECRET"],
)

airport_flights_resource.register(mcp, client)
aircraft_state_resource.register(mcp, client)
track_aircraft_tool.register(mcp, client)
airport_traffic_tool.register(mcp, client)
congestion_check_tool.register(mcp, client)
delay_pattern_tool.register(mcp, client)
departure_brief_prompt.register(mcp, client)
disruption_scope_prompt.register(mcp, client)
congestion_check_prompt.register(mcp, client)


if __name__ == "__main__":
    mcp.run()
