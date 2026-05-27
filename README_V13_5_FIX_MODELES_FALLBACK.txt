V13.5 FIX MODELES FALLBACK

Correction :
- Si un modèle sélectionné échoue, il est ignoré.
- Si tous les modèles sélectionnés échouent, l’app bascule automatiquement sur Best match.
- Évite l’erreur : Aucun modèle disponible.
- Best match reste le mode le plus fiable.

À remplacer :
- mobile_app.py
- requirements.txt
- dossier icons/
