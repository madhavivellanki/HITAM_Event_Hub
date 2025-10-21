from datetime import datetime, timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError

# ----------------- Configuration and Initialization -----------------
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ----------------- Define Models (Tables) -----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='student')

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)
    venue_id = db.Column(db.Integer, db.ForeignKey('venue.id'))
    organizer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='pending')

class Venue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    capacity = db.Column(db.Integer, default=0)

class EventRegistration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    registration_time = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('event_id', 'user_id', name='_user_event_uc'),)

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False) 
    comments = db.Column(db.Text)
    feedback_time = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('event_id', 'user_id', name='_user_feedback_uc'),)


# ----------------- Core Logic: Create Tables and Insert Data -----------------

def init_db():
    with app.app_context():
        # Step 1: Drop/Create Tables
        db.drop_all()
        db.create_all()
        
        # Step 2: Insert Dummy Users (Includes Student!)
        student = User(username='student', password='studentpassword', role='student')
        admin = User(username='admin_hitam', password='adminpassword', role='admin')
        organizer = User(username='cs_club', password='clubpassword', role='organizer')
        
        db.session.add_all([student, admin, organizer])
        db.session.commit()
        print("Dummy users (Student, Admin, Organizer) created.") # CONFIRMATION LINE
        
        organizer_id = organizer.id
        student_id = student.id

        # Step 3: Insert Venues and Events... (rest of the logic)

        venue1 = Venue(name='HITAM Auditorium', capacity=500)
        venue2 = Venue(name='Seminar Hall 1', capacity=100)
        
        db.session.add_all([venue1, venue2])
        db.session.commit()
        
        auditorium_id = venue1.id
        seminar_id = venue2.id

        now = datetime.now()
        event_done = Event(
            title='Annual Sports Day',
            description='The grand sports event of the year.',
            start_datetime=now - timedelta(days=2),
            end_datetime=now - timedelta(hours=1),
            venue_id=auditorium_id,
            organizer_id=organizer_id,
            status='approved'
        )

        event_ongoing = Event(
            title='Code-a-Thon Challenge',
            description='24-hour coding challenge for all branches.',
            start_datetime=now - timedelta(hours=1),
            end_datetime=now + timedelta(hours=2),
            venue_id=seminar_id,
            organizer_id=organizer_id,
            status='approved'
        )
        
        event_upcoming = Event(
            title='Mega Cultural Fest',
            description='Talent showcase and cultural events.',
            start_datetime=now + timedelta(days=5, hours=10),
            end_datetime=now + timedelta(days=6),
            venue_id=auditorium_id,
            organizer_id=organizer_id,
            status='approved'
        )
        
        event_pending = Event(
            title='Photography Workshop (Pending)',
            description='A workshop on digital photography basics.',
            start_datetime=now + timedelta(days=10),
            end_datetime=now + timedelta(days=10, hours=4),
            venue_id=seminar_id,
            organizer_id=organizer_id,
            status='pending'
        )

        db.session.add_all([event_done, event_ongoing, event_upcoming, event_pending])
        db.session.commit()
        
        # 5. Pre-register and leave feedback for demonstration
        try:
            dummy_reg = EventRegistration(event_id=event_ongoing.id, user_id=student_id)
            db.session.add(dummy_reg)
            
            dummy_feedback = Feedback(
                event_id=event_done.id,
                user_id=student_id,
                rating=5,
                comments="Great event, loved the organization!"
            )
            db.session.add(dummy_feedback)
            
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            
        print("\nInitialization complete. Run 'python app.py' now.")

if __name__ == '__main__':
    init_db()