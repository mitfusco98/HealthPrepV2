#!/usr/bin/env python3
"""
Quick verification that Patient schema migration was successful
"""

import os
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_patient_schema():
    """Verify Patient table now has all required FHIR columns"""
    try:
        import psycopg2
        from urllib.parse import urlparse
        
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL not found")
            return False
        
        parsed = urlparse(database_url)
        
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path[1:]
        )
        
        cur = conn.cursor()
        
        # Check Patient table columns
        cur.execute("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'patient' 
            ORDER BY ordinal_position
        """)
        
        columns = cur.fetchall()
        logger.info("Patient table schema:")
        
        required_fhir_columns = ['fhir_patient_resource', 'last_fhir_sync', 'fhir_version_id']
        found_columns = [col[0] for col in columns]
        
        for col_name, data_type, nullable in columns:
            logger.info(f"  {col_name}: {data_type} ({'NULL' if nullable == 'YES' else 'NOT NULL'})")
        
        # Check if all required FHIR columns are present
        missing_columns = [col for col in required_fhir_columns if col not in found_columns]
        
        if missing_columns:
            logger.error(f"Missing FHIR columns: {missing_columns}")
            return False
        
        logger.info("✅ All required FHIR columns are present!")
        
        # Check indexes
        cur.execute("""
            SELECT indexname, tablename FROM pg_indexes 
            WHERE tablename = 'patient' AND indexname LIKE 'idx_patient_%'
        """)
        
        indexes = cur.fetchall()
        logger.info("Patient table indexes:")
        for idx_name, table_name in indexes:
            logger.info(f"  {idx_name}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Schema verification failed: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Verifying Patient schema migration...")
    success = verify_patient_schema()
    
    if success:
        logger.info("🎉 Patient schema migration completed successfully!")
        logger.info("Admin dashboard should now work without database errors.")
    else:
        logger.error("❌ Patient schema verification failed.")