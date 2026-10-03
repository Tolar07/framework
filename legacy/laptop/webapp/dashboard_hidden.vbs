' OLP XDV - launch the web dashboard server with NO console window.
' Run from the Startup folder shortcut (setup_dashboard_autostart.ps1) at logon,
' so the board is reachable on the LAN after every reboot without manual work.
' Window style 0 = hidden, False = don't wait for it to exit.
' start_dashboard.bat redirects all output to logs\web_server.log.

Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv"
sh.Run "cmd /c """ & sh.CurrentDirectory & "\webapp\start_dashboard.bat""", 0, False
