"""
run.py - Beginner-Friendly Launcher for SafeHer Backend

Runs the Flask server with friendly instructions and environment diagnostics.
Usage:
    python run.py
"""

import sys
import os

print("""
========================================================================
   🛡️   SafeHer — Women Safety Route Navigation Backend
========================================================================
""")

# Check Python version
print(f"Python Version: {sys.version.split()[0]}")

# Ensure database is initialized
try:
    import database
    database.init_db()
    print("✓ SQLite Database (safety.db) initialized and sample data verified.")
except Exception as e:
    print(f"❌ Database initialization failed: {e}")
    sys.exit(1)

# Start Flask App
try:
    from app import app
    print("✓ Flask application loaded successfully.")
    print("\nStarting local server on http://127.0.0.1:5000 ...")
    print("Press CTRL+C to stop the server.\n")
    app.run(host='127.0.0.1', port=5000, debug=True)
except ImportError as e:
    print(f"\n❌ Missing dependencies: {e}")
    print("Please install requirements using:")
    print("    pip install -r requirements.txt\n")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Server error: {e}")
    sys.exit(1)
