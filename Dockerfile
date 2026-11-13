# Bausteinbrücke und nachgebildete Gegenstellen (Python, ohne Datenbank)
FROM python:3.13-slim
RUN pip install --no-cache-dir pyyaml==6.0.3 rdflib==7.5.0 pyshacl==0.30.1 jsonschema==4.25.1 pytest==8.4.2
WORKDIR /app
COPY . /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["python", "-m", "pytest", "-q"]
