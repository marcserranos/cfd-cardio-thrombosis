@echo off
rem ===== Case 1 left atrium CFD (MOS individual lab). Double-click this file. =====
setlocal
cd /d "%~dp0"
echo.
echo  Looking for Ansys Fluent...
set "FLUENT="
for %%V in (262 261 252 251 242 241 232 231) do (
  if not defined FLUENT if exist "%ProgramFiles%\ANSYS Inc\ANSYS Student\v%%V\fluent\ntbin\win64\fluent.exe" set "FLUENT=%ProgramFiles%\ANSYS Inc\ANSYS Student\v%%V\fluent\ntbin\win64\fluent.exe"
  if not defined FLUENT if exist "%ProgramFiles%\ANSYS Inc\v%%V\fluent\ntbin\win64\fluent.exe" set "FLUENT=%ProgramFiles%\ANSYS Inc\v%%V\fluent\ntbin\win64\fluent.exe"
)
if not defined FLUENT (
  echo  ERROR: Fluent was not found in "%ProgramFiles%\ANSYS Inc".
  echo  Please send Marc a photo of this window.
  pause
  exit /b 1
)
echo  Found: "%FLUENT%"
echo %FLUENT%> fluent_path_used.txt
if not exist results_A_baseline mkdir results_A_baseline
if not exist results_B_finemesh mkdir results_B_finemesh

echo.
echo  [1/2] Baseline simulation started %date% %time%  (a few hours, do not close this window)
"%FLUENT%" 3ddp -t4 -g -wait -i run_A_baseline.jou > results_A_baseline\console_log.txt 2>&1
echo  [1/2] finished %date% %time%
powershell -NoProfile -Command "Compress-Archive -Path 'results_A_baseline' -DestinationPath 'SEND_TO_MARC_A_baseline.zip' -Force"

echo.
echo  [2/2] Fine-mesh simulation started %date% %time%  (optional, a few more hours)
"%FLUENT%" 3ddp -t4 -g -wait -i run_B_finemesh.jou > results_B_finemesh\console_log.txt 2>&1
echo  [2/2] finished %date% %time%
powershell -NoProfile -Command "Compress-Archive -Path 'results_B_finemesh' -DestinationPath 'SEND_TO_MARC_B_finemesh.zip' -Force"

echo.
echo  ALL DONE. Please upload SEND_TO_MARC_A_baseline.zip (and _B_ if it exists) to the Google Drive link from Marc.
pause
