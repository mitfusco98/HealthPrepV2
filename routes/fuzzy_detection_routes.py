"""
Fuzzy Detection API Routes
Provides endpoints for testing and using advanced fuzzy keyword matching
"""
import logging
from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from core.fuzzy_detection import FuzzyDetectionEngine
from core.matcher import DocumentMatcher
from core.engine import ScreeningEngine
from models import ScreeningType, Document, db

# Create blueprint
fuzzy_bp = Blueprint('fuzzy', __name__, url_prefix='/fuzzy')

# Initialize engines
fuzzy_engine = FuzzyDetectionEngine()
document_matcher = DocumentMatcher()
screening_engine = ScreeningEngine()
logger = logging.getLogger(__name__)

@fuzzy_bp.route('/test')
@login_required
def fuzzy_test_page():
    """Fuzzy detection testing interface"""
    try:
        # Get sample screening types for testing
        screening_types = ScreeningType.query.filter_by(is_active=True).limit(10).all()
        
        return render_template('fuzzy/test.html', 
                             screening_types=screening_types)
        
    except Exception as e:
        logger.error(f"Error loading fuzzy test page: {str(e)}")
        flash('Error loading fuzzy detection test page', 'error')
        return render_template('error/500.html'), 500

@fuzzy_bp.route('/api/match-keywords', methods=['POST'])
@login_required
def api_match_keywords():
    """API endpoint for fuzzy keyword matching"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        text = data.get('text', '')
        keywords = data.get('keywords', [])
        threshold = float(data.get('threshold', 0.7))
        
        if not text or not keywords:
            return jsonify({'error': 'Text and keywords are required'}), 400
        
        # Perform fuzzy matching
        matches = fuzzy_engine.fuzzy_match_keywords(text, keywords, threshold)
        
        # Format results
        results = []
        for keyword, confidence, matched_text in matches:
            results.append({
                'keyword': keyword,
                'confidence': round(confidence, 3),
                'matched_text': matched_text,
                'confidence_percentage': round(confidence * 100, 1)
            })
        
        return jsonify({
            'success': True,
            'matches': results,
            'total_matches': len(results),
            'text_analyzed': text[:100] + '...' if len(text) > 100 else text
        })
        
    except Exception as e:
        logger.error(f"Error in fuzzy keyword matching: {str(e)}")
        return jsonify({'error': 'Keyword matching failed'}), 500

@fuzzy_bp.route('/api/analyze-document', methods=['POST'])
@login_required
def api_analyze_document():
    """API endpoint for document content analysis"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        text = data.get('text', '')
        filename = data.get('filename', '')
        
        if not text and not filename:
            return jsonify({'error': 'Text or filename is required'}), 400
        
        # Combine filename and text
        full_text = f"{filename} {text}".strip()
        
        # Extract semantic terms
        semantic_terms = fuzzy_engine.extract_semantic_terms(full_text)
        
        # Get keyword suggestions
        keyword_suggestions = fuzzy_engine.suggest_keywords(full_text)
        
        # Normalize text for display
        normalized_text = fuzzy_engine._normalize_text(full_text)
        
        return jsonify({
            'success': True,
            'analysis': {
                'semantic_terms': semantic_terms,
                'keyword_suggestions': keyword_suggestions,
                'normalized_text': normalized_text,
                'original_text': full_text[:200] + '...' if len(full_text) > 200 else full_text,
                'text_complexity': len(full_text.split()) if full_text else 0,
                'has_medical_content': bool(semantic_terms.get('medical_terms'))
            }
        })
        
    except Exception as e:
        logger.error(f"Error in document analysis: {str(e)}")
        return jsonify({'error': 'Document analysis failed'}), 500

