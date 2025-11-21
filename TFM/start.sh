#!/bin/bash
cd /home/jpajares/2025-JP-GENESIS/backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8500 --workers 1
