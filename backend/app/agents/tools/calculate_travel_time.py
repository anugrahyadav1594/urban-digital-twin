from app.agents.tools.contracts import TravelTimeRequest, TravelTimeResponse


def calculate_travel_time(request: TravelTimeRequest) -> TravelTimeResponse:
    """Calculate the distance and travel time deterministically between two locations."""
    origin = request.origin.lower()
    destination = request.destination.lower()
    
    # Deterministic distance logic based on inputs
    dist = float(abs(len(origin) - len(destination)) * 1.5 + 4.0)
    
    speed_map = {
        "driving": 45.0,  # km/h
        "transit": 25.0,
        "walking": 5.0
    }
    
    speed = speed_map.get(request.mode.lower(), 40.0)
    time_hours = dist / speed
    time_minutes = round(time_hours * 60.0, 1)
    
    return TravelTimeResponse(travel_time_minutes=time_minutes, distance_km=dist)
