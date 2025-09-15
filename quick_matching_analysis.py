#!/usr/bin/env python3
"""
Quick analysis of document matching results
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from models import Patient, Document, Screening, ScreeningType, ScreeningDocumentMatch
from core.matcher import DocumentMatcher
from core.engine import ScreeningEngine

def quick_analysis():
    app = create_app()
    with app.app_context():
        print("DOCUMENT MATCHING ANALYSIS - ORGANIZATION 1")
        print("="*50)
        
        # Get data
        documents = Document.query.filter_by(org_id=1).all()
        matcher = DocumentMatcher()
        
        # Test each document quickly
        for doc in documents:
            patient = Patient.query.get(doc.patient_id)
            matches = matcher.find_document_matches(doc)
            
            print(f"\n📄 {doc.filename} ({patient.name})")
            print(f"   Type: {doc.document_type}, Confidence: {doc.ocr_confidence}%")
            
            if matches:
                print(f"   ✅ Found {len(matches)} matches:")
                for screening_id, confidence in matches:
                    screening = Screening.query.get(screening_id)
                    st = ScreeningType.query.get(screening.screening_type_id)
                    print(f"      → {st.name}: {confidence:.3f} confidence")
                    if confidence > 0.8:
                        print(f"        🎯 STRONG MATCH!")
                    elif confidence > 0.5:
                        print(f"        ✨ GOOD MATCH")
            else:
                print(f"   ❌ No matches found")
        
        print(f"\n{'='*50}")
        print("SCREENING STATUS BEFORE ENGINE PROCESSING")
        print(f"{'='*50}")
        
        # Show current screening statuses
        patients = Patient.query.filter_by(org_id=1).all()
        for patient in patients:
            screenings = Screening.query.filter_by(patient_id=patient.id).all()
            if screenings:
                print(f"\n👤 {patient.name}:")
                for screening in screenings:
                    st = ScreeningType.query.get(screening.screening_type_id)
                    print(f"   {st.name}: {screening.status}")
        
        print(f"\n{'='*50}")
        print("PROCESSING DOCUMENTS THROUGH ENGINE")
        print(f"{'='*50}")
        
        # Process documents through engine
        engine = ScreeningEngine()
        for doc in documents:
            print(f"Processing {doc.filename}...")
            engine.process_new_document(doc.id)
        
        print(f"\n{'='*50}")
        print("SCREENING STATUS AFTER ENGINE PROCESSING")
        print(f"{'='*50}")
        
        # Show updated statuses
        for patient in patients:
            screenings = Screening.query.filter_by(patient_id=patient.id).all()
            if screenings:
                print(f"\n👤 {patient.name}:")
                for screening in screenings:
                    st = ScreeningType.query.get(screening.screening_type_id)
                    status_icon = "✅" if screening.status == "complete" else "⏳"
                    print(f"   {status_icon} {st.name}: {screening.status}")
        
        # Check matches table
        print(f"\n{'='*50}")
        print("RECORDED DOCUMENT MATCHES")
        print(f"{'='*50}")
        
        matches = ScreeningDocumentMatch.query.all()
        print(f"Total matches recorded: {len(matches)}")
        
        for match in matches:
            screening = Screening.query.get(match.screening_id)
            document = Document.query.get(match.document_id)
            st = ScreeningType.query.get(screening.screening_type_id)
            patient = Patient.query.get(screening.patient_id)
            
            print(f"🔗 {patient.name}: {document.filename} → {st.name}")
            print(f"   Confidence: {match.match_confidence:.3f}")

if __name__ == "__main__":
    quick_analysis()