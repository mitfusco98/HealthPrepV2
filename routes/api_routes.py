"""
API routes for AJAX requests and external integrations
Provides JSON endpoints for frontend interactions
"""
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
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

@api_bp.route('/screening-keywords/<int:screening_type_id>')
@login_required
def get_screening_keywords(screening_type_id):
    """Get keywords for a screening type"""
    try:
        screening_type = ScreeningType.query.get_or_404(screening_type_id)

        # Parse keywords
        keywords = []
        if screening_type.keywords:
            try:
                if screening_type.keywords.strip().startswith('['):
                    keywords = json.loads(screening_type.keywords)
                else:
                    keywords = [kw.strip() for kw in screening_type.keywords.split(',') if kw.strip()]
            except:
                keywords = [kw.strip() for kw in str(screening_type.keywords).split(',') if kw.strip()]

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
                result = engine.process_patient_screenings(patient_id, force_refresh=True)
                results.append(result)

            return jsonify({
                'success': True,
                'message': f'Refreshed screenings for {len(patient_ids)} patients',
                'results': results
            })

        elif screening_type_ids:
            # Selective refresh for specific screening types
            result = engine.selective_refresh(changed_screening_type_ids=screening_type_ids)

            return jsonify({
                'success': True,
                'message': f'Refreshed {result["processed"]} screenings',
                'result': result
            })

        else:
            # Full refresh
            result = engine.refresh_all_screenings()

            return jsonify({
                'success': True,
                'message': f'Refreshed screenings for {result["processed"]} patients',
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

        matcher = DocumentMatcher()
        # DocumentMatcher doesn't have get_keyword_suggestions, so we'll use fuzzy_matching utils
        from utils.fuzzy_matching import medical_matcher
        suggestions = medical_matcher.find_related_terms(partial)[:10]

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

@api_bp.route('/condition-suggestions')
@login_required
def get_condition_suggestions():
    """Get condition suggestions for trigger conditions"""
    try:
        partial = request.args.get('q', '').strip()
        if not partial:
            return jsonify({'suggestions': []})

        criteria = EligibilityCriteria()
        suggestions = criteria.get_condition_suggestions(partial, limit=10)

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

        if enabled_filters:
            filtered_text = phi_filter.filter_phi(test_text)
            report = phi_filter.test_phi_filter(test_text)
        else:
            filtered_text = phi_filter.filter_phi(test_text)
            report = phi_filter.test_phi_filter(test_text)

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
                    ScreeningType.description.contains(query),
                    ScreeningType.keywords.contains(query)
                )
            ).limit(limit).all()

            results['screenings'] = [
                {
                    'id': s.id,
                    'name': s.name,
                    'description': s.description,
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