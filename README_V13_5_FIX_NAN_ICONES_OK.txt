V13.5 FIX NAN ICONES OK

Correction :
- Corrige l’erreur :
  cannot convert float NaN to integer
- Les icônes météo ne plantent plus si un modèle renvoie une valeur vide.
- Les valeurs météo manquantes sont remplacées par des valeurs neutres.
- Conserve :
  - averses + éclaircies
  - graphes unités
  - icônes pro

À remplacer :
- mobile_app.py
- requirements.txt
- dossier icons/

Main file path : mobile_app.py
