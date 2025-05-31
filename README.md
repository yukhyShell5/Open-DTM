# Open DTM (Distributed Task Manager)

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL](https://img.shields.io/badge/license-AGPL--v3-green)](https://opensource.org/license/agpl-v3)
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
git clone git+https://github.com/yukhyShell5/Open-DTM.git
pip install .
```

### Lancement
```bash
# Démarrer le serveur
python src/server.py

# Dans un autre terminal - Démarrer un worker
python src/worker.py
```

### Utilisation Basique
```bash
# Soumettre une tâche
curl -X POST "http://localhost:8000/submit_task?command=for%20i%20in%20{1..5}%3B%20do%20echo%20%22Step%20%24i%22%3B%20sleep%201%3B%20done"

# Voir les résultats
curl "http://localhost:8000/tasks" | jq
```

## Architecture
![graph](https://mermaid.ink/img/pako:eNqNkD1vgzAQhv8Kupkg29QxeOiSDF0iVWqlShWLU18AEWxkbKkt8N_rQD_W3nSv7nnva4I3qxEk1E4NTfJ8rEwS43Bt0fhkt7ufn8K5b_2cnJRRNbqt_i1W4DGM0ajGbpyTF-s6dPQ_ENugTazMAyrnz6j8-DsN0rhYq0F6FzCFHl2vbhKmm7sC32CPFciYauW6CiqzRM-gzKu1_Y_N2VA3IC_qOkYVBq08HlsVT_5D0Gh0BxuMB0lpvvYAOcE7SLYvs70oKCG84GUueAofIHlGSlqUglBSkJyxfEnhcx1KspJxTjkjvLwToiAiBdStt-60_Xp9-fIFdpJ2eA?type=png)

## Contribuer
Les contributions sont bienvenues ! Voir :

- Guide de [contribution](CONTRIBUTING.md)
- [Gestion sémantique de version](https://semver.org/lang/fr/)
- Code de conduite

## License
AGPL - Voir [LICENSE](LICENSE)