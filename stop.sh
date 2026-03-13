#!/bin/bash
# Stop Evolution UI server

pkill -f "uvicorn main:app" && echo "✅ Evolution UI stopped" || echo "ℹ️ Server was not running"
