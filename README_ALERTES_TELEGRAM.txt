Station Météo V9 — Alertes Telegram

1) Créer un bot Telegram
- Dans Telegram, cherche : @BotFather
- Envoie : /newbot
- Donne un nom au bot
- Copie le token donné par BotFather

2) Récupérer ton chat_id
- Dans Telegram, cherche ton bot et envoie-lui un message : Bonjour
- Dans le navigateur, ouvre :
  https://api.telegram.org/botTON_TOKEN/getUpdates
- Remplace TON_TOKEN par le token du bot
- Cherche "chat":{"id":123456789
- Copie ce nombre : c’est ton chat_id

3) Configurer config_alertes.json
Remplace :
- TON_TOKEN_BOT_TELEGRAM
- TON_CHAT_ID

4) Tester
Double-clique :
TESTER_ALERTE_TELEGRAM.bat

5) Lancer une vérification manuelle
Double-clique :
VERIFIER_ALERTES.bat

6) Planifier toutes les 10 minutes
Double-clique :
PLANIFIER_ALERTES_10MIN.bat

7) Supprimer la planification
Double-clique :
SUPPRIMER_PLANIFICATION_ALERTES.bat

Seuils configurables dans config_alertes.json :
- score_orage : défaut 70/100
- score_pluie_intense : défaut 70/100
- score_grele : défaut 60/100
- score_tornade_approximatif : défaut 55/100
- risque_downburst : défaut 65/100
- risque_supercellule : défaut 65/100
- wind_gusts_10m : défaut 75 km/h

Note :
Ces alertes tournent sur ton PC Windows si tu utilises la tâche planifiée.
Sur Streamlit Cloud, il faudra plus tard utiliser GitHub Actions pour déclencher les alertes automatiquement.
