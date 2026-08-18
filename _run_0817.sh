#!/usr/bin/env bash
cd "C:/Users/Motunrayo/omniroute test/olp_xdv_agent/olp_xdv"
python _run_0817.py > /tmp/run_0817.txt 2>&1
echo "EXIT:$?" >> /tmp/run_0817.txt
