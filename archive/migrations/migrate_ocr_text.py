
"""
Migration script to add ocr_text column and sync existing content field
"""
from app import create_app, db
from models import Document
from sqlalchemy import text

def migrate_ocr_text():
    """Add ocr_text column and migrate existing content to it"""
    app = create_app()
    with app.app_context():
        try:
            # First, check if ocr_text column exists
            result = db.session.execute(text("PRAGMA table_info(document)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'ocr_text' not in columns:
                print("Adding ocr_text column to document table...")
                # Add the ocr_text column
                db.session.execute(text("ALTER TABLE document ADD COLUMN ocr_text TEXT"))
                db.session.commit()
                print("ocr_text column added successfully.")
            else:
                print("ocr_text column already exists.")
            
            # Now migrate data from content to ocr_text where needed
            print("Migrating existing content to ocr_text field...")
            
            # Update documents that have content but no ocr_text
            result = db.session.execute(text("""
                UPDATE document 
                SET ocr_text = content 
                WHERE content IS NOT NULL 
                AND (ocr_text IS NULL OR ocr_text = '')
            """))
            
            updated_count = result.rowcount
            db.session.commit()
            
            print(f"Migration complete. Updated {updated_count} documents.")
            
            # Verify the migration
            total_with_content = db.session.execute(text("SELECT COUNT(*) FROM document WHERE content IS NOT NULL")).scalar()
            total_with_ocr_text = db.session.execute(text("SELECT COUNT(*) FROM document WHERE ocr_text IS NOT NULL")).scalar()
            
            print(f"Verification: {total_with_content} documents have content, {total_with_ocr_text} have ocr_text")
            
        except Exception as e:
            print(f"Error during migration: {str(e)}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    migrate_ocr_text()
