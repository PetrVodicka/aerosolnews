@echo off
REM Spusti vyhledavani clanku (poslednich 7 dni). Pro jine obdobi: spustit.bat --days 30
cd /d "%~dp0"
python -c "import feedparser" 2>nul || python -m pip install feedparser
python atmo_news.py %*
pause
