V13.6 GRAPH 15J ECMWF SAFE

Base utilisée :
- V13.6 Graphique 15J ECMWF/GFS qui fonctionnait.

Correction :
- Ne touche pas à load_multimodel.
- Si ECMWF ne répond pas, GFS reste affiché seul.
- La moyenne apparaît uniquement si ECMWF + GFS sont vraiment disponibles.
- Si les deux courbes sont identiques, la moyenne est masquée.

À remplacer sur GitHub :
- mobile_app.py uniquement.
