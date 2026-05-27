V13.6 FALLBACK SOIR + CACHE OK

Correction :
- Si les modèles sélectionnés échouent, ils sont ignorés un par un.
- Si aucun modèle sélectionné ne répond :
  1) fallback Best match
  2) fallback GFS Global
  3) dernière prévision valide en cache local
- Évite l'écran : Aucun modèle disponible
- Utile surtout le soir, quand certains modèles météo sont en mise à jour.

À remplacer :
- mobile_app.py
- requirements.txt
- dossier icons/
