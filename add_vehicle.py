from app import app, db
from app import Vehicle, Station

with app.app_context():
    # Ensure there's at least one station in the database
    station = Station.query.first()
    if not station:
        station = Station(name="Main Station", address="123 Fire St", latitude=40.7128, longitude=-74.0060)
        db.session.add(station)
        db.session.commit()

    # Add vehicles
    vehicles = [
        Vehicle(name="Engine 1", vehicle_type="Engine", status="available", capacity=5, station_id=station.id),
        Vehicle(name="Ladder 1", vehicle_type="Ladder", status="available", capacity=3, station_id=station.id),
        Vehicle(name="Ambulance 1", vehicle_type="Ambulance", status="available", capacity=2, station_id=station.id),
        Vehicle(name="Hazmat 1", vehicle_type="Hazmat", status="maintenance", capacity=4, station_id=station.id),
    ]

    for vehicle in vehicles:
        db.session.add(vehicle)
    
    db.session.commit()
    print("Vehicles added successfully!")