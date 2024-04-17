# Utilisez une image de base légère de Python
FROM --platform=linux/amd64 python:3.12-alpine

# Définissez le répertoire de travail dans le conteneur
WORKDIR /app

# Copiez les fichiers nécessaires dans le conteneur
COPY api/app.py .
COPY requirements.txt .
COPY .env .

# Installez les dépendances
RUN pip install --no-cache-dir -r requirements.txt

# Exposez le port sur lequel l'application va s'exécuter
EXPOSE 5000/tcp

# Commande pour exécuter l'application
CMD ["python", "app.py"]
