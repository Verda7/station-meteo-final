
# V13.6 — FIX RESUME 7 JOURS

# ANCIEN :

if code_med == 0 or cloud < 18:
    return icon_img("ciel_clair.png", 28)

if code_med == 1 or cloud < 38:
    return icon_img("peu_nuageux.png", 28)

if code_med == 2 or cloud < 72:
    return icon_img("partiellement_nuageux.png", 28)

# NOUVEAU :

if code_med == 0 or cloud < 22:
    return icon_img("ciel_clair.png", 28)

if code_med == 1 or cloud < 45:
    return icon_img("peu_nuageux.png", 28)

if code_med == 2 or cloud < 70:
    return icon_img("partiellement_nuageux.png", 28)
