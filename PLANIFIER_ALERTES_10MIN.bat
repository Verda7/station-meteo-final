@echo off
cd /d "%~dp0"
schtasks /Create /TN "StationMeteoAlertesTelegram" /TR "\"%CD%\VERIFIER_ALERTES.bat\"" /SC MINUTE /MO 10 /F
echo.
echo Tache planifiee creee : verification alertes toutes les 10 minutes.
pause
