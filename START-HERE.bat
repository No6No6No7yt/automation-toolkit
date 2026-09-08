@echo off
REM Drag a CSV file onto this .bat to get a report.html in the same folder
if "%~1"=="" goto menu
python reportforge.py "%~1" --title "Report for %~n1" --out "%~dp1%~n1-report.html"
echo.
echo Done! Report saved next to your file: %~n1-report.html
pause
exit /b

:menu
echo What do you want to do?
echo.
echo   1. Make a report from a CSV (drag-drop works too)
echo   2. Clean/merge CSV files
echo   3. Scrape a website
echo   4. See all tools
echo.
set /p choice="Enter 1-4: "
if "%choice%"=="1" ( set /p f="Drag your CSV here and press Enter: " & python reportforge.py "%f%" --out "%~dp0report.html" & echo Report: report.html & pause )
if "%choice%"=="2" ( echo Run: python csvkit.py --help  & python csvkit.py --help & pause )
if "%choice%"=="3" ( set /p u="Enter website URL: " & python scrapekit.py %u% --links & pause )
if "%choice%"=="4" ( python promptflow.py list & pause )
