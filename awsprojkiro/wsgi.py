#!/usr/bin/env python3
"""
WSGI entry point for the dominoes game application.
This file is used by Gunicorn and other WSGI servers.
"""

import os
from app.main import create_app

# Create the Flask application
app = create_app(os.environ.get('FLASK_ENV', 'production'))

if __name__ == "__main__":
    # For development only - use Gunicorn in production
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))