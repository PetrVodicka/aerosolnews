@echo off
REM Uzsi vyber: jen jadro tematu (aerosoly, ovzdusi, atmosfera, prach), poslednich 30 dni
cd /d "%~dp0"
python -c "import feedparser" 2>nul || python -m pip install feedparser
python atmo_news.py --narrow %*
pause
