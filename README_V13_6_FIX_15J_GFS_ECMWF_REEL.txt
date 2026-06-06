V13.6 FIX 15J GFS / ECMWF REEL

Correction :
- Le graphique 15 jours n'affiche plus de fausse courbe ECMWF si ECMWF ne répond pas.
- GFS est affiché seul si ECMWF est indisponible.
- La moyenne ECMWF/GFS est affichée uniquement si les deux modèles sont réellement disponibles.
- Si ECMWF et GFS ressortent identiques, la moyenne est masquée.

À remplacer sur GitHub :
- mobile_app.py uniquement
