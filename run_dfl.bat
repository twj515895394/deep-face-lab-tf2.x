@echo off
REM run_dfl.bat - Start DFL container

set IMAGE=dfl-tf2:latest
set CONTAINER=dfl-tf2

docker images --format "{{.Repository}}:{{.Tag}}" | findstr /c:"%IMAGE%" >nul
if %errorlevel% neq 0 (
  echo [ERROR] Image %IMAGE% not found, building...
  docker build -t %IMAGE% .
)

docker ps -a --format "{{.Names}}" | findstr /c:"%CONTAINER%" >nul
if %errorlevel% equ 0 (
  echo Removing old container %CONTAINER%...
  docker rm -f %CONTAINER% >nul
)

echo Starting container %CONTAINER%...
echo Mounts: S H D E F G
echo.

docker run --name %CONTAINER% --gpus all -v /mnt/host/d:/d -v /mnt/host/e:/e -v /mnt/host/f:/f -v /mnt/host/g:/g -v /mnt/host/h:/h -v /mnt/host/s:/s -it %IMAGE% /bin/bash
