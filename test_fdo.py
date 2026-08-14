import os
os.chdir(r"c:\Users\Motunrayo\omniroute test\olp_xdv_agent\olp_xdv")
from data.football_data_org_source import list_competitions
print(list_competitions()[:3])