# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Install ffmpeg and other dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port the app will run on
EXPOSE 5000

# Define environment variable to tell Flask it’s in production mode
ENV FLASK_ENV=production
ENV YT_COOKIE_BASE64=${YT_COOKIE_BASE64}

# Run the app
CMD ["python", "app.py"]
