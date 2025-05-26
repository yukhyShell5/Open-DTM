# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container (initial)
WORKDIR /worker_app

# Add project root to PYTHONPATH to allow imports from 'common' and 'workers' packages
ENV PYTHONPATH "${PYTHONPATH}:/app_root"

# Copy necessary application code from the build context (project root)
# into the /app_root directory in the container.
COPY ./workers/ /app_root/workers/
COPY ./common/ /app_root/common/

# Set the final working directory
WORKDIR /app_root/workers

# Install any needed packages specified in requirements_worker.txt
# (requirements_worker.txt is expected to be inside the 'workers' directory)
RUN pip install --no-cache-dir -r requirements_worker.txt

# Command to run the worker script
# Using -u for unbuffered output, good for logging
CMD ["python", "-u", "worker.py"]
