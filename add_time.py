from datetime import datetime, timedelta
from app import app, db, Incident

with app.app_context():
    # Create a test incident
    incident = Incident(
        incident_number="INC-12345",
        incident_type="fire",
        status="resolved",
        priority=1,
        address="123 Test St",
        reported_time=datetime.utcnow() - timedelta(hours=2),
        dispatch_time=datetime.utcnow() - timedelta(hours=1, minutes=45),
        arrival_time=datetime.utcnow() - timedelta(hours=1, minutes=30),
        description="Test incident"
    )
    db.session.add(incident)
    db.session.commit()
    print("Test incident added successfully!")