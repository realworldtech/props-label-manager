FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (cups-client provides lp command for CUPS printing)
RUN apt-get update && apt-get install -y --no-install-recommends cups-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Collect static files
RUN cd src && python manage.py collectstatic --noinput --clear 2>/dev/null || true

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

WORKDIR /app/src

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "printclient.wsgi:application"]
