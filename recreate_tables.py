#!/usr/bin/env python3

"""
Recreate database tables for HealthPrep system
"""

import logging
from app import create_app, db

def recreate_tables():
    """Drop and recreate all database tables"""
    app = create_app()
    
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        
        print("Creating all tables...")
        db.create_all()
        
        print("Database tables recreated successfully!")

if __name__ == '__main__':
    recreate_tables()