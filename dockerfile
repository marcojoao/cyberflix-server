# Use the official Python image as base
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt /app

# Install any dependencies specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . /app

# Set environmental variables from .env file
ENV $(cat /app/.env | grep -v ^# | xargs)

# Expose port 80 to the outside world
EXPOSE 8000

# Command to run your FastAPI server using Gunicorn
CMD ["gunicorn", "run:app", "--timeout", "600", "-b", "0.0.0.0:8000", "--workers", "4"]
