# Distributed Task Manager (DTM)

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/votrecompte/distributed-task-manager/badge)](https://securityscorecards.dev/viewer/?uri=github.com/votrecompte/distributed-task-manager)

Un système de gestion de tâches distribué minimaliste pour exécuter des commandes shell sur des workers. Parfait pour le traitement parallèle et les démonstrations éducatives.


## Cas d'Usage
- Parfait pour les laboratoires de sécurité offensive (tests légitimes)
- Traitement parallèle de données
- Démonstration des concepts de systèmes distribués
- Automatisation de workflows shell

## Fonctionnalités Clés
✅ Exécution distribuée de commandes shell  
✅ Interface web de monitoring  
✅ Architecture push/pull flexible  
✅ Gestion automatique des workers défaillants  
✅ Sortie en temps réel des tâches  

## 🚀 Démarrage Rapide

### Prérequis
- Python 3.9+
- Bash (pour l'exécution des commandes)

### Installation
```bash
pip install git+https://github.com/votrecompte/distributed-task-manager.git
```

### Lancement
```bash
# Démarrer le serveur
dtm-server --port 8000

# Dans un autre terminal - Démarrer un worker
dtm-worker --manager http://localhost:8000
```

### Utilisation Basique
```bash
# Soumettre une tâche
curl -X POST "http://localhost:8000/submit_task?command=for%20i%20in%20{1..5}%3B%20do%20echo%20%22Step%20%24i%22%3B%20sleep%201%3B%20done"

# Voir les résultats
curl "http://localhost:8000/tasks" | jq
```

## Architecture
```
graph TD
    Client -->|Submit| Manager
    Manager -->|Push Tasks| Worker1
    Manager -->|Push Tasks| Worker2
    Worker -->|Heartbeats| Manager
```

## Contribuer
Les contributions sont bienvenues ! Voir :

- Guide de [contribution](CONTRIBUTING.md)
- [Gestion sémantique de version](https://semver.org/lang/fr/)
- Code de conduite

## License
AGPL - Voir [LICENSE](LICENSE)