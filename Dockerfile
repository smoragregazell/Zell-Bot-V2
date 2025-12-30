# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Create necessary directories
RUN mkdir -p logs Data knowledgebase Prompts Tools utils endpoints

# Expose the port the app runs on
EXPOSE 5050

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=5050

# Run the application
CMD ["python", "main.py"]
