$ErrorActionPreference='SilentlyContinue'
Set-Location "C:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv"
python run_daily.py --no-send --no-web --no-whatsapp --no-email | Out-File -Append prod_0825_full.log
"DONE_EXIT=$LASTEXITCODE"