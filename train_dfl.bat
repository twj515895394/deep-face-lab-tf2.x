@echo off
REM train_dfl.bat - Start DFL training
REM Edit SRC_DIR DST_DIR MODEL_DIR below

set CONTAINER=dfl-tf2

set SRC_DIR=/s/src/yangzi-2025/aligned
set DST_DIR=/s/v_source/chenxiang/02/data_dst/aligned
set MODEL_DIR=/h/models2/model-yangzi

set MODEL=SAEHD
set DISPLAY=host.docker.internal:2

docker ps --format "{{.Names}}" | findstr /c:"%CONTAINER%" >nul
if %errorlevel% neq 0 (
  echo [ERROR] Container %CONTAINER% not running.
  echo Run run_dfl.bat first.
  pause
  exit /b 1
)

echo ==========================================
echo   DFL Training
echo   SRC  : %SRC_DIR%
echo   DST  : %DST_DIR%
echo   MODEL: %MODEL_DIR%
echo ==========================================
echo.
echo Killing any leftover training processes...
docker exec %CONTAINER% pkill -f "python main.py train" >nul 2>&1
timeout /t 3 /nobreak >nul

docker exec -e DISPLAY=%DISPLAY% -it %CONTAINER% python main.py train --model %MODEL% --training-data-src-dir %SRC_DIR% --training-data-dst-dir %DST_DIR% --model-dir %MODEL_DIR%

pause
