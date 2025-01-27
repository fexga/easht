# Use the official Python base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy requirements file first to leverage Docker caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY . .

# Set environment variables (if needed)
ENV MONGO_URI="mongo://mongo:27017/hyperopt/jobs"

# Specify the entry point for the container
CMD ["python", "train.py"]
