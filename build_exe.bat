@echo off
setlocal

python -m pip install -r requirements.txt
pyinstaller --noconfirm --clean --onefile --windowed --name ClipboardAIAssistant app.py

echo.
echo Build complete: dist\ClipboardAIAssistant.exe
