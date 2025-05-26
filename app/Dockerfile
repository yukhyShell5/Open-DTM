# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
# Path is relative to the build context (project root)
COPY ./app/requirements.txt /app/requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
# This copies the content of the 'app' directory from the build context (project root)
# into the '/app' directory in the container (which is the WORKDIR).
COPY ./app/ /app/

# Expose port 8000 for Uvicorn
EXPOSE 8000

# Command to run the application using Uvicorn
# Bind to 0.0.0.0 to allow external connections to the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
