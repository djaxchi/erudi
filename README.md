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
npm start


🧠 Lancer le backend FastAPI

cd backend
python -m venv venv
./venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload


Pour Builder l'appli :

Rester dans la racine (erudi/)

.\backend\venv\Scripts\activate

pyinstaller --name backend --clean --onedir --console --paths=backend --add-data "backend/data;data" --add-data "backend/app/prompting/jinja_templates;jinja" --hidden-import jinja2 --hidden-import sqlalchemy --hidden-import erudi_secrets --add-data "backend/erudi_secrets.py;." run.py

Attendre la fin du package backend, puis dans un autre terminal et en s'assurant de ne pas utiliser les fichiers du projet (fermer vscode sinon crash) :

cd frontend
npm run make

