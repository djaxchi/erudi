✅ Prérequis

Node.js >= 18

npm

Docker

📦 Installation

1. Cloner le projet

git clone https://github.com/votre-utilisateur/smarter.git
cd smarter

2. Installer les dépendances de l'interface

cd frontend
npm install

🧠 Lancer le backend FastAPI

1. Construire l'image Docker du backend

cd backend
docker build -t smarter-backend .

2. Lancer le conteneur

docker run -p 8000:8000 smarter-backend
docker run --gpus all -p 8000:8000 smarter-backend


Le backend est maintenant disponible sur http://localhost:8000.

💻 Lancer l'application Electron avec live-reload

Dans un terminal séparé :

cd frontend
npm start

Cela démarre l'application Electron en mode développement, avec rechargement automatique à chaque modification.