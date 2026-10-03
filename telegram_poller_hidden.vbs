' OLP XDV - launch the Telegram poller daemon with NO console window.
' Task Scheduler ("OLP XDV Telegram Daemon", at logon) runs this via wscript.
' Window style 0 = hidden, False = don't wait for it to exit.
' The .bat redirects all output to logs\poller.log, so nothing is lost.

Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv"
sh.Run "cmd /c """ & sh.CurrentDirectory & "\telegram_poller.bat""", 0, False
