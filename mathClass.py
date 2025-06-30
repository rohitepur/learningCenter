from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from bson.objectid import ObjectId
from dotenv import load_dotenv
from datetime import datetime
import os

load_dotenv() # Load environment variables from .env file

app = Flask(__name__)
# It's best practice to load sensitive data from environment variables.
# The second argument to .get() is a default value, useful for local development.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['MONGO_URI'] = os.environ.get('MONGO_URI')

# --- Configuration Validation ---
# Ensure essential variables are set, otherwise raise a clear error.
if not app.config['MONGO_URI']:
    raise RuntimeError("MONGO_URI not set. Please check your .env file.")
if not app.config['SECRET_KEY']:
    raise RuntimeError("SECRET_KEY not set. Please check your .env file.")

# For debugging purposes, print the URI to the console on startup.
# This helps confirm that the .env file is being loaded correctly.
# Remember to remove this in a production environment.
print(f"INFO: Connecting to MongoDB with URI: {app.config.get('MONGO_URI')}")

mongo = PyMongo(app)

# --- Database Connection Validation ---
# Add a check to ensure a database connection was actually established.
# mongo.db will be None if the MONGO_URI is missing a database name.
if mongo.db is None:
    raise RuntimeError("Failed to connect to the database. "
                       "Please check that your MONGO_URI in the .env file "
                       "includes a database name, e.g., 'mongodb://localhost:27017/mydatabase'.")
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ---------------------------- User Loader ----------------------------
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.name = user_data['name']
        self.email = user_data['email']
        self.role = user_data['role']

@login_manager.user_loader
def load_user(user_id):
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    return User(user) if user else None

# ---------------------------- Routes ----------------------------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Use .get() to safely access form data and prevent crashes
        name = request.form.get('name')
        email = request.form.get('email')
        password_from_form = request.form.get('password')
        role = request.form.get('role')

        if not all([name, email, password_from_form, role]):
            # In a real app, you'd flash a message: "All fields are required."
            flash('All fields are required.', 'error')
            return redirect(url_for('register'))

        # Check if user already exists to prevent duplicates
        if mongo.db.users.find_one({'email': email}):
            # In a real app, you'd flash a message to the user here
            flash('User already exists.', 'error')
            return redirect(url_for('register'))

        mongo.db.users.insert_one({
            'name': name,
            'email': email,
            'password_hash': bcrypt.generate_password_hash(password_from_form).decode('utf-8'),
            'role': role,
            'enrolled_classes': []
        })
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Use .get() to safely access form data
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            # In a real app, you'd flash a message: "Email and password are required."
            flash('Email and password are required.', 'error')
            return redirect(url_for('login'))

        user_data = mongo.db.users.find_one({'email': email})
        if user_data and bcrypt.check_password_hash(user_data['password_hash'], password):
            login_user(User(user_data))
            return redirect(url_for('dashboard'))
        
        # If login fails, flash an error message to the user.
        flash('Invalid email or password. Please try again.', 'error')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    tests = []
    assignments = []
    classes = []
    registrations = []
    student_assignments = []
    submissions_map = {}

    # If the user is a teacher, find all tests they have created.
    if current_user.role == 'teacher':
        assignments = list(mongo.db.assignments.find({'created_by': ObjectId(current_user.id)}))
        classes = list(mongo.db.classes.find({'created_by': ObjectId(current_user.id)}))
    # If the user is a student, find their class registrations.
    elif current_user.role == 'student':
        registrations = list(mongo.db.class_registrations.find({'student_id': ObjectId(current_user.id)}))
        # Safely get class_id, only for documents that have it.
        registered_class_ids = [reg['class_id'] for reg in registrations if 'class_id' in reg]
        
        # Find assignments for the classes the student is in
        student_assignments = list(mongo.db.assignments.find({'assigned_to_classes': {'$in': registered_class_ids}}))
        
        # Find which assignments the student has already submitted
        submissions = list(mongo.db.submissions.find({'student_id': ObjectId(current_user.id)}))
        # Create a map of assignment_id -> submission_id for linking to results
        submissions_map = {str(sub['assignment_id']): str(sub['_id']) for sub in submissions}

    return render_template('dashboard.html', assignments=assignments, registrations=registrations, classes=classes, student_assignments=student_assignments, submissions_map=submissions_map)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ---------------------------- Assignment Creation ----------------------------
