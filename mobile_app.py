
# V12.5 extrait principal
# Ajout :
# - sélection des modèles météo dans la sidebar
# - moyenne multi-modèles personnalisable
# - mode 'comme PC'

MODELS = {
    "Best match": "best_match",
    "AROME HD": "meteofrance_arome_france_hd",
    "ICON D2": "icon_d2",
    "ICON EU": "icon_eu",
    "GFS": "gfs_global",
    "ECMWF": "ecmwf_ifs04",
    "HARMONIE": "knmi_harmonie_arome_europe",
}

selected_models = st.sidebar.multiselect(
    "Modèles météo",
    list(MODELS.keys()),
    default=["ECMWF", "ICON EU", "AROME HD"]
)

# La logique moyenne multi-modèles utilise maintenant
# exactement les mêmes calculs que l'app PC.
