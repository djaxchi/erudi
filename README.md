✅ Prérequis

Node.js >= 18

npm

Docker

📦 Installation

1. Cloner le projet

git clone https://github.com/votre-utilisateur/smarter.git
cd smarter
rqe: SMARTER est l'ancien nom... C'est Erudi maintenant
2. Installer les dépendances de l'interface

cd frontend
npm install

🧠 Lancer le backend FastAPI

1. Construire l'image Docker du backend

cd backend
docker build -t smarter-backend .

2. Lancer le conteneur

<!-- docker run -p 8000:8000 smarter-backend -->
<!-- VERSION POWERSHELL WINDOWS !! -->
docker run -v ${PWD}\data:/app/data -p 8000:8000 smarter-backend

Le backend est maintenant disponible sur http://localhost:8000.

💻 Lancer l'application Electron avec live-reload

Dans un terminal séparé :

cd frontend
npm start

Cela démarre l'application Electron en mode développement, avec rechargement automatique à chaque modification.






## SI UTILISATION SANS DOCKER !!!!!!!
# Windows
dans le terminal backend faire :
cd backend
python -m venv venv
./venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Mac
dans le terminal backend faire :
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

reste a faire mnt:
systeme prompt dynamique en fonction de model taille
tune title
starred messages (tester pertinence debut/fin prompt)
opti KB (chunk plus petit)
Clean code base

plus tard: 
user story kb
actualisation info apres telechargement



