# Project Title

A brief description of what this project does and who it's for.

## Features

- **User Authentication:** Secure user registration and login system.
- **Role-Based Access:** Distinct roles for 'teacher' and 'student' with different permissions.
- **Class Management:** Teachers can create, edit, and manage classes.
- **Assignment Creation:** Teachers can create assignments with multiple question types (single response, multiple choice).
- **Automated Grading:** Assignments are automatically graded upon submission.
- **Student Dashboard:** Students can view their enrolled classes and assignments.
- **Teacher Dashboard:** Teachers can track student progress and manage their classes and assignments.

## Technologies Used

- **Backend:** Flask, Python
- **Database:** MongoDB (with Flask-PyMongo)
- **Authentication:** Flask-Login, Flask-Bcrypt
- **Frontend:** HTML, CSS (with basic templates)

## Setup and Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/your-repository.git
   cd your-repository
   ```

2. **Create a virtual environment and activate it:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   - Create a `.env` file in the root directory.
   - Add the following variables:
     ```
     SECRET_KEY='a_very_secret_key'
     MONGO_URI='mongodb://localhost:27017/your_database_name'
     ```

5. **Run the application:**
   ```bash
   flask run
   ```

## Usage

1. **Register a new user:**
   - Navigate to `/register` to create a new 'teacher' or 'student' account.

2. **Log in:**
   - Navigate to `/login` to access your dashboard.

3. **Teacher Actions:**
   - Create a new class from the dashboard.
   - Create a new assignment.
   - Assign the assignment to a class.
   - View student submissions and track progress.

4. **Student Actions:**
   - Register for an available class.
   - Take an assigned test.
   - View your score and submission summary.
