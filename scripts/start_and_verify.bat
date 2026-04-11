@echo off
cd /d D:\soft\agent\LinkAgent-main\PyLinkAgent
start "Takin Mock Server" cmd /k "python takin_mock_server.py --db-host localhost --db-port 3306 --db-user root --db-password 123456 --db-name trodb"
timeout /t 3 /nobreak >nul
start "Demo Application" cmd /k "python demo_app.py"
timeout /t 5 /nobreak >nul
echo Services started. Press any key to run verification...
pause >nul
python verify_all.py
pause
