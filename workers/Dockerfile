# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /worker_app

# Add project root to PYTHONPATH to allow imports like `from workers.config`
# This assumes the Docker build context is the project root `bruteforce_framework/`
# and we copy the 'workers' and 'common' directories.
ENV PYTHONPATH "${PYTHONPATH}:/app_root"

# Copy only necessary directories: 'workers' and 'common' (if it exists and is needed by worker)
# We place them inside a directory called /app_root in the container.
COPY ./workers /app_root/workers
COPY ./common /app_root/common # Assuming 'common' might be used by worker later

# Change working directory to where the worker code is, for convenience
WORKDIR /app_root/workers

# Install any needed packages specified in requirements_worker.txt
# requirements_worker.txt is expected to be inside the 'workers' directory
RUN pip install --no-cache-dir -r requirements_worker.txt


# Command to run the worker script
# Using -u for unbuffered output, good for logging
CMD ["python", "-u", "worker.py"]
