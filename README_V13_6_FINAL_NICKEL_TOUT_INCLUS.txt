V13.6 FINAL NICKEL — TOUT INCLUS

ZIP complet :
- mobile_app.py complet
- requirements.txt
- dossier icons/
- README

Inclus :
- load_multimodel restauré / sécurisé
- fallback modèles : sélectionnés -> Best match -> GFS
- alertes avec priorité orage :
  35 jaune, 50 orange, 70 rouge, 90 violet
- score global :
  <35 vert, <50 jaune, <70 orange, <90 rouge, sinon violet
- soleil réaliste :
  ciel clair jusqu’à 22% de nuages
- correction résumé 7 jours
- graphique 15 jours ECMWF/GFS safe :
  GFS seul si ECMWF indisponible
  moyenne seulement si les deux sont disponibles

À remplacer sur GitHub :
- mobile_app.py
- requirements.txt
- dossier icons/
