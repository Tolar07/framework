import os
os.chdir(r"c:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv")
from dotenv import load_dotenv
load_dotenv()
from data.api_football_plan import is_paid_plan, _probe_plan
print("probed:", _probe_plan())
print("Paid:", is_paid_plan())