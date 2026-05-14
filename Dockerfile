FROM python:3.12-slim
WORKDIR /app
# Instala as bibliotecas que o seu projeto usa
RUN pip install fastapi uvicorn google-generativeai sqlalchemy pymysql python-multipart
# Copia todos os seus arquivos (main.py, etc) para dentro do Docker
COPY . .
# Porta que o FastAPI usa
EXPOSE 8000
# Comando para rodar o projeto
CMD ["python", "main.py"]