# Comment Contribuer

Nous apprécions votre intérêt pour le Distributed Task Manager ! Voici comment contribuer de manière utile.

## Prérequis Techniques
- Python 3.9+
- Git basique
- Connaissance des PR GitHub

## Processus de Contribution

1. **Ouvrir un Issue** avant de coder :
   - Bug ? Décrire le problème et les étapes pour le reproduire
   - Nouvelle fonctionnalité ? Expliquer le cas d'usage

2. **Forker le dépôt** et créer une branche :
    ```bash
    git checkout -b feat/ma-nouvelle-fonctionnalite
    ```

3. Garder les changements petits :
    - 1 PR = 1 fonctionnalité/bugfix
    - Maximum 400 lignes modifiées par PR

4. **Tester localement** :
    ```bash
    python -m pytest tests/
    ```

5. Documenter les changements :
    - Mettre à jour le README si nécessaire
    - Ajouter des commentaires pour les parties complexes

## Standards de Code

- Style : Respecter PEP 8 (utilisez black pour formater)
- Tests : Couvrir les nouvelles fonctionnalités
- Messages de commit :
    ```bash
    [Type]: description courte
    ```
    - **Types acceptés** : `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## Rapport de Bugs
Utilisez le template d'issue et incluez :

```bash
### Environnement
- OS : [ex: Ubuntu 22.04]
- Version Python : [ex: 3.10.6]
- Étapes pour reproduire : [ex: 1. Lancer X, 2. Cliquer Y]

### Comportement attendu
[Description]

### Comportement actuel
[Description]

### Logs/Screenshots
[Coller les logs d'erreur]
```

## Processus de Revue
1. Un mainteneur assignera un reviewer sous 48h
2. Discussion sur la PR
3. Tests automatiques doivent passer
4. 2 approbations nécessaires avant merge