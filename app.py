# Fire Department Real-Time Monitoring & Evaluation System
# This is a comprehensive Flask application for fire department operations management

import os
import json
import uuid
from datetime import datetime, timedelta
import random
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func, desc
import folium
from folium.plugins import HeatMap, MarkerCluster
import pandas as pd
import numpy as np

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_for_testing')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///firedb.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ====================== DATABASE MODELS ======================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(100))
    role = db.Column(db.String(20), default='firefighter')  # admin, chief, dispatcher, firefighter
    station_id = db.Column(db.Integer, db.ForeignKey('station.id'))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Station(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    phone = db.Column(db.String(20))
    personnel = db.relationship('User', backref='station')
    vehicles = db.relationship('Vehicle', backref='station')
    incidents = db.relationship('Incident', backref='responding_station')
    
class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    vehicle_type = db.Column(db.String(50))  # Engine, Ladder, Ambulance, etc.
    status = db.Column(db.String(20), default='available')  # available, responding, maintenance
    capacity = db.Column(db.Integer)
    last_maintenance = db.Column(db.DateTime)
    next_maintenance = db.Column(db.DateTime)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    station_id = db.Column(db.Integer, db.ForeignKey('station.id'))
    incidents = db.relationship('VehicleAssignment', back_populates='vehicle')
    
class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    equipment_type = db.Column(db.String(50))
    status = db.Column(db.String(20), default='operational')  # operational, needs_maintenance, out_of_service
    last_inspection = db.Column(db.DateTime)
    next_inspection = db.Column(db.DateTime)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'))
    vehicle = db.relationship('Vehicle', backref='equipment')
    
class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    incident_number = db.Column(db.String(20), unique=True)
    incident_type = db.Column(db.String(50))  # fire, medical, hazmat, rescue
    status = db.Column(db.String(20), default='reported')  # reported, responding, onscene, resolved
    priority = db.Column(db.Integer)  # 1-5, with 1 being highest priority
    address = db.Column(db.String(200))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    reported_time = db.Column(db.DateTime, default=datetime.utcnow)
    dispatch_time = db.Column(db.DateTime)
    arrival_time = db.Column(db.DateTime)
    controlled_time = db.Column(db.DateTime)
    cleared_time = db.Column(db.DateTime)
    description = db.Column(db.Text)
    reporter_name = db.Column(db.String(100))
    reporter_phone = db.Column(db.String(20))
    station_id = db.Column(db.Integer, db.ForeignKey('station.id'))
    personnel = db.relationship('PersonnelAssignment', back_populates='incident')
    vehicles = db.relationship('VehicleAssignment', back_populates='incident')
    notes = db.relationship('IncidentNote', backref='incident')
    
class PersonnelAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    incident_id = db.Column(db.Integer, db.ForeignKey('incident.id'))
    role = db.Column(db.String(50))  # commander, operator, medic, etc.
    assigned_time = db.Column(db.DateTime, default=datetime.utcnow)
    cleared_time = db.Column(db.DateTime)
    user = db.relationship('User', backref='assignments')
    incident = db.relationship('Incident', back_populates='personnel')
    
class VehicleAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'))
    incident_id = db.Column(db.Integer, db.ForeignKey('incident.id'))
    dispatched_time = db.Column(db.DateTime, default=datetime.utcnow)
    arrived_time = db.Column(db.DateTime)
    cleared_time = db.Column(db.DateTime)
    vehicle = db.relationship('Vehicle', back_populates='incidents')
    incident = db.relationship('Incident', back_populates='vehicles')
    
class IncidentNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey('incident.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    content = db.Column(db.Text)
    user = db.relationship('User', backref='notes')
    
class Maintenance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'))
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    description = db.Column(db.Text)
    cost = db.Column(db.Float)
    status = db.Column(db.String(20))  # scheduled, in_progress, completed
    technician = db.Column(db.String(100))
    vehicle = db.relationship('Vehicle', backref='maintenance_records')
    
class TrainingRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    training_type = db.Column(db.String(100))
    completion_date = db.Column(db.DateTime)
    expiration_date = db.Column(db.DateTime)
    certification_number = db.Column(db.String(50))
    status = db.Column(db.String(20))  # completed, expired, in_progress
    user = db.relationship('User', backref='training_records')

class EmergencyContact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    organization = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    contact_type = db.Column(db.String(50))  # police, hospital, utility, government
    address = db.Column(db.String(200))
    notes = db.Column(db.Text)

# ====================== ROUTE HANDLERS ======================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Count active incidents
    active_incidents = Incident.query.filter(Incident.status != 'resolved').count()

    # Get vehicle and personnel availability
    available_vehicles = Vehicle.query.filter_by(status='available').count()
    total_vehicles = Vehicle.query.count()

    # Calculate average response time (in minutes)
    response_times = db.session.query(
        func.avg(Incident.arrival_time - Incident.dispatch_time)
    ).filter(
        Incident.arrival_time.isnot(None),
        Incident.dispatch_time.isnot(None)
    ).scalar()

    # Convert response time to minutes
    if response_times:
        average_response_time = response_times.total_seconds() / 60
    else:
        average_response_time = None

    # Recent incidents
    recent_incidents = Incident.query.order_by(desc(Incident.reported_time)).limit(5).all()
    print("Average response time:", average_response_time)

    return render_template(
        'dashboard.html',
        active_incidents=active_incidents,
        available_vehicles=available_vehicles,
        total_vehicles=total_vehicles,
        recent_incidents=recent_incidents,
        average_response_time=average_response_time
    )

@app.route('/incidents')
@login_required
def incidents():
    status_filter = request.args.get('status', 'all')
    type_filter = request.args.get('type', 'all')
    
    query = Incident.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if type_filter != 'all':
        query = query.filter_by(incident_type=type_filter)
    
    incidents = query.order_by(desc(Incident.reported_time)).all()
    
    return render_template('incidents.html', incidents=incidents, status_filter=status_filter, type_filter=type_filter)

@app.route('/incidents/<int:incident_id>')
@login_required
def incident_detail(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    available_vehicles = Vehicle.query.filter_by(status='available').all()
    return render_template('incident_detail.html', incident=incident, available_vehicles=available_vehicles)
@app.route('/incidents/new', methods=['GET', 'POST'])
@login_required
def new_incident():
    if request.method == 'POST':
        # Create new incident based on form data
        incident = Incident(
            incident_number=f"INC-{uuid.uuid4().hex[:8].upper()}",
            incident_type=request.form.get('incident_type'),
            priority=int(request.form.get('priority')),
            address=request.form.get('address'),
            latitude=float(request.form.get('latitude')),
            longitude=float(request.form.get('longitude')),
            description=request.form.get('description'),
            reporter_name=request.form.get('reporter_name'),
            reporter_phone=request.form.get('reporter_phone'),
            status='reported',
            reported_time=datetime.utcnow(),
            station_id=current_user.station_id
        )
        
        db.session.add(incident)
        db.session.commit()
        
        flash('Incident created successfully')
        return redirect(url_for('incident_detail', incident_id=incident.id))
    
    return render_template('new_incident.html')

@app.route('/incidents/<int:incident_id>/update', methods=['POST'])
@login_required
def update_incident(incident_id):
    incident = Incident.query.get_or_404(incident_id)

    if 'status' in request.form:
        incident.status = request.form.get('status')

        # Update timestamps based on status changes
        if incident.status == 'responding' and not incident.dispatch_time:
            incident.dispatch_time = datetime.utcnow()
        elif incident.status == 'onscene' and not incident.arrival_time:
            incident.arrival_time = datetime.utcnow()
        elif incident.status == 'resolved' and not incident.cleared_time:
            incident.cleared_time = datetime.utcnow()

            # Update vehicle statuses to "available"
            for assignment in incident.vehicles:
                if not assignment.cleared_time:
                    assignment.cleared_time = datetime.utcnow()
                    assignment.vehicle.status = 'available'
                    db.session.add(assignment.vehicle)

    # Update other fields if provided
    for field in ['priority', 'description', 'address']:
        if field in request.form:
            setattr(incident, field, request.form.get(field))

    db.session.commit()
    return redirect(url_for('incident_detail', incident_id=incident.id))
@app.route('/incidents/<int:incident_id>/assign_vehicle', methods=['POST'])
@login_required
def assign_vehicle_to_incident(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    vehicle_id = request.form.get('vehicle_id')

    if not vehicle_id:
        flash('No vehicle selected')
        return redirect(url_for('incident_detail', incident_id=incident.id))

    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        flash('Vehicle not found')
        return redirect(url_for('incident_detail', incident_id=incident.id))

    # Check if the vehicle is already assigned to this incident
    existing_assignment = VehicleAssignment.query.filter_by(
        vehicle_id=vehicle.id,
        incident_id=incident.id,
        cleared_time=None
    ).first()

    if existing_assignment:
        flash('Vehicle is already assigned to this incident')
        return redirect(url_for('incident_detail', incident_id=incident.id))

    # Assign the vehicle to the incident
    assignment = VehicleAssignment(
        vehicle_id=vehicle.id,
        incident_id=incident.id,
        dispatched_time=datetime.utcnow()
    )
    db.session.add(assignment)

    # Update the vehicle status to "responding"
    vehicle.status = 'responding'
    db.session.commit()

    flash('Vehicle assigned successfully')
    return redirect(url_for('incident_detail', incident_id=incident.id))

@app.route('/incidents/<int:incident_id>/notes', methods=['POST'])
@login_required
def add_incident_note(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    
    note = IncidentNote(
        incident_id=incident.id,
        user_id=current_user.id,
        content=request.form.get('content')
    )
    
    db.session.add(note)
    db.session.commit()
    
    return redirect(url_for('incident_detail', incident_id=incident.id))

@app.route('/delete_all_incidents', methods=['GET'])
@login_required
def delete_all_incidents():
    try:
        # Delete all incidents
        Incident.query.delete()
        db.session.commit()
        flash('All incidents deleted successfully!')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting incidents: {str(e)}')
    
    return redirect(url_for('dashboard'))
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        name = request.form.get('name')
        role = request.form.get('role', 'firefighter')  # Default role is 'firefighter'

        # Check if the username already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))

        # Create a new user
        user = User(username=username, name=name, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))

    return render_template('register.html')
@app.route('/incidents/<int:incident_id>/delete', methods=['POST'])
@login_required
def delete_incident(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    
    try:
        # Revert assigned vehicles to "available"
        for vehicle_assignment in incident.vehicles:
            vehicle = vehicle_assignment.vehicle
            vehicle.status = 'available'  # Set the vehicle status to "available"
            db.session.add(vehicle)
        
        # Delete the incident
        db.session.delete(incident)
        db.session.commit()
        flash('Incident deleted successfully, and assigned vehicles reverted to available!')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting incident: {str(e)}')
    
    return redirect(url_for('incidents'))
@app.route('/incidents/<int:incident_id>/assign', methods=['POST'])
@login_required
def assign_resources(incident_id):
    incident = Incident.query.get_or_404(incident_id)
    
    # Assign vehicles
    vehicle_ids = request.form.getlist('vehicles')
    for vehicle_id in vehicle_ids:
        vehicle = Vehicle.query.get(vehicle_id)
        if vehicle:
            # Check if already assigned
            existing = VehicleAssignment.query.filter_by(
                vehicle_id=vehicle.id, 
                incident_id=incident.id,
                cleared_time=None
            ).first()