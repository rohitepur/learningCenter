# =================================================================
# Stage 1: Builder - Install dependencies into a virtual environment
# =================================================================
FROM python:3.10-slim AS builder

# Set working directory
WORKDIR /app

# Create a virtual environment to isolate our dependencies
RUN python -m venv /opt/venv
# Add the venv to the PATH
ENV PATH="/opt/venv/bin:$PATH"

# Copy only the requirements file to leverage Docker's layer caching.
# This step is only re-run if requirements.txt changes.
COPY requirements.txt .

# Install the Python dependencies into the virtual environment
RUN pip install --no-cache-dir -r requirements.txt


# =================================================================
# Stage 2: Final Image - Create a lean and secure production image
# =================================================================
FROM python:3.10-slim

# Create a non-root user for security
RUN useradd --create-home appuser
USER appuser

# Set working directory for the new user
WORKDIR /home/appuser/app

# Copy the virtual environment with installed packages from the builder stage
COPY --chown=appuser:appuser --from=builder /opt/venv /opt/venv

# Copy the application code into the container
# The .dockerignore file will prevent unnecessary files from being copied
COPY --chown=appuser:appuser . .

# Make the virtual environment's binaries accessible
ENV PATH="/opt/venv/bin:$PATH"

EXPOSE 8000

# Define the command to run the application using Gunicorn
# The number of workers is a suggestion. Adjust based on your server's CPU cores (2-4 per core is a common rule of thumb).
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:8000", "app:app"]