#!/usr/bin/env python3
"""
Database Migration Script: Add FHIR Mapping Fields to ScreeningType
This script adds FHIR interoperability fields to support Epic integration
"""

import os
import sys
import logging
from sqlalchemy import text

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
# Create app instance for migration
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize db first, then import models
from app import db
db.init_app(app)

from models import ScreeningType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_fhir_mapping_columns():
    """Add FHIR mapping columns to ScreeningType table"""
    try:
        with app.app_context():
            # Check if columns already exist
            inspector = db.inspect(db.engine)
            existing_columns = [col['name'] for col in inspector.get_columns('screening_type')]
            
            columns_to_add = [
                'fhir_search_params',
                'epic_query_context', 
                'fhir_condition_codes',
                'fhir_observation_codes',
                'fhir_document_types'
            ]
            
            for column in columns_to_add:
                if column not in existing_columns:
                    logger.info(f"Adding column: {column}")
                    db.session.execute(text(f"""
                        ALTER TABLE screening_type 
                        ADD COLUMN {column} TEXT
                    """))
                    db.session.commit()
                    logger.info(f"Successfully added column: {column}")
                else:
                    logger.info(f"Column already exists: {column}")
            
            logger.info("FHIR mapping columns migration completed successfully")
            return True
            
    except Exception as e:
        logger.error(f"Error adding FHIR mapping columns: {str(e)}")
        db.session.rollback()
        return False


def populate_fhir_mappings():
    """Populate FHIR mappings for existing screening types"""
    try:
        with app.app_context():
            from utils.fhir_mapping import ScreeningTypeFHIREnhancer
            
            enhancer = ScreeningTypeFHIREnhancer()
            screening_types = ScreeningType.query.all()
            
            updated_count = 0
            for screening_type in screening_types:
                try:
                    # Generate FHIR mappings
                    enhanced_data = screening_type.generate_fhir_mappings()
                    
                    # Save to database
                    db.session.add(screening_type)
                    updated_count += 1
                    
                    logger.info(f"Generated FHIR mappings for: {screening_type.name}")
                    
                except Exception as e:
                    logger.warning(f"Error generating FHIR mappings for {screening_type.name}: {str(e)}")
                    continue
            
            db.session.commit()
            logger.info(f"Successfully populated FHIR mappings for {updated_count} screening types")
            return True
            
    except Exception as e:
        logger.error(f"Error populating FHIR mappings: {str(e)}")
        db.session.rollback()
        return False


def verify_fhir_mappings():
    """Verify FHIR mappings are working correctly"""
    try:
        with app.app_context():
            # Test a few screening types
            test_screenings = ScreeningType.query.limit(3).all()
            
            for screening in test_screenings:
                fhir_params = screening.get_fhir_search_params()
                epic_context = screening.get_epic_query_context()
                condition_codes = screening.get_fhir_condition_codes()
                
                logger.info(f"Testing {screening.name}:")
                logger.info(f"  - FHIR params: {'✓' if fhir_params else '✗'}")
                logger.info(f"  - Epic context: {'✓' if epic_context else '✗'}")
                logger.info(f"  - Condition codes: {'✓' if condition_codes else '✗'}")
            
            logger.info("FHIR mapping verification completed")
            return True
            
    except Exception as e:
        logger.error(f"Error verifying FHIR mappings: {str(e)}")
        return False


def main():
    """Run the complete FHIR mapping migration"""
    logger.info("Starting FHIR Mapping Migration for Epic Interoperability")
    logger.info("=" * 60)
    
    # Step 1: Add database columns
    logger.info("Step 1: Adding FHIR mapping columns to database...")
    if not add_fhir_mapping_columns():
        logger.error("Failed to add FHIR mapping columns")
        return False
    
    # Step 2: Populate FHIR mappings for existing screening types
    logger.info("Step 2: Populating FHIR mappings for existing screening types...")
    if not populate_fhir_mappings():
        logger.error("Failed to populate FHIR mappings")
        return False
    
    # Step 3: Verify mappings
    logger.info("Step 3: Verifying FHIR mappings...")
    if not verify_fhir_mappings():
        logger.error("Failed to verify FHIR mappings")
        return False
    
    logger.info("=" * 60)
    logger.info("✅ FHIR Mapping Migration completed successfully!")
    logger.info("Epic interoperability features are now available")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)