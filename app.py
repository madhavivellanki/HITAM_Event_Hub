from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps
from sqlalchemy.exc import IntegrityError

# --- Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key_for_hitam' 
# app.py (Replace the line)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db' # Use the local SQLite file directly
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Models ---
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


# --- Utility Functions ---

def get_event_status(event):
    """Dynamically determines the event status based on current time."""
    now = datetime.now()
    if event.start_datetime <= now and event.end_datetime >= now:
        return 'Ongoing'
    elif event.start_datetime > now:
        return 'Upcoming'
    else: 
        return 'Done'

def login_required(f):
    """Decorator to require login for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    """Decorator to require specific roles."""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if session.get('role') not in roles:
                flash(f'Access denied. Required roles: {", ".join(roles)}', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# --- Routes ---

@app.route('/')
def index():
    """Student View: Secure Login, Browse Events, Registration/Feedback Status."""
    approved_events = Event.query.filter_by(status='approved').order_by(Event.start_datetime).all()
    user_id = session.get('user_id')
    
    events_with_status = []
    registered_event_ids = []
    feedback_event_ids = []
    
    if user_id:
        registered_event_ids = [reg.event_id for reg in EventRegistration.query.filter_by(user_id=user_id).all()]
        feedback_event_ids = [fb.event_id for fb in Feedback.query.filter_by(user_id=user_id).all()]

    for event in approved_events:
        event.dynamic_status = get_event_status(event)
        event.is_registered = event.id in registered_event_ids
        event.has_feedback = event.id in feedback_event_ids
        events_with_status.append(event)

    ongoing = [e for e in events_with_status if e.dynamic_status == 'Ongoing']
    upcoming = [e for e in events_with_status if e.dynamic_status == 'Upcoming']
    done = [e for e in events_with_status if e.dynamic_status == 'Done']

    return render_template('index.html', ongoing=ongoing, upcoming=upcoming, done=done)

@app.route('/register/<int:event_id>', methods=['POST'])
@login_required
def register_event(event_id):
    """Student Function: Register for events."""
    if session.get('role') in ['organizer', 'admin']:
        flash('Organizers and Admins cannot register for events.', 'danger')
        return redirect(url_for('index'))

    event = Event.query.get_or_404(event_id)
    user_id = session['user_id']

    if get_event_status(event) == 'Done':
        flash(f'Cannot register. "{event.title}" is already finished.', 'danger')
        return redirect(url_for('index'))

    try:
        new_registration = EventRegistration(event_id=event_id, user_id=user_id)
        db.session.add(new_registration)
        db.session.commit()
        flash(f'Successfully registered for: {event.title}! 🎉', 'success')
    except IntegrityError:
        db.session.rollback()
        flash(f'You are already registered for: {event.title}.', 'warning')
    except Exception:
        db.session.rollback()
        flash('An unexpected error occurred during registration.', 'danger') 

    return redirect(url_for('index'))

@app.route('/feedback/<int:event_id>', methods=['GET', 'POST'])
@role_required(roles=['student'])
def submit_feedback(event_id):
    """Student Function: Provide Feedback."""
    event = Event.query.get_or_404(event_id)
    user_id = session['user_id']
    
    if get_event_status(event) != 'Done':
        flash('You can only leave feedback for events that are finished.', 'danger')
        return redirect(url_for('index'))

    existing_feedback = Feedback.query.filter_by(event_id=event_id, user_id=user_id).first()
    if existing_feedback and request.method == 'GET':
        flash('You have already submitted feedback for this event.', 'warning')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            rating = int(request.form.get('rating'))
            comments = request.form.get('comments')

            if 1 <= rating <= 5:
                new_feedback = Feedback(event_id=event_id, user_id=user_id, rating=rating, comments=comments)
                db.session.add(new_feedback)
                db.session.commit()
                flash('Thank you for your feedback! It has been submitted.', 'success')
                return redirect(url_for('index'))
            else:
                flash('Rating must be between 1 and 5.', 'danger')
        except Exception:
            db.session.rollback()
            flash('Error submitting feedback. Please try again.', 'danger')

    return render_template('submit_feedback.html', event=event, existing_feedback=existing_feedback)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Students: Secure Login."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'] 
        user = User.query.filter_by(username=username, password=password).first()
        
        if user:
            session['user_id'] = user.id
            session['role'] = user.role
            flash(f'Logged in as {user.role.capitalize()}', 'success')
            
            if user.role == 'student':
                return redirect(url_for('index'))
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
            return render_template('login.html')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Handles User Logout."""
    session.pop('user_id', None)
    session.pop('role', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard Interface for Organizers and Admins."""
    role = session['role']
    user_id = session['user_id']
    
    events = []
    
    if role == 'organizer':
        events = Event.query.filter_by(organizer_id=user_id).all()
    else: 
        events = Event.query.all()
    
    for event in events:
        event.dynamic_status = get_event_status(event)
        venue = Venue.query.get(event.venue_id)
        event.venue_name = venue.name if venue else 'N/A'

    return render_template('organizer_dashboard.html', events=events, role=role)

# --- STUDENT FUNCTION: View Registered Events ---
@app.route('/my_registrations')
@role_required(roles=['student'])
def my_registrations():
    """Student Function: View their registered events."""
    user_id = session['user_id']
    registrations = EventRegistration.query.filter_by(user_id=user_id).all()
    
    registered_events = []
    for reg in registrations:
        event = Event.query.get(reg.event_id)
        if event:
            event.dynamic_status = get_event_status(event)
            event.registration_date = reg.registration_time.strftime('%b %d, %Y')
            
            event.has_feedback = Feedback.query.filter_by(event_id=event.id, user_id=user_id).first() is not None
            registered_events.append(event)

    return render_template('my_registrations.html', events=registered_events)

# --- ORGANIZER/ADMIN FUNCTION: Edit Event ---
@app.route('/edit_event/<int:event_id>', methods=['GET', 'POST'])
@role_required(roles=['organizer', 'admin'])
def edit_event(event_id):
    event = Event.query.get_or_404(event_id)
    venues = Venue.query.all()

    if session.get('role') == 'organizer' and event.organizer_id != session.get('user_id'):
        flash('You are not authorized to edit this event.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        try:
            event.title = request.form['title']
            event.description = request.form['description']
            event.venue_id = request.form['venue_id']
            
            start_str = f"{request.form['start_date']} {request.form['start_time']}"
            end_str = f"{request.form['end_date']} {request.form['end_time']}"
            
            event.start_datetime = datetime.strptime(start_str, '%Y-%m-%d %H:%M')
            event.end_datetime = datetime.strptime(end_str, '%Y-%m-%d %H:%M')
            event.status = request.form['status'] 

            db.session.commit()
            flash(f'Event "{event.title}" updated successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f'Error updating event: {e}', 'danger')
            db.session.rollback()
            return redirect(url_for('edit_event', event_id=event_id))

    return render_template('edit_event.html', event=event, venues=venues)


# --- Run the application ---
if __name__ == '__main__':
    app.run(debug=True)