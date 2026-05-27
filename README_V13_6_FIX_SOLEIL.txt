
V13.6 — FIX SOLEIL / NUAGEUX

REMPLACE :

if c == 0 or cloud < 18:
    return icon_img("ciel_clair.png")

if c == 1 or cloud < 38:
    return icon_img("peu_nuageux.png")

if c == 2 or cloud < 72:
    return icon_img("partiellement_nuageux.png")

PAR :

if c == 0 or cloud < 12:
    return icon_img("ciel_clair.png")

if c == 1 or cloud < 28:
    return icon_img("peu_nuageux.png")

if c == 2 or cloud < 60:
    return icon_img("partiellement_nuageux.png")

Résultat :
- ☀️ plein soleil plus fréquent
- 🌤️ moins agressif
- ⛅ uniquement quand les nuages sont réellement visibles
- rendu plus réaliste pour Frasnes / Rèves
