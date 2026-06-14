FROM python:3.11-slim

WORKDIR /app

# Instala as dependencias primeiro para aproveitar o cache de camadas do Docker.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o codigo da aplicacao (e os testes).
COPY . .

EXPOSE 8000

# Sobe o servidor FastAPI na porta fixa 8000.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