@app.route('/create_assignment', methods=['GET', 'POST'])
@login_required
def create_assignment():
    # Authorization check: Only teachers can create assignments.
    if current_user.role != 'teacher':
        abort(403)

    if request.method == 'POST':
        title = request.form.get('title')
        question_texts = request.form.getlist('question_text')
        question_types = request.form.getlist('question_type')

        if not title or not question_texts:
            flash('An assignment must have a title and at least one question.', 'error')
            return redirect(url_for('create_assignment'))

        questions = []
        for i, text in enumerate(question_texts):
            q_type = question_types[i]
            question_data = {"text": text, "type": q_type}

            if q_type == 'single_response':
                question_data['answer'] = request.form.get(f'answer_{i}')
            elif q_type == 'multiple_choice':
                # Get all options for the current question
                options = request.form.getlist(f'option_{i}')
                correct_option_index = request.form.get(f'correct_option_{i}')
                
                question_data['options'] = options
                # Store the index of the correct answer
                question_data['answer'] = int(correct_option_index) if correct_option_index else None
            
            questions.append(question_data)

        mongo.db.assignments.insert_one({
            'title': title,
            'questions': questions,
            'created_by': ObjectId(current_user.id) # Track who created the test
        })
        flash('Assignment created successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('create_assignment.html')

# ---------------------------- Assign Assignment (Teacher) ----------------------------
@app.route('/assign_assignment/<assignment_id>', methods=['GET', 'POST'])
@login_required
def assign_assignment(assignment_id):
    if current_user.role != 'teacher':
        abort(403)

    assignment = mongo.db.assignments.find_one_or_404({'_id': ObjectId(assignment_id)})
    # Security check: ensure the teacher owns this assignment
    if assignment['created_by'] != ObjectId(current_user.id):
        abort(403)

    if request.method == 'POST':
        class_ids = request.form.getlist('class_ids')
        class_object_ids = [ObjectId(cid) for cid in class_ids]

        mongo.db.assignments.update_one(
            {'_id': ObjectId(assignment_id)},
            {'$set': {'assigned_to_classes': class_object_ids}}
        )

        flash(f'Assignment "{assignment["title"]}" has been assigned.', 'success')
        return redirect(url_for('dashboard'))

    # GET request
    teacher_classes = list(mongo.db.classes.find({
        'created_by': ObjectId(current_user.id),
        'is_active': True
    }))
    return render_template('assign_assignment.html', assignment=assignment, classes=teacher_classes)


# ---------------------------- Class Creation (Teacher) ----------------------------
@app.route('/create_class', methods=['GET', 'POST'])
@login_required
def create_class():
    # Authorization: Only teachers can create classes.
    if current_user.role != 'teacher':
        abort(403)

    if request.method == 'POST':
        class_name = request.form.get('class_name')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        fee = request.form.get('fee')
        # Checkbox value will be 'on' if checked, None otherwise.
        is_active = 'is_active' in request.form

        if not all([class_name, start_date, end_date, fee]):
            flash('Please fill out all fields.', 'error')
            return redirect(url_for('create_class'))

        mongo.db.classes.insert_one({
            'name': class_name,
            'start_date': start_date,
            'end_date': end_date,
            'fee': fee,
            'is_active': is_active,
            'created_by': ObjectId(current_user.id),
            'created_at': datetime.utcnow()
        })

        flash(f'Class "{class_name}" created successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('create_class.html')

# ---------------------------- Class Registration ----------------------------
@app.route('/register_class', methods=['GET', 'POST'])
@login_required
def register_class():
    # Authorization: Only students can register for a class.
    if current_user.role != 'student':
        abort(403)

    if request.method == 'POST':
        student_name = request.form.get('student_name')
        contact_email = request.form.get('contact_email')
        contact_phone = request.form.get('contact_phone') # Optional
        class_id = request.form.get('class_id')

        # Validation for mandatory fields
        if not all([student_name, contact_email, class_id]):
            flash('Please fill out all mandatory fields.', 'error')
            return redirect(url_for('register_class'))

        # Find the class to get its name for storage
        class_obj = mongo.db.classes.find_one_or_404({'_id': ObjectId(class_id)})

        # Prevent duplicate registration
        existing_reg = mongo.db.class_registrations.find_one({'student_id': ObjectId(current_user.id), 'class_id': ObjectId(class_id)})
        if existing_reg:
            flash(f'You are already registered for {class_obj["name"]}.', 'warning')
            return redirect(url_for('dashboard'))

        mongo.db.class_registrations.insert_one({
            'student_id': ObjectId(current_user.id),
            'class_id': ObjectId(class_id),
            'student_name': student_name,
            'contact_email': contact_email,
            'contact_phone': contact_phone,
            'class_name': class_obj['name'], # Store name for easy display
            'registration_date': datetime.utcnow()
        })

        flash(f'You have successfully registered for {class_obj["name"]}!', 'success')
        return redirect(url_for('dashboard'))

    # GET request: Fetch only active classes to display in the form.
    active_classes = list(mongo.db.classes.find({'is_active': True}))
    return render_template('register_class.html', active_classes=active_classes)

# ---------------------------- Take Assignment (Student) ----------------------------
@app.route('/take_assignment/<assignment_id>', methods=['GET', 'POST'])
@login_required
def take_assignment(assignment_id):
    if current_user.role != 'student':
        abort(403)

    assignment = mongo.db.assignments.find_one_or_404({'_id': ObjectId(assignment_id)})

    # Authorization: Check if student is in a class this is assigned to
    registrations = list(mongo.db.class_registrations.find({'student_id': ObjectId(current_user.id)}))
    # Safely get class_id, only for documents that have it.
    registered_class_ids = {reg['class_id'] for reg in registrations if 'class_id' in reg}
    assigned_class_ids = set(assignment.get('assigned_to_classes', []))

    if not registered_class_ids.intersection(assigned_class_ids):
        flash('You are not authorized to take this assignment.', 'error')
        return redirect(url_for('dashboard'))

    # Prevent re-submission
    existing_submission = mongo.db.submissions.find_one({'student_id': ObjectId(current_user.id), 'assignment_id': ObjectId(assignment_id)})
    if existing_submission:
        flash('You have already completed this assignment.', 'warning')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        answers = []
        score = 0
        total_questions = len(assignment['questions'])

        for i, question in enumerate(assignment['questions']):
            student_answer_raw = request.form.get(f'answer_{i}')
            is_correct = False
            correct_answer = question.get('answer')

            if question['type'] == 'single_response':
                # Simple case-insensitive, whitespace-trimmed comparison
                if student_answer_raw and isinstance(correct_answer, str):
                    is_correct = student_answer_raw.strip().lower() == correct_answer.strip().lower()
            
            elif question['type'] == 'multiple_choice':
                # Compare the submitted index with the correct index
                if student_answer_raw is not None:
                    try:
                        is_correct = int(student_answer_raw) == correct_answer
                    except (ValueError, TypeError):
                        is_correct = False # Handle cases where conversion fails
            
            if is_correct:
                score += 1

            answers.append({
                'question_text': question['text'], 
                'student_answer': student_answer_raw,
                'is_correct': is_correct
            })

        submission_doc = {
            'assignment_id': ObjectId(assignment_id),
            'student_id': ObjectId(current_user.id),
            'submitted_at': datetime.utcnow(),
            'answers': answers,
            'score': score,
            'total_questions': total_questions
        }
        result = mongo.db.submissions.insert_one(submission_doc)

        flash('Your assignment has been submitted successfully!', 'success')
        return redirect(url_for('submission_summary', submission_id=result.inserted_id))

    return render_template('take_assignment.html', assignment=assignment)

@app.route('/submission_summary/<submission_id>')
@login_required
def submission_summary(submission_id):
    submission = mongo.db.submissions.find_one_or_404({'_id': ObjectId(submission_id)})
    # Fetch the original assignment to get all question data and correct answers
    assignment = mongo.db.assignments.find_one_or_404({'_id': submission['assignment_id']})

    # --- Enhanced Security Check ---
    # Allow access if the user is the student who made the submission
    is_student_owner = submission['student_id'] == ObjectId(current_user.id)
    # OR if the user is the teacher who created the assignment
    is_teacher_owner = False
    if current_user.role == 'teacher':
        is_teacher_owner = assignment['created_by'] == ObjectId(current_user.id)

    if not is_student_owner and not is_teacher_owner:
        abort(403)

    return render_template('submission_summary.html', submission=submission, assignment=assignment)

@app.route('/assignment_tracking')
@login_required
def assignment_tracking():
    if current_user.role != 'teacher':
        abort(403)

    teacher_classes = list(mongo.db.classes.find({'created_by': ObjectId(current_user.id)}))
    
    tracking_data = []
    for a_class in teacher_classes:
        class_id = a_class['_id']
        
        # Get all assignments for this class
        assignments_in_class = list(mongo.db.assignments.find({'assigned_to_classes': class_id}))
        
        # Get all students registered in this class
        registrations = list(mongo.db.class_registrations.find({'class_id': class_id}))
        student_ids = [reg['student_id'] for reg in registrations]
        students = {str(s['_id']): s['name'] for s in mongo.db.users.find({'_id': {'$in': student_ids}})}
        
        # Get all submissions for these students and assignments
        assignment_ids = [a['_id'] for a in assignments_in_class]
        submissions = list(mongo.db.submissions.find({'student_id': {'$in': student_ids}, 'assignment_id': {'$in': assignment_ids}}))
        
        # Structure submissions for easy lookup in the template
        submissions_map = {(str(s['student_id']), str(s['assignment_id'])): s for s in submissions}
        
        tracking_data.append({'class': a_class, 'assignments': assignments_in_class, 'students': students, 'submissions': submissions_map})

    return render_template('assignment_tracking.html', tracking_data=tracking_data)
if __name__ == '__main__':
    app.run(debug=True)
