#!/usr/bin/env python3
"""
Test script to verify document matching logic for Organization 1 patients
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from models import Patient, Document, Screening, ScreeningType, ScreeningDocumentMatch
from core.matcher import DocumentMatcher
from core.engine import ScreeningEngine
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_document_matching():
    """Test document matching logic with real data"""
    print("="*60)
    print("TESTING DOCUMENT MATCHING LOGIC FOR ORGANIZATION 1")
    print("="*60)
    
    app = create_app()
    with app.app_context():
        # Get Organization 1 patients and their documents
        patients = Patient.query.filter_by(org_id=1).all()
        documents = Document.query.filter_by(org_id=1).all()
        screening_types = ScreeningType.query.filter_by(org_id=1, is_active=True).all()
        
        print(f"\nFound {len(patients)} patients, {len(documents)} documents, {len(screening_types)} screening types")
        
        # Initialize matcher
        matcher = DocumentMatcher()
        
        print("\n" + "="*50)
        print("TESTING INDIVIDUAL DOCUMENT MATCHES")
        print("="*50)
        
        for document in documents:
            patient = Patient.query.get(document.patient_id)
            print(f"\nTesting Document ID {document.id}: {document.filename}")
            print(f"Patient: {patient.name} (ID: {patient.id})")
            print(f"Document Type: {document.document_type}")
            print(f"OCR Confidence: {document.ocr_confidence}%")
            print(f"OCR Text Sample: {document.ocr_text[:100]}...")
            
            # Find matches for this document
            matches = matcher.find_document_matches(document)
            print(f"Found {len(matches)} potential screening matches:")
            
            for screening_id, confidence in matches:
                screening = Screening.query.get(screening_id)
                screening_type = ScreeningType.query.get(screening.screening_type_id)
                print(f"  - Screening: {screening_type.name} (ID: {screening_id})")
                print(f"    Confidence: {confidence:.3f}")
                print(f"    Keywords: {screening_type.keywords}")
                print(f"    Current Status: {screening.status}")
        
        print("\n" + "="*50)
        print("TESTING SCREENING-TO-DOCUMENT MATCHES")
        print("="*50)
        
        # Test finding documents for each screening
        for patient in patients:
            screenings = Screening.query.filter_by(patient_id=patient.id).all()
            print(f"\nPatient: {patient.name} (ID: {patient.id})")
            
            for screening in screenings:
                screening_type = ScreeningType.query.get(screening.screening_type_id)
                print(f"  Screening: {screening_type.name} (Status: {screening.status})")
                
                # Find matching documents
                document_matches = matcher.find_screening_matches(screening)
                print(f"  Found {len(document_matches)} document matches:")
                
                for match in document_matches:
                    doc = match['document']
                    confidence = match['confidence']
                    print(f"    - Document: {doc.filename} (Confidence: {confidence:.3f})")
        
        print("\n" + "="*50)
        print("TESTING SCREENING ENGINE PROCESSING")
        print("="*50)
        
        # Test screening engine processing
        engine = ScreeningEngine()
        
        print("Before processing - Screening statuses:")
        for patient in patients:
            screenings = Screening.query.filter_by(patient_id=patient.id).all()
            for screening in screenings:
                screening_type = ScreeningType.query.get(screening.screening_type_id)
                print(f"  {patient.name}: {screening_type.name} = {screening.status}")
        
        # Process each document through the engine
        print("\nProcessing documents through screening engine...")
        for document in documents:
            print(f"Processing document {document.id}: {document.filename}")
            engine.process_new_document(document.id)
        
        print("\nAfter processing - Screening statuses:")
        for patient in patients:
            screenings = Screening.query.filter_by(patient_id=patient.id).all()
            for screening in screenings:
                screening_type = ScreeningType.query.get(screening.screening_type_id)
                print(f"  {patient.name}: {screening_type.name} = {screening.status}")
        
        print("\n" + "="*50)
        print("CHECKING SCREENING DOCUMENT MATCHES TABLE")
        print("="*50)
        
        # Check what's in the screening_document_match table
        matches = ScreeningDocumentMatch.query.all()
        print(f"Total document matches recorded: {len(matches)}")
        
        for match in matches:
            screening = Screening.query.get(match.screening_id)
            document = Document.query.get(match.document_id)
            screening_type = ScreeningType.query.get(screening.screening_type_id)
            patient = Patient.query.get(screening.patient_id)
            
            print(f"Match: {patient.name} - {screening_type.name}")
            print(f"  Document: {document.filename}")
            print(f"  Confidence: {match.match_confidence:.3f}")
            if hasattr(match, 'matched_keywords') and match.matched_keywords:
                print(f"  Keywords: {match.matched_keywords}")
        
        print("\n" + "="*50)
        print("DETAILED KEYWORD ANALYSIS")
        print("="*50)
        
        # Analyze keyword matching in detail
        for document in documents:
            patient = Patient.query.get(document.patient_id)
            print(f"\nDetailed analysis for {document.filename} ({patient.name}):")
            
            # Get relevant screening types for this patient
            patient_screenings = Screening.query.filter_by(patient_id=patient.id).all()
            
            for screening in patient_screenings:
                screening_type = ScreeningType.query.get(screening.screening_type_id)
                keywords = screening_type.keywords_list if hasattr(screening_type, 'keywords_list') else []
                
                print(f"\n  Screening: {screening_type.name}")
                print(f"  Keywords to match: {keywords}")
                
                # Check which keywords appear in the document text
                text_lower = document.ocr_text.lower()
                found_keywords = []
                for keyword in keywords:
                    if keyword.lower() in text_lower:
                        found_keywords.append(keyword)
                
                print(f"  Keywords found in text: {found_keywords}")
                
                # Calculate match confidence manually
                confidence = matcher._calculate_match_confidence(document, screening_type)
                print(f"  Calculated confidence: {confidence:.3f}")
                print(f"  Above threshold (0.3): {'YES' if confidence > 0.3 else 'NO'}")

if __name__ == "__main__":
    test_document_matching()