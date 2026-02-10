# 1. Basis-Image wählen
FROM python:3.11-slim

# 2. Arbeitsverzeichnis im Container festlegen
WORKDIR /app

# 3. System-Abhängigkeiten installieren (wichtig für spätere PDF-Verarbeitung)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 4. requirements.txt kopieren und Pakete installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Den restlichen Code des Backends kopieren
COPY . .

# 6. Port für FastAPI (Standard 8000)
EXPOSE 8000

# 7. Startbefehl: FastAPI mit Uvicorn starten
# --host 0.0.0.0 ist zwingend erforderlich für Docker!
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
