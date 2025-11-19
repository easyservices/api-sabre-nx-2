# Use an official Python base image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install dependencies first (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Ensure Python can find the nested src package
ENV PYTHONPATH=/app/app

# Expose default port (actual port can be overridden via config/env)
EXPOSE 1265

# Default command delegates to the module so it can read config/env values
CMD ["python", "-m", "app.fastapi4nx"]
