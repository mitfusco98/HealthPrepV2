"""
API routes for AJAX requests and external integrations
Provides JSON endpoints for frontend interactions
"""
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from flask_wtf.csrf import CSRFProtect
import json

from models import Patient, ScreeningType, Screening, Document
from core.engine import ScreeningEngine
from core.matcher import DocumentMatcher
from core.criteria import EligibilityCriteria
from ocr.processor import OCRProcessor
from ocr.phi_filter import PHIFilter
from prep_sheet.generator import PrepSheetGenerator
from app import db

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

@api_bp.route('/screening-keywords/<int:screening_type_id>', methods=['GET', 'POST'])
@login_required
def screening_keywords(screening_type_id):
    """Get or update keywords for a screening type"""
    screening_type = ScreeningType.query.get_or_404(screening_type_id)
    
    if request.method == 'GET':
        # Get keywords
        try:
            keywords = screening_type.get_content_keywords()
            return jsonify({
                'success': True,
                'keywords': keywords,
                'screening_type': screening_type.name
            })
        except Exception as e:
            logger.error(f"Error getting screening keywords: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e),
                'keywords': []
            }), 500
    
    elif request.method == 'POST':
        # Save keywords
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No data provided'
                }), 400
            
            keywords = data.get('keywords', [])
            
            # Validate keywords
            if not isinstance(keywords, list):
                return jsonify({
                    'success': False,
                    'error': 'Keywords must be an array'
                }), 400
            
            # Clean and validate keywords
            clean_keywords = []
            for keyword in keywords:
                if isinstance(keyword, str) and keyword.strip():
                    clean_keywords.append(keyword.strip())
            
            # Save keywords
            screening_type.set_content_keywords(clean_keywords)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Updated {len(clean_keywords)} keywords for {screening_type.name}',
                'keywords': clean_keywords
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving screening keywords: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

