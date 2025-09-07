import os
from flask_pymongo import PyMongo
from pymongo import ASCENDING
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize PyMongo
mongo = PyMongo()

# Registration status options used throughout the UI & CSV
ALLOWED_STATUSES = {"pending", "registered", "waitlisted", "dropped"}

def init_app(app):
    """
    Initialize the database with the Flask app.
    This function sets up the MongoDB connection and ensures indexes are created.
    """
    # Configure the app with MongoDB URI
    app.config['MONGO_URI'] = os.environ.get('MONGO_URI')

    # Validate essential configurations
    if not app.config['MONGO_URI']:
        raise RuntimeError("MONGO_URI not set. Please check your .env file.")

    # Initialize PyMongo with the app
    mongo.init_app(app)

    # For debugging purposes, print the URI to the console on startup
    print(f"INFO: Connecting to MongoDB with URI: {app.config.get('MONGO_URI')}")

    # Initialize database indexes
    with app.app_context():
        init_indexes()

def init_indexes():
    """
    Create necessary indexes for the MongoDB collections.
    """
    # Students collection indexes
    mongo.db.students.create_index([("student_id", ASCENDING)], unique=True, sparse=True)
    mongo.db.students.create_index([("email", ASCENDING)], unique=True, sparse=True)
    mongo.db.students.create_index([("last_name", ASCENDING), ("first_name", ASCENDING)])
    # Optional: Add indexes for parent names/phones if needed
    # mongo.db.students.create_index([("dad_name", ASCENDING)])
    # mongo.db.students.create_index([("mom_name", ASCENDING)])

def get_db():
    """
    Returns the MongoDB database instance.
    """
    return mongo.db