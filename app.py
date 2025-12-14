from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dental_clinic.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'

db = SQLAlchemy(app)

# ==================== Models ====================

class Patient(db.Model):
    __tablename__ = 'patients'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    diseases = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    appointments = db.relationship('Appointment', backref='patient', lazy=True, cascade='all, delete-orphan')
    medical_history = db.relationship('MedicalHistory', backref='patient', uselist=False, cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='patient', lazy=True, cascade='all, delete-orphan')

class Doctor(db.Model):
    __tablename__ = 'doctors'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    specialization = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    
    appointments = db.relationship('Appointment', backref='doctor', lazy=True)
    reviews = db.relationship('Review', backref='doctor', lazy=True)

class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    reason = db.Column(db.Text)
    symptoms = db.Column(db.Text)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, completed, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    notes = db.relationship('DoctorNote', backref='appointment', uselist=False, cascade='all, delete-orphan')

class DoctorNote(db.Model):
    __tablename__ = 'doctor_notes'
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=False)
    diagnosis = db.Column(db.Text)
    treatment = db.Column(db.Text)
    prescription = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MedicalHistory(db.Model):
    __tablename__ = 'medical_history'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    allergies = db.Column(db.Text)
    previous_treatments = db.Column(db.Text)
    chronic_conditions = db.Column(db.Text)
    medications = db.Column(db.Text)
    notes = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ==================== Authentication Routes ====================

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    """Patient Sign Up"""
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['name', 'email', 'password', 'phone', 'diseases']
    if not all(k in data for k in required_fields):
        return jsonify({'error': 'All fields are required'}), 400
    
    # Check if email exists
    if Patient.query.filter_by(email=data['email'].lower().strip()).first():
        return jsonify({'error': 'Email already exists'}), 409
    
    # Create new patient
    patient = Patient(
        name=data['name'].strip(),
        email=data['email'].lower().strip(),
        password=data['password'],  # TODO: Hash in production
        phone=data['phone'].strip(),
        diseases=data['diseases'].strip()
    )
    
    db.session.add(patient)
    db.session.commit()
    
    return jsonify({
        'message': 'Registration successful',
        'patient': {
            'id': patient.id,
            'name': patient.name,
            'email': patient.email,
            'phone': patient.phone
        }
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Patient/Doctor Login"""
    data = request.get_json()
    
    if not all(k in data for k in ['email', 'password']):
        return jsonify({'error': 'Email and password are required'}), 400
    
    user_type = data.get('user_type', 'patient')
    
    if user_type == 'doctor':
        # Doctor login
        doctor = Doctor.query.filter_by(email=data['email'].lower().strip()).first()
        
        if not doctor or (doctor.password and doctor.password != data['password']):
            return jsonify({'error': 'Incorrect email or password'}), 401
        
        return jsonify({
            'message': 'Login successful',
            'user_type': 'doctor',
            'doctor': {
                'id': doctor.id,
                'name': doctor.name,
                'email': doctor.email,
                'specialization': doctor.specialization
            }
        }), 200
    else:
        # Patient login
        patient = Patient.query.filter_by(email=data['email'].lower().strip()).first()
        
        if not patient or patient.password != data['password']:
            return jsonify({'error': 'Incorrect email or password'}), 401
        
        return jsonify({
            'message': 'Login successful',
            'user_type': 'patient',
            'patient': {
                'id': patient.id,
                'name': patient.name,
                'email': patient.email,
                'phone': patient.phone,
                'diseases': patient.diseases
            }
        }), 200

# ==================== Appointment Routes ====================

@app.route('/api/appointments', methods=['GET'])
def get_appointments():
    """Get all appointments or filter by patient/doctor"""
    patient_id = request.args.get('patient_id', type=int)
    doctor_id = request.args.get('doctor_id', type=int)
    status = request.args.get('status')
    
    query = Appointment.query
    
    if patient_id:
        query = query.filter_by(patient_id=patient_id)
    if doctor_id:
        query = query.filter_by(doctor_id=doctor_id)
    if status:
        query = query.filter_by(status=status)
    
    appointments = query.all()
    
    return jsonify([{
        'id': apt.id,
        'patient_name': apt.patient.name,
        'doctor_name': apt.doctor.name,
        'appointment_date': apt.appointment_date.isoformat(),
        'reason': apt.reason,
        'symptoms': apt.symptoms,
        'status': apt.status,
        'created_at': apt.created_at.isoformat()
    } for apt in appointments]), 200

@app.route('/api/appointments/<int:id>', methods=['GET'])
def get_appointment(id):
    """Get single appointment details"""
    apt = Appointment.query.get_or_404(id)
    
    return jsonify({
        'id': apt.id,
        'patient_id': apt.patient_id,
        'patient_name': apt.patient.name,
        'doctor_id': apt.doctor_id,
        'doctor_name': apt.doctor.name,
        'appointment_date': apt.appointment_date.isoformat(),
        'reason': apt.reason,
        'symptoms': apt.symptoms,
        'status': apt.status,
        'created_at': apt.created_at.isoformat(),
        'notes': {
            'diagnosis': apt.notes.diagnosis,
            'treatment': apt.notes.treatment,
            'prescription': apt.notes.prescription,
            'notes': apt.notes.notes
        } if apt.notes else None
    }), 200

@app.route('/api/appointments', methods=['POST'])
def book_appointment():
    """Book new appointment"""
    data = request.get_json()
    
    # Validate required fields
    if not all(k in data for k in ['patient_id', 'doctor_id', 'appointment_date']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Parse appointment date
    try:
        appointment_date = datetime.fromisoformat(data['appointment_date'].replace('Z', '+00:00'))
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use ISO 8601'}), 400
    
    # Check if time slot is available
    existing = Appointment.query.filter_by(
        doctor_id=data['doctor_id'],
        appointment_date=appointment_date,
        status='scheduled'
    ).first()
    
    if existing:
        return jsonify({'error': 'Time slot already booked. Please choose another slot.'}), 409
    
    # Create appointment
    appointment = Appointment(
        patient_id=data['patient_id'],
        doctor_id=data['doctor_id'],
        appointment_date=appointment_date,
        reason=data.get('reason', ''),
        symptoms=data.get('symptoms', ''),
        status='scheduled'
    )
    
    db.session.add(appointment)
    db.session.commit()
    
    return jsonify({
        'message': 'Appointment booked successfully',
        'appointment': {
            'id': appointment.id,
            'patient_name': appointment.patient.name,
            'doctor_name': appointment.doctor.name,
            'appointment_date': appointment.appointment_date.isoformat(),
            'status': appointment.status
        }
    }), 201

@app.route('/api/appointments/<int:id>', methods=['PUT'])
def edit_appointment(id):
    """Edit existing appointment"""
    apt = Appointment.query.get_or_404(id)
    data = request.get_json()
    
    # Check if appointment can be edited
    if apt.status == 'completed':
        return jsonify({'error': 'Cannot edit completed appointment'}), 400
    
    # Update appointment date if provided
    if 'appointment_date' in data:
        try:
            new_date = datetime.fromisoformat(data['appointment_date'].replace('Z', '+00:00'))
            
            # Check if new time slot is available
            existing = Appointment.query.filter(
                Appointment.id != id,
                Appointment.doctor_id == apt.doctor_id,
                Appointment.appointment_date == new_date,
                Appointment.status == 'scheduled'
            ).first()
            
            if existing:
                return jsonify({'error': 'New time slot is not available'}), 409
            
            apt.appointment_date = new_date
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400
    
    # Update other fields
    if 'reason' in data:
        apt.reason = data['reason']
    if 'symptoms' in data:
        apt.symptoms = data['symptoms']
    if 'status' in data:
        apt.status = data['status']
    
    db.session.commit()
    
    return jsonify({
        'message': 'Appointment updated successfully',
        'appointment': {
            'id': apt.id,
            'appointment_date': apt.appointment_date.isoformat(),
            'reason': apt.reason,
            'symptoms': apt.symptoms,
            'status': apt.status
        }
    }), 200

@app.route('/api/appointments/<int:id>', methods=['DELETE'])
def cancel_appointment(id):
    """Cancel appointment"""
    apt = Appointment.query.get_or_404(id)
    
    if apt.status == 'completed':
        return jsonify({'error': 'Cannot cancel completed appointment'}), 400
    
    apt.status = 'cancelled'
    db.session.commit()
    
    return jsonify({'message': 'Appointment cancelled successfully'}), 200

@app.route('/api/appointments/available-slots', methods=['GET'])
def get_available_slots():
    """Get available time slots for a doctor"""
    doctor_id = request.args.get('doctor_id', type=int)
    date = request.args.get('date')  # YYYY-MM-DD
    
    if not doctor_id or not date:
        return jsonify({'error': 'doctor_id and date are required'}), 400
    
    try:
        target_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    
    # Get booked appointments for that day
    booked = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        db.func.date(Appointment.appointment_date) == target_date,
        Appointment.status == 'scheduled'
    ).all()
    
    booked_times = [apt.appointment_date.time() for apt in booked]
    
    # Generate available slots (9 AM - 5 PM, hourly)
    from datetime import time
    all_slots = [time(hour=h) for h in range(9, 17)]
    available_slots = [slot for slot in all_slots if slot not in booked_times]
    
    return jsonify({
        'date': date,
        'doctor_id': doctor_id,
        'available_slots': [slot.strftime('%H:%M') for slot in available_slots]
    }), 200

# ==================== Doctor Notes Routes ====================

@app.route('/api/appointments/<int:id>/notes', methods=['POST'])
def add_doctor_notes(id):
    """Add doctor notes to appointment"""
    apt = Appointment.query.get_or_404(id)
    data = request.get_json()
    
    # Check if notes already exist
    if apt.notes:
        return jsonify({'error': 'Notes already exist. Use PUT to update.'}), 400
    
    notes = DoctorNote(
        appointment_id=id,
        diagnosis=data.get('diagnosis', ''),
        treatment=data.get('treatment', ''),
        prescription=data.get('prescription', ''),
        notes=data.get('notes', '')
    )
    
    # Mark appointment as completed
    apt.status = 'completed'
    
    db.session.add(notes)
    db.session.commit()
    
    return jsonify({
        'message': 'Doctor notes added successfully',
        'notes': {
            'id': notes.id,
            'diagnosis': notes.diagnosis,
            'treatment': notes.treatment,
            'prescription': notes.prescription,
            'notes': notes.notes
        }
    }), 201

@app.route('/api/appointments/<int:id>/notes', methods=['PUT'])
def update_doctor_notes(id):
    """Update doctor notes"""
    apt = Appointment.query.get_or_404(id)
    
    if not apt.notes:
        return jsonify({'error': 'No notes found. Use POST to create.'}), 404
    
    data = request.get_json()
    
    if 'diagnosis' in data:
        apt.notes.diagnosis = data['diagnosis']
    if 'treatment' in data:
        apt.notes.treatment = data['treatment']
    if 'prescription' in data:
        apt.notes.prescription = data['prescription']
    if 'notes' in data:
        apt.notes.notes = data['notes']
    
    apt.notes.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'message': 'Doctor notes updated successfully',
        'notes': {
            'diagnosis': apt.notes.diagnosis,
            'treatment': apt.notes.treatment,
            'prescription': apt.notes.prescription,
            'notes': apt.notes.notes,
            'updated_at': apt.notes.updated_at.isoformat()
        }
    }), 200

@app.route('/api/appointments/<int:id>/notes', methods=['GET'])
def get_doctor_notes(id):
    """Get doctor notes for appointment"""
    apt = Appointment.query.get_or_404(id)
    
    if not apt.notes:
        return jsonify({'error': 'No notes found'}), 404
    
    return jsonify({
        'diagnosis': apt.notes.diagnosis,
        'treatment': apt.notes.treatment,
        'prescription': apt.notes.prescription,
        'notes': apt.notes.notes,
        'created_at': apt.notes.created_at.isoformat(),
        'updated_at': apt.notes.updated_at.isoformat()
    }), 200

# ==================== Medical History Routes ====================

@app.route('/api/patients/<int:id>/history', methods=['GET'])
def get_medical_history(id):
    """Get patient medical history"""
    patient = Patient.query.get_or_404(id)
    
    if not patient.medical_history:
        return jsonify({'message': 'No medical history found'}), 404
    
    history = patient.medical_history
    return jsonify({
        'allergies': history.allergies,
        'previous_treatments': history.previous_treatments,
        'chronic_conditions': history.chronic_conditions,
        'medications': history.medications,
        'notes': history.notes,
        'updated_at': history.updated_at.isoformat()
    }), 200

@app.route('/api/patients/<int:id>/history', methods=['POST', 'PUT'])
def update_medical_history(id):
    """Create or update patient medical history"""
    patient = Patient.query.get_or_404(id)
    data = request.get_json()
    
    if patient.medical_history:
        # Update existing
        history = patient.medical_history
    else:
        # Create new
        history = MedicalHistory(patient_id=id)
        db.session.add(history)
    
    if 'allergies' in data:
        history.allergies = data['allergies']
    if 'previous_treatments' in data:
        history.previous_treatments = data['previous_treatments']
    if 'chronic_conditions' in data:
        history.chronic_conditions = data['chronic_conditions']
    if 'medications' in data:
        history.medications = data['medications']
    if 'notes' in data:
        history.notes = data['notes']
    
    history.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'message': 'Medical history saved successfully',
        'history': {
            'allergies': history.allergies,
            'previous_treatments': history.previous_treatments,
            'chronic_conditions': history.chronic_conditions,
            'medications': history.medications,
            'notes': history.notes
        }
    }), 200

# ==================== Review Routes ====================

@app.route('/api/reviews', methods=['GET'])
def get_reviews():
    """Get all reviews or filter by doctor"""
    doctor_id = request.args.get('doctor_id', type=int)
    
    query = Review.query
    if doctor_id:
        query = query.filter_by(doctor_id=doctor_id)
    
    reviews = query.order_by(Review.created_at.desc()).all()
    
    return jsonify([{
        'id': r.id,
        'patient_name': r.patient.name,
        'doctor_name': r.doctor.name,
        'rating': r.rating,
        'comment': r.comment,
        'created_at': r.created_at.isoformat()
    } for r in reviews]), 200

@app.route('/api/reviews', methods=['POST'])
def add_review():
    """Add new review"""
    data = request.get_json()
    
    if not all(k in data for k in ['patient_id', 'doctor_id', 'rating']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    if not 1 <= data['rating'] <= 5:
        return jsonify({'error': 'Rating must be between 1 and 5'}), 400
    
    review = Review(
        patient_id=data['patient_id'],
        doctor_id=data['doctor_id'],
        rating=data['rating'],
        comment=data.get('comment', '')
    )
    
    db.session.add(review)
    db.session.commit()
    
    return jsonify({
        'message': 'Review added successfully',
        'review': {
            'id': review.id,
            'rating': review.rating,
            'comment': review.comment,
            'created_at': review.created_at.isoformat()
        }
    }), 201

@app.route('/api/reviews/<int:id>', methods=['PUT'])
def update_review(id):
    """Update review"""
    review = Review.query.get_or_404(id)
    data = request.get_json()
    
    if 'rating' in data:
        if not 1 <= data['rating'] <= 5:
            return jsonify({'error': 'Rating must be between 1 and 5'}), 400
        review.rating = data['rating']
    
    if 'comment' in data:
        review.comment = data['comment']
    
    db.session.commit()
    
    return jsonify({
        'message': 'Review updated successfully',
        'review': {
            'rating': review.rating,
            'comment': review.comment
        }
    }), 200

@app.route('/api/reviews/<int:id>', methods=['DELETE'])
def delete_review(id):
    """Delete review"""
    review = Review.query.get_or_404(id)
    db.session.delete(review)
    db.session.commit()
    
    return jsonify({'message': 'Review deleted successfully'}), 200

@app.route('/api/doctors/<int:id>/rating', methods=['GET'])
def get_doctor_rating(id):
    """Get average rating for doctor"""
    doctor = Doctor.query.get_or_404(id)
    reviews = Review.query.filter_by(doctor_id=id).all()
    
    if not reviews:
        return jsonify({
            'doctor_name': doctor.name,
            'average_rating': 0,
            'total_reviews': 0
        }), 200
    
    avg_rating = sum(r.rating for r in reviews) / len(reviews)
    
    return jsonify({
        'doctor_name': doctor.name,
        'average_rating': round(avg_rating, 2),
        'total_reviews': len(reviews)
    }), 200

# ==================== Patient Routes ====================

@app.route('/api/patients', methods=['POST'])
def create_patient():
    """Create new patient (Sign Up)"""
    data = request.get_json()
    
    if not all(k in data for k in ['name', 'email', 'password']):
        return jsonify({'error': 'Name, email and password are required'}), 400
    
    # Check if email exists
    if Patient.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 409
    
    patient = Patient(
        name=data['name'],
        email=data['email'],
        password=data['password'],
        phone=data.get('phone', ''),
        diseases=data.get('diseases', '')
    )
    
    db.session.add(patient)
    db.session.commit()
    
    return jsonify({
        'message': 'Patient created successfully',
        'patient': {
            'id': patient.id,
            'name': patient.name,
            'email': patient.email,
            'phone': patient.phone
        }
    }), 201

@app.route('/api/patients', methods=['GET'])
def get_patients():
    """Get all patients"""
    patients = Patient.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'email': p.email,
        'phone': p.phone,
        'diseases': p.diseases
    } for p in patients]), 200

@app.route('/api/patients/<int:id>', methods=['GET'])
def get_patient(id):
    """Get single patient details"""
    patient = Patient.query.get_or_404(id)
    
    return jsonify({
        'id': patient.id,
        'name': patient.name,
        'email': patient.email,
        'phone': patient.phone,
        'diseases': patient.diseases,
        'created_at': patient.created_at.isoformat()
    }), 200

@app.route('/api/patients/with-appointments', methods=['GET'])
def get_patients_with_appointments():
    """Get all patients who have appointments"""
    doctor_id = request.args.get('doctor_id', type=int)
    
    query = db.session.query(Patient).join(Appointment).distinct()
    
    if doctor_id:
        query = query.filter(Appointment.doctor_id == doctor_id)
    
    patients = query.all()
    
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'email': p.email,
        'phone': p.phone,
        'diseases': p.diseases,
        'total_appointments': len(p.appointments)
    } for p in patients]), 200

# ==================== Doctor Routes ====================

@app.route('/api/doctors', methods=['POST'])
def create_doctor():
    """Create new doctor"""
    data = request.get_json()
    
    if not data.get('name'):
        return jsonify({'error': 'Name is required'}), 400
    
    # Check if email exists (if provided)
    if data.get('email'):
        existing = Doctor.query.filter_by(email=data['email']).first()
        if existing:
            return jsonify({'error': 'Email already exists'}), 409
    
    doctor = Doctor(
        name=data['name'],
        specialization=data.get('specialization', ''),
        email=data.get('email', ''),
        password=data.get('password', '')
    )
    
    db.session.add(doctor)
    db.session.commit()
    
    return jsonify({
        'message': 'Doctor created successfully',
        'doctor': {
            'id': doctor.id,
            'name': doctor.name,
            'specialization': doctor.specialization,
            'email': doctor.email
        }
    }), 201

@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    """Get all doctors"""
    doctors = Doctor.query.all()
    return jsonify([{
        'id': d.id,
        'name': d.name,
        'specialization': d.specialization,
        'email': d.email
    } for d in doctors]), 200

# ==================== Initialize Database ====================

@app.route('/api/init-db', methods=['POST'])
def init_database():
    """Initialize database with sample data"""
    db.drop_all()
    db.create_all()
    
    # Create sample doctors
    doctor1 = Doctor(
        name='Dr. Youmna Ali', 
        specialization='General Dentistry', 
        email='doctor@gmail.com',
        password='Doctor123*'
    )
    doctor2 = Doctor(
        name='Dr. Ahmed Hassan', 
        specialization='Orthodontics', 
        email='ahmed@clinic.com',
        password='Doctor123*'
    )
    
    db.session.add_all([doctor1, doctor2])
    db.session.commit()
    
    return jsonify({'message': 'Database initialized successfully with 2 doctors'}), 200

# ==================== Home Route ====================

@app.route('/')
def home():
    return jsonify({
        'message': 'Dental Clinic API - Dentistawy',
        'version': '1.0',
        'status': 'Running',
        'endpoints': {
            'auth': {
                'signup': 'POST /api/auth/signup',
                'login': 'POST /api/auth/login'
            },
            'appointments': {
                'list': 'GET /api/appointments',
                'create': 'POST /api/appointments',
                'get': 'GET /api/appointments/<id>',
                'update': 'PUT /api/appointments/<id>',
                'cancel': 'DELETE /api/appointments/<id>',
                'available_slots': 'GET /api/appointments/available-slots'
            },
            'patients': {
                'list': 'GET /api/patients',
                'get': 'GET /api/patients/<id>',
                'with_appointments': 'GET /api/patients/with-appointments',
                'history': 'GET/POST /api/patients/<id>/history'
            },
            'doctors': {
                'list': 'GET /api/doctors',
                'rating': 'GET /api/doctors/<id>/rating'
            },
            'reviews': {
                'list': 'GET /api/reviews',
                'create': 'POST /api/reviews'
            },
            'notes': {
                'add': 'POST /api/appointments/<id>/notes',
                'get': 'GET /api/appointments/<id>/notes'
            },
            'admin': {
                'init_db': 'POST /api/init-db'
            }
        }
    }), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)