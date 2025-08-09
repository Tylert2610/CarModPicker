# Stage 1: Build stage - for installing dependencies
FROM python:3.12-slim AS builder
WORKDIR /opt/build
COPY requirements.txt .
RUN python -m venv /opt/venv
RUN /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Stage 2: Final stage - for running the application
FROM python:3.12-slim
WORKDIR /  
RUN addgroup --system appuser && adduser --system --ingroup appuser appuser
COPY --from=builder /opt/venv /opt/venv
COPY app/ /app/app/
# Copy alembic files for migrations
COPY alembic.ini /app/alembic.ini
COPY alembic/ /app/alembic/
ENV PATH="/opt/venv/bin:$PATH"
RUN chown -R appuser:appuser /app /opt/venv
USER appuser
WORKDIR /app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 