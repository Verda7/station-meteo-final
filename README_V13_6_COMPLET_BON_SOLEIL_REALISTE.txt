V13.6 COMPLET — BON SOLEIL REALISTE

Version complète tout compris :
- mobile_app.py
- requirements.txt
- dossier icons/
- README

Objectif :
- afficher ☀️ plein soleil même avec quelques cirrus / léger voile
- éviter que l’app affiche trop vite 🌤️ ou ⛅ quand le ciel paraît serein
- garder 🌤️ quand les nuages deviennent visibles
- garder ⛅ quand le ciel est réellement partagé

Nouveaux seuils :
- ☀️ ciel clair : cloud < 22%
- 🌤️ peu nuageux : cloud < 45%
- ⛅ partiellement nuageux : cloud < 70%
- ☁️ très nuageux : au-dessus

À remplacer sur GitHub :
- mobile_app.py
- requirements.txt
- dossier icons/

Main file path Streamlit :
mobile_app.py
