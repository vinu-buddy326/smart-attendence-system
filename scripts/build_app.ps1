# Check if PyInstaller is installed
if (-not (Get-Command "pyinstaller" -ErrorAction SilentlyContinue)) {
    Write-Host "Installing PyInstaller..." -ForegroundColor Cyan
    pip install pyinstaller
}

Write-Host "--- BUILDING SMART CCTV ATTENDANCE APP ---" -ForegroundColor Yellow

# Create the executable
# --onefile: Bundle into a single EXE
# --noconsole: Don't show terminal window (only for GUI/Web dash)
# --add-data: Include folders (format: "source;dest" on Windows)

pyinstaller --onefile --noconsole `
    --add-data "frontend/templates;frontend/templates" `
    --add-data "static;static" `
    --add-data "models;models" `
    --add-data "config;config" `
    --add-data "database;database" `
    --add-data "ai_engine;ai_engine" `
    --add-data "attendance;attendance" `
    --add-data "notifications;notifications" `
    --add-data "reports;reports" `
    --add-data ".env;." `
    --name "SmartAttendanceAI" `
    main.py

Write-Host "`n--- BUILD COMPLETE! ---" -ForegroundColor Green
Write-Host "Your app is in the 'dist' folder." -ForegroundColor White
Write-Host "Double-click 'SmartAttendanceAI.exe' to run." -ForegroundColor Cyan