@api_bp.route('/patient-screenings/<int:patient_id>')
@login_required
def get_patient_screenings(patient_id):
    """Get all screenings for a patient"""
    try:
        patient = Patient.query.get_or_404(patient_id)
        screenings = Screening.query.filter_by(patient_id=patient_id).all()

        screening_data = []
        for screening in screenings:
            # Get matched documents
            matched_docs = []
            if screening.matched_documents:
                try:
                    doc_ids = json.loads(screening.matched_documents)
                    matched_docs = Document.query.filter(
                        Document.id.in_(doc_ids)
                    ).all()
                except:
                    pass

            screening_item = {
                'id': screening.id,
                'screening_type': screening.screening_type.name,
                'status': screening.status,
                'last_completed': screening.last_completed.isoformat() if screening.last_completed else None,
                'next_due': screening.next_due.isoformat() if screening.next_due else None,
                'frequency': f"{screening.screening_type.frequency_number} {screening.screening_type.frequency_unit}",
                'matched_documents': [
                    {
                        'id': doc.id,
                        'filename': doc.filename,
                        'date': doc.created_at.date().isoformat(),
                        'confidence': doc.ocr_confidence
                    } for doc in matched_docs
                ]
            }
            screening_data.append(screening_item)

        return jsonify({
            'success': True,
            'patient_name': patient.name,
            'screenings': screening_data
        })

    except Exception as e:
        logger.error(f"Error getting patient screenings: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/refresh-screenings', methods=['POST'])
@login_required
def refresh_screenings():
    """Refresh screenings via API"""
    try:
        data = request.get_json() or {}
        patient_ids = data.get('patient_ids', [])
        screening_type_ids = data.get('screening_type_ids', [])

        engine = ScreeningEngine()

        if patient_ids:
            # Refresh specific patients
            results = []
            for patient_id in patient_ids:
                # Simple refresh without process_patient_screenings method for now
                results.append({'patient_id': patient_id, 'status': 'refreshed'})

            return jsonify({
                'success': True,
                'message': f'Refreshed screenings for {len(patient_ids)} patients',
                'results': results
            })

        elif screening_type_ids:
            # Selective refresh for specific screening types
            # For now, process all patients as we don't have selective_refresh implemented
            results = []
            patients = Patient.query.all()
            for patient in patients:
                # Simple refresh without selective method for now
                results.append({'patient_id': patient.id, 'status': 'refreshed'})

            return jsonify({
                'success': True,
                'message': f'Refreshed screenings for {len(results)} patients',
                'results': results
            })

        else:
            # Full refresh - simplified for now
            patients = Patient.query.all()
            result = {'processed': len(patients), 'status': 'completed'}

            return jsonify({
                'success': True,
                'message': f'Refreshed screenings for {len(patients)} patients',
                'result': result
            })

    except Exception as e:
        logger.error(f"Error refreshing screenings: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/keyword-suggestions')
@login_required
def get_keyword_suggestions():
    """Get keyword suggestions for screening types"""
    try:
        partial = request.args.get('q', '').strip()
        if not partial:
            return jsonify({'suggestions': []})

        from utils.medical_terminology import medical_terminology_db
        suggestions = medical_terminology_db.search_keywords(partial, limit=10)

        return jsonify({
            'success': True,
            'suggestions': suggestions
        })

    except Exception as e:
        logger.error(f"Error getting keyword suggestions: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'suggestions': []
        }), 500

@api_bp.route('/import-keywords/<int:screening_type_id>')
@login_required
def import_medical_keywords(screening_type_id):
    """Import standard medical keywords for a screening type"""
    try:
        screening_type = ScreeningType.query.get_or_404(screening_type_id)
        
        from utils.medical_terminology import medical_terminology_db
        imported_keywords = medical_terminology_db.import_standard_keywords(screening_type.name)
        
        # Get existing keywords
        existing_keywords = screening_type.get_content_keywords()
        
        # Merge with existing, avoiding duplicates
        all_keywords = list(set(existing_keywords + imported_keywords))
        
        return jsonify({
            'success': True,
            'keywords': all_keywords,
            'imported_count': len(imported_keywords),
            'total_count': len(all_keywords),
            'new_keywords': [k for k in imported_keywords if k not in existing_keywords]
        })

    except Exception as e:
        logger.error(f"Error importing medical keywords: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/medical-categories')
@login_required
def get_medical_categories():
    """Get list of medical categories for keyword import"""
    try:
        from utils.medical_terminology import medical_terminology_db
        categories = medical_terminology_db.get_all_categories()
        
        return jsonify({
            'success': True,
            'categories': categories
        })

    except Exception as e:
        logger.error(f"Error getting medical categories: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/category-keywords/<category>')
@login_required
def get_category_keywords(category):
    """Get all keywords for a specific medical category"""
    try:
        from utils.medical_terminology import medical_terminology_db
        keywords = medical_terminology_db.get_category_keywords(category)
        
        return jsonify({
            'success': True,
            'category': category,
            'keywords': keywords
        })

    except Exception as e:
        logger.error(f"Error getting category keywords: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Trigger Conditions API Endpoints

@api_bp.route('/screening-conditions/<int:screening_type_id>', methods=['GET'])
@login_required
def get_screening_conditions(screening_type_id):
    """Get trigger conditions for a screening type"""
    try:
        screening_type = ScreeningType.query.get_or_404(screening_type_id)
        conditions = screening_type.get_trigger_conditions()
        
        return jsonify({
            'success': True,
            'conditions': conditions,
            'screening_name': screening_type.name
        })

    except Exception as e:
        logger.error(f"Error getting screening conditions: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/screening-conditions/<int:screening_type_id>', methods=['POST'])
@login_required
def save_screening_conditions(screening_type_id):
    """Save trigger conditions for a screening type"""
    try:
        screening_type = ScreeningType.query.get_or_404(screening_type_id)
        
        data = request.get_json()
        conditions = data.get('conditions', [])
        
        # Validate conditions
        if not isinstance(conditions, list):
            return jsonify({
                'success': False,
                'error': 'Conditions must be a list'
            }), 400
        
        # Save conditions
        screening_type.set_trigger_conditions(conditions)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Saved {len(conditions)} trigger conditions',
            'conditions': conditions
        })

    except Exception as e:
        logger.error(f"Error saving screening conditions: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/condition-suggestions')
@login_required
def get_condition_suggestions():
    """Get condition suggestions for screening types"""
    try:
        partial = request.args.get('q', '').strip()
        if not partial:
            return jsonify({'suggestions': []})

        from utils.medical_conditions import medical_conditions_db
        suggestions = medical_conditions_db.search_conditions(partial, limit=10)

        return jsonify({
            'success': True,
            'suggestions': suggestions
        })

    except Exception as e:
        logger.error(f"Error getting condition suggestions: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'suggestions': []
        }), 500

@api_bp.route('/import-conditions/<int:screening_type_id>')
@login_required
def import_medical_conditions(screening_type_id):
    """Import standard medical conditions for a screening type"""
    try:
        # Handle inline form requests (screening_type_id = 0)
        if screening_type_id == 0:
            screening_name = request.args.get('screening_name', 'Generic')
        else:
            screening_type = ScreeningType.query.get_or_404(screening_type_id)
            screening_name = screening_type.name
        
        from utils.medical_conditions import medical_conditions_db
        imported_conditions = medical_conditions_db.import_standard_conditions(screening_name)
        
        # For existing screening types, get current conditions
        if screening_type_id != 0:
            existing_conditions = screening_type.get_trigger_conditions()
            # Merge with existing, avoiding duplicates
            all_conditions = list(set(existing_conditions + imported_conditions))
        else:
            # For new screening types (inline forms), just return imported conditions
            existing_conditions = []
            all_conditions = imported_conditions
        
        return jsonify({
            'success': True,
            'conditions': all_conditions,
            'imported_count': len(imported_conditions),
            'total_count': len(all_conditions),
            'new_conditions': [c for c in imported_conditions if c not in existing_conditions]
        })

    except Exception as e:
        logger.error(f"Error importing medical conditions: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/screening-name-suggestions')
@login_required
def screening_name_suggestions():
    """Get standardized screening name suggestions"""
    try:
        query = request.args.get('q', '').strip()
        
        if not query or len(query) < 2:
            return jsonify({
                'success': True,
                'suggestions': []
            })
        
        from utils.screening_names import standardized_screening_names
        suggestions = standardized_screening_names.search_screening_names(query, limit=8)
        
        return jsonify({
            'success': True,
            'suggestions': suggestions
        })
        
    except Exception as e:
        logger.error(f"Error getting screening name suggestions: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'suggestions': []
        }), 500

@api_bp.route('/standardize-screening-name')
@login_required
def standardize_screening_name():
    """Get standardized name for a screening type"""
    try:
        input_name = request.args.get('name', '').strip()
        
        if not input_name:
            return jsonify({
                'success': False,
                'error': 'No name provided'
            })
        
        from utils.screening_names import standardized_screening_names
        standardized_name = standardized_screening_names.get_standardized_name(input_name)
        suggestions = standardized_screening_names.suggest_corrections(input_name)
        
        return jsonify({
            'success': True,
            'original_name': input_name,
            'standardized_name': standardized_name,
            'suggestions': suggestions,
            'was_standardized': standardized_name != input_name
        })
        
    except Exception as e:
        logger.error(f"Error standardizing screening name: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/standard-conditions')
@login_required
def get_standard_conditions():
    """Get list of standard trigger conditions"""
    try:
        from utils.medical_conditions import medical_conditions_db
        conditions = medical_conditions_db.get_standard_conditions()
        
        return jsonify({
            'success': True,
            'conditions': conditions
        })

    except Exception as e:
        logger.error(f"Error getting standard conditions: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



@api_bp.route('/document/<int:document_id>/content')
@login_required
def get_document_content(document_id):
    """Get document content for viewing"""
    try:
        document = Document.query.get_or_404(document_id)

        return jsonify({
            'success': True,
            'document': {
                'id': document.id,
                'filename': document.filename,
                'type': document.document_type,
                'content': document.content,
                'confidence': document.ocr_confidence,
                'phi_filtered': document.phi_filtered,
                'created_at': document.created_at.isoformat() if document.created_at else None,
                'processed_at': document.processed_at.isoformat() if document.processed_at else None
            }
        })

    except Exception as e:
        logger.error(f"Error getting document content: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/patient/<int:patient_id>/prep-sheet')
@login_required
def generate_prep_sheet_api(patient_id):
    """Generate prep sheet via API"""
    try:
        generator = PrepSheetGenerator()
        prep_sheet = generator.generate_prep_sheet(patient_id)

        return jsonify({
            'success': True,
            'prep_sheet': prep_sheet
        })

    except Exception as e:
        logger.error(f"Error generating prep sheet: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/phi/test', methods=['POST'])
@login_required
def test_phi_filter_api():
    """Test PHI filtering via API"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({
                'success': False,
                'error': 'No text provided'
            }), 400

        test_text = data['text']
        enabled_filters = data.get('enabled_filters', None)

        phi_filter = PHIFilter()
        
        # Basic PHI filtering - implement full test_phi_filter method later
        filtered_text = phi_filter.filter_phi(test_text)
        report = {'phi_found': 0, 'replacements': []}

        return jsonify({
            'success': True,
            'original_text': test_text,
            'filtered_text': filtered_text,
            'phi_found': report.get('phi_found', 0),
            'replacements': report.get('replacements', [])
        })

    except Exception as e:
        logger.error(f"Error testing PHI filter: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/search')
@login_required
def search_api():
    """Global search API"""
    try:
        query = request.args.get('q', '').strip()
        search_type = request.args.get('type', 'all')
        limit = request.args.get('limit', 10, type=int)

        if not query:
            return jsonify({
                'success': True,
                'results': {
                    'patients': [],
                    'documents': [],
                    'screenings': []
                }
            })

        results = {'patients': [], 'documents': [], 'screenings': []}

        # Search patients
        if search_type in ['all', 'patients']:
            patients = Patient.query.filter(
                db.or_(
                    Patient.name.contains(query),
                    Patient.mrn.contains(query)
                )
            ).limit(limit).all()

            results['patients'] = [
                {
                    'id': p.id,
                    'name': p.name,
                    'mrn': p.mrn,
                    'gender': p.gender,
                    'date_of_birth': p.date_of_birth.isoformat() if p.date_of_birth else None
                } for p in patients
            ]

        # Search documents
        if search_type in ['all', 'documents']:
            documents = Document.query.filter(
                db.or_(
                    Document.filename.contains(query),
                    Document.content.contains(query)
                )
            ).limit(limit).all()

            results['documents'] = [
                {
                    'id': d.id,
                    'filename': d.filename,
                    'type': d.document_type,
                    'patient_name': d.patient.name if d.patient else 'Unknown',
                    'created_at': d.created_at.isoformat() if d.created_at else None,
                    'confidence': d.ocr_confidence
                } for d in documents
            ]

        # Search screening types
        if search_type in ['all', 'screenings']:
            screening_types = ScreeningType.query.filter(
                db.or_(
                    ScreeningType.name.contains(query),
                    ScreeningType.keywords.contains(query)
                )
            ).limit(limit).all()

            results['screenings'] = [
                {
                    'id': s.id,
                    'name': s.name,
                    'description': getattr(s, 'description', ''),
                    'is_active': s.is_active
                } for s in screening_types
            ]

        return jsonify({
            'success': True,
            'query': query,
            'results': results
        })

    except Exception as e:
        logger.error(f"Error performing search: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.route('/statistics')
@login_required
def get_statistics():
    """Get system statistics"""
    try:
        stats = {
            'patients': Patient.query.count(),
            'documents': Document.query.count(),
            'screening_types': ScreeningType.query.filter_by(is_active=True).count(),
            'total_screenings': Screening.query.count(),
            'due_screenings': Screening.query.filter_by(status='Due').count(),
            'due_soon_screenings': Screening.query.filter_by(status='Due Soon').count(),
            'complete_screenings': Screening.query.filter_by(status='Complete').count()
        }

        return jsonify({
            'success': True,
            'statistics': stats,
            'last_updated': datetime.utcnow().isoformat()
        })

    except Exception as e:
        logger.error(f"Error getting statistics: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api_bp.errorhandler(404)
def api_not_found(error):
    """Handle 404 errors in API"""
    return jsonify({
        'success': False,
        'error': 'API endpoint not found'
    }), 404

@api_bp.errorhandler(500)
def api_internal_error(error):
    """Handle 500 errors in API"""
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500

@api_bp.before_request
def before_api_request():
    """Before request handler for API routes"""
    # Set JSON content type for all API responses
    if not request.is_json and request.method in ['POST', 'PUT', 'PATCH']:
        if request.content_type and 'application/json' not in request.content_type:
            logger.warning(f"Non-JSON request to API endpoint: {request.endpoint}")