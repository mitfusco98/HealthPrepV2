
"""
Migration script to sync existing content field to new ocr_text field
"""
from app import create_app, db
from models import Document

def migrate_ocr_text():
    """Migrate existing content to ocr_text field"""
    app = create_app()
    with app.app_context():
        # Find documents with content but no ocr_text
        documents = Document.query.filter(
            Document.content.isnot(None),
            Document.ocr_text.is_(None)
        ).all()
        
        print(f"Found {len(documents)} documents to migrate...")
        
        for doc in documents:
            doc.ocr_text = doc.content
            print(f"Migrated document {doc.id}: {doc.filename}")
        
        db.session.commit()
        print(f"Migration complete. Updated {len(documents)} documents.")

if __name__ == "__main__":
    migrate_ocr_text()