@fuzzy_bp.route('/api/test-separator-matching', methods=['POST'])
@login_required
def api_test_separator_matching():
    """Test fuzzy matching with different separators"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        base_keyword = data.get('keyword', '')
        test_texts = data.get('test_texts', [])
        
        if not base_keyword or not test_texts:
            return jsonify({'error': 'Keyword and test texts are required'}), 400
        
        # Generate keyword variations
        keyword_variations = fuzzy_engine._get_keyword_variations(base_keyword)
        
        # Test each text against the keyword
        results = []
        for text in test_texts:
            matches = fuzzy_engine.fuzzy_match_keywords(text, [base_keyword], threshold=0.5)
            
            result = {
                'text': text,
                'normalized_text': fuzzy_engine._normalize_text(text),
                'matches': matches,
                'has_match': len(matches) > 0,
                'best_confidence': matches[0][1] if matches else 0.0
            }
            results.append(result)
        
        return jsonify({
            'success': True,
            'base_keyword': base_keyword,
            'keyword_variations': keyword_variations,
            'test_results': results,
            'summary': {
                'total_tests': len(test_texts),
                'successful_matches': len([r for r in results if r['has_match']]),
                'average_confidence': sum(r['best_confidence'] for r in results) / len(results) if results else 0
            }
        })
        
    except Exception as e:
        logger.error(f"Error in separator matching test: {str(e)}")
        return jsonify({'error': 'Separator matching test failed'}), 500

@fuzzy_bp.route('/api/optimize-keywords/<int:screening_type_id>', methods=['POST'])
@login_required
def api_optimize_keywords(screening_type_id):
    """Optimize keywords for a specific screening type"""
    try:
        if not current_user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        # Analyze keywords using the screening engine
        analysis = screening_engine.analyze_screening_keywords(screening_type_id)
        
        if not analysis:
            return jsonify({'error': 'Screening type not found'}), 404
        
        return jsonify({
            'success': True,
            'analysis': analysis
        })
        
    except Exception as e:
        logger.error(f"Error optimizing keywords: {str(e)}")
        return jsonify({'error': 'Keyword optimization failed'}), 500

@fuzzy_bp.route('/api/suggest-keywords', methods=['POST'])
@login_required
def api_suggest_keywords():
    """Get keyword suggestions based on text content"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        text = data.get('text', '')
        existing_keywords = data.get('existing_keywords', [])
        
        if not text:
            return jsonify({'error': 'Text is required'}), 400
        
        # Get keyword suggestions
        suggestions = fuzzy_engine.suggest_keywords(text, existing_keywords)
        
        # Validate relevance of suggestions
        validated_suggestions = []
        for suggestion in suggestions:
            relevance = fuzzy_engine.validate_keyword_relevance(suggestion, [text])
            validated_suggestions.append({
                'keyword': suggestion,
                'relevance': round(relevance, 3),
                'recommended': relevance > 0.5
            })
        
        # Sort by relevance
        validated_suggestions.sort(key=lambda x: x['relevance'], reverse=True)
        
        return jsonify({
            'success': True,
            'suggestions': validated_suggestions,
            'text_analyzed': text[:100] + '...' if len(text) > 100 else text,
            'existing_keywords': existing_keywords
        })
        
    except Exception as e:
        logger.error(f"Error getting keyword suggestions: {str(e)}")
        return jsonify({'error': 'Keyword suggestion failed'}), 500

@fuzzy_bp.route('/api/validate-keywords', methods=['POST'])
@login_required
def api_validate_keywords():
    """Validate keyword effectiveness across documents"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        keywords = data.get('keywords', [])
        document_texts = data.get('document_texts', [])
        
        if not keywords or not document_texts:
            return jsonify({'error': 'Keywords and document texts are required'}), 400
        
        # Validate each keyword
        validation_results = []
        for keyword in keywords:
            relevance = fuzzy_engine.validate_keyword_relevance(keyword, document_texts)
            
            # Get sample matches
            sample_matches = []
            for text in document_texts[:3]:  # Show first 3 examples
                matches = fuzzy_engine.fuzzy_match_keywords(text, [keyword], threshold=0.5)
                if matches:
                    sample_matches.append({
                        'text_preview': text[:50] + '...' if len(text) > 50 else text,
                        'confidence': matches[0][1],
                        'matched_text': matches[0][2]
                    })
            
            validation_results.append({
                'keyword': keyword,
                'relevance': round(relevance, 3),
                'effectiveness': 'High' if relevance > 0.7 else 'Medium' if relevance > 0.4 else 'Low',
                'sample_matches': sample_matches
            })
        
        return jsonify({
            'success': True,
            'validation_results': validation_results,
            'documents_analyzed': len(document_texts),
            'summary': {
                'high_effectiveness': len([r for r in validation_results if r['relevance'] > 0.7]),
                'medium_effectiveness': len([r for r in validation_results if 0.4 < r['relevance'] <= 0.7]),
                'low_effectiveness': len([r for r in validation_results if r['relevance'] <= 0.4])
            }
        })
        
    except Exception as e:
        logger.error(f"Error validating keywords: {str(e)}")
        return jsonify({'error': 'Keyword validation failed'}), 500

@fuzzy_bp.route('/api/batch-optimize', methods=['POST'])
@login_required
def api_batch_optimize():
    """Optimize keywords for all screening types"""
    try:
        if not current_user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        # Run optimization for all screening types
        optimization_results = screening_engine.optimize_all_screening_keywords()
        
        return jsonify({
            'success': True,
            'optimization_results': optimization_results,
            'total_screening_types': len(optimization_results),
            'timestamp': str(db.func.current_timestamp())
        })
        
    except Exception as e:
        logger.error(f"Error in batch optimization: {str(e)}")
        return jsonify({'error': 'Batch optimization failed'}), 500

# Error handlers
@fuzzy_bp.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@fuzzy_bp.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500