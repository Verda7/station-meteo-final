V13.5 FIX PLUIE FAIBLE VISIBLE

Correction :
- Une petite pluie avec forte probabilité est maintenant visible sur l’icône.
- Exemple : 0,6 mm + proba 72% affichera pluie faible / éclaircies + pluie.
- La logique tient compte de :
  - cumul pluie
  - probabilité de pluie
  - soleil/éclaircies dans la période
  - nébulosité
- Correction appliquée aux cartes matin/après-midi/soirée/nuit et au résumé 7 jours.

À remplacer :
- mobile_app.py
- requirements.txt
- dossier icons/

Main file path : mobile_app.py
