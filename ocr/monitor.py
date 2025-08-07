"""
Quality and confidence scoring for OCR processing
"""
import re
from datetime import datetime, timedelta
from app import db
from models import Document, OCRStats
import logging

class OCRMonitor:
    """Monitors OCR processing quality and performance"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Quality indicators for medical documents
        self.medical_indicators = [
            r'\b(patient|diagnosis|treatment|medication|dosage|mg|ml|units)\b',
            r'\b(blood pressure|heart rate|temperature|weight|height)\b',
            r'\b(lab results?|laboratory|pathology|radiology)\b',
            r'\b(doctor|physician|nurse|provider|clinic|hospital)\b',
            r'\d{1,3}/\d{1,3}',  # Blood pressure readings
            r'\d+\.\d+\s*(mg|ml|units|mmol|g)',  # Medical measurements
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'  # Dates
        ]
        
        # Common OCR errors in medical text
        self.ocr_error_patterns = [
            r'[0O]{3,}',  # Multiple zeros/Os that might be OCR errors
            r'[1Il]{3,}',  # Multiple 1s/Is/ls
            r'[^\w\s.,;:()[\]{}/"\'!?@#$%^&*+=<>-]',  # Unusual characters
            r'\b[A-Z]{10,}\b',  # Very long uppercase strings (likely errors)
            r'\s{3,}',  # Multiple spaces
        ]
    
    def analyze_document_quality(self, document_id):
        """Analyze the quality of OCR text for a document"""
        document = Document.query.get(document_id)
        if not document or not document.ocr_text:
            return None
        
        text = document.ocr_text
        
        analysis = {
            'document_id': document_id,
            'text_length': len(text),
            'confidence_score': document.ocr_confidence or 0.0,
            'quality_indicators': {},
            'error_indicators': {},
            'overall_quality': 'unknown'
        }
        
        # Check for medical content indicators
        medical_matches = 0
        for pattern in self.medical_indicators:
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            if matches > 0:
                medical_matches += matches
        
        analysis['quality_indicators']['medical_terms'] = medical_matches
        analysis['quality_indicators']['has_medical_content'] = medical_matches > 0
        
        # Check for OCR errors
        total_errors = 0
        for pattern in self.ocr_error_patterns:
            errors = len(re.findall(pattern, text))
            total_errors += errors
        
        analysis['error_indicators']['ocr_errors'] = total_errors
        analysis['error_indicators']['error_density'] = total_errors / len(text) if len(text) > 0 else 0
        
        # Calculate overall quality
        quality_score = self._calculate_quality_score(analysis)
        analysis['quality_score'] = quality_score
        analysis['overall_quality'] = self._categorize_quality(quality_score)
        
        return analysis
    
    def _calculate_quality_score(self, analysis):
        """Calculate overall quality score from 0.0 to 1.0"""
        base_score = analysis['confidence_score']
        
        # Boost score for medical content
        if analysis['quality_indicators']['medical_terms'] > 0:
            medical_boost = min(0.2, analysis['quality_indicators']['medical_terms'] * 0.02)
            base_score += medical_boost
        
        # Reduce score for OCR errors
        error_penalty = min(0.3, analysis['error_indicators']['error_density'] * 10)
        base_score -= error_penalty
        
        # Text length factor (very short or very long texts might be problematic)
        text_length = analysis['text_length']
        if text_length < 50:
            base_score -= 0.1  # Too short
        elif text_length > 10000:
            base_score -= 0.1  # Too long, might have errors
        
        return max(0.0, min(1.0, base_score))
    
    def _categorize_quality(self, quality_score):
        """Categorize quality score into human-readable levels"""
        if quality_score >= 0.8:
            return 'high'
        elif quality_score >= 0.6:
            return 'medium'
        elif quality_score >= 0.4:
            return 'low'
        else:
            return 'very_low'
    
    def get_low_quality_documents(self, threshold=0.6, limit=50):
        """Get documents with quality scores below threshold"""
        documents = Document.query.filter(
            Document.ocr_confidence < threshold,
            Document.ocr_text.isnot(None)
        ).order_by(Document.ocr_confidence.asc()).limit(limit).all()
        
        return [self.analyze_document_quality(doc.id) for doc in documents]
    
    def update_ocr_stats(self):
        """Update global OCR statistics"""
        stats = OCRStats.query.first()
        if not stats:
            stats = OCRStats()
            db.session.add(stats)
        
        # Calculate current statistics
        total_docs = Document.query.count()
        processed_docs = Document.query.filter(Document.ocr_text.isnot(None)).count()
        
        # Calculate average confidence
        avg_confidence = db.session.query(db.func.avg(Document.ocr_confidence)).scalar() or 0.0
        
        # Calculate average processing time (simulated for now)
        # In a real implementation, you'd track actual processing times
        stats.total_documents = total_docs
        stats.processed_documents = processed_docs
        stats.average_confidence = avg_confidence
        stats.processing_time_avg = 15.0  # Average 15 seconds per document
        stats.last_updated = datetime.utcnow()
        
        db.session.commit()
        
        return {
            'total_documents': total_docs,
            'processed_documents': processed_docs,
            'processing_rate': (processed_docs / total_docs * 100) if total_docs > 0 else 0,
            'average_confidence': round(avg_confidence * 100, 1),
            'processing_time_avg': stats.processing_time_avg
        }
    
    def get_processing_queue_status(self):
        """Get status of documents pending OCR processing"""
        pending_docs = Document.query.filter(Document.ocr_text.is_(None)).count()
        
        # Get recent processing activity (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_processed = Document.query.filter(
            Document.processed_at >= week_ago,
            Document.ocr_text.isnot(None)
        ).count()
        
        return {
            'pending_documents': pending_docs,
            'recent_processed': recent_processed,
            'estimated_completion_time': pending_docs * 15  # 15 seconds per document
        }
    
    def get_confidence_distribution(self):
        """Get distribution of confidence scores"""
        # Query confidence ranges
        high_confidence = Document.query.filter(Document.ocr_confidence >= 0.8).count()
        medium_confidence = Document.query.filter(
            Document.ocr_confidence >= 0.6,
            Document.ocr_confidence < 0.8
        ).count()
        low_confidence = Document.query.filter(
            Document.ocr_confidence < 0.6,
            Document.ocr_confidence.isnot(None)
        ).count()
        
        total = high_confidence + medium_confidence + low_confidence
        
        if total == 0:
            return {'high': 0, 'medium': 0, 'low': 0}
        
        return {
            'high': round(high_confidence / total * 100, 1),
            'medium': round(medium_confidence / total * 100, 1),
            'low': round(low_confidence / total * 100, 1)
        }
    
    def identify_problematic_documents(self):
        """Identify documents that may need manual review"""
        problematic = []
        
        # Very low confidence documents
        low_confidence_docs = Document.query.filter(
            Document.ocr_confidence < 0.4,
            Document.ocr_text.isnot(None)
        ).limit(20).all()
        
        for doc in low_confidence_docs:
            analysis = self.analyze_document_quality(doc.id)
            if analysis:
                problematic.append({
                    'document': doc,
                    'reason': 'Low OCR confidence',
                    'confidence': doc.ocr_confidence,
                    'quality_score': analysis['quality_score']
                })
        
        # Documents with high error density
        all_docs = Document.query.filter(Document.ocr_text.isnot(None)).all()
        
        for doc in all_docs:
            analysis = self.analyze_document_quality(doc.id)
            if analysis and analysis['error_indicators']['error_density'] > 0.05:
                problematic.append({
                    'document': doc,
                    'reason': 'High OCR error density',
                    'confidence': doc.ocr_confidence,
                    'error_density': analysis['error_indicators']['error_density']
                })
        
        return sorted(problematic, key=lambda x: x.get('confidence', 0))
    
    def generate_quality_report(self):
        """Generate comprehensive quality report"""
        stats = self.update_ocr_stats()
        confidence_dist = self.get_confidence_distribution()
        queue_status = self.get_processing_queue_status()
        problematic_docs = self.identify_problematic_documents()
        
        return {
            'summary': stats,
            'confidence_distribution': confidence_dist,
            'queue_status': queue_status,
            'problematic_documents': len(problematic_docs),
            'recommendations': self._generate_recommendations(stats, confidence_dist)
        }
    
    def _generate_recommendations(self, stats, confidence_dist):
        """Generate recommendations based on OCR quality analysis"""
        recommendations = []
        
        if stats['processing_rate'] < 80:
            recommendations.append("Consider increasing OCR processing capacity")
        
        if confidence_dist['low'] > 20:
            recommendations.append("Review OCR settings - high percentage of low confidence documents")
        
        if stats['average_confidence'] < 70:
            recommendations.append("Document quality may be poor - consider image preprocessing")
        
        return recommendations

    def get_processing_dashboard(self):
        """Get comprehensive dashboard data for OCR processing"""
        try:
            # Get basic statistics
            stats = self.update_ocr_stats()
            
            # Get confidence distribution
            confidence_dist = self.get_confidence_distribution()
            
            # Get queue status
            queue_status = self.get_processing_queue_status()
            
            # Get problematic documents count
            problematic_docs = self.identify_problematic_documents()
            
            # Calculate additional metrics
            dashboard_data = {
                'overview': {
                    'total_documents': stats['total_documents'],
                    'processed_documents': stats['processed_documents'],
                    'pending_documents': queue_status['pending_documents'],
                    'processing_rate': stats['processing_rate']
                },
                'quality': {
                    'average_confidence': stats['average_confidence'],
                    'confidence_distribution': confidence_dist,
                    'problematic_count': len(problematic_docs)
                },
                'performance': {
                    'processing_time_avg': stats['processing_time_avg'],
                    'recent_processed': queue_status['recent_processed'],
                    'estimated_completion_time': queue_status['estimated_completion_time']
                },
                'recommendations': self._generate_recommendations(stats, confidence_dist)
            }
            
            return dashboard_data
            
        except Exception as e:
            self.logger.error(f"Error generating processing dashboard: {str(e)}")
            # Return safe default data
            return {
                'overview': {
                    'total_documents': 0,
                    'processed_documents': 0,
                    'pending_documents': 0,
                    'processing_rate': 0
                },
                'quality': {
                    'average_confidence': 0,
                    'confidence_distribution': {'high': 0, 'medium': 0, 'low': 0},
                    'problematic_count': 0
                },
                'performance': {
                    'processing_time_avg': 0,
                    'recent_processed': 0,
                    'estimated_completion_time': 0
                },
                'recommendations': []
            }
