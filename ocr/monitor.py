"""
OCR quality monitoring and confidence scoring
Provides analytics and monitoring for OCR processing
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from models import Document, OCRProcessing, db
from sqlalchemy import func, and_

class OCRMonitor:
    """Monitors OCR processing quality and performance"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def get_processing_dashboard(self) -> Dict[str, Any]:
        """Get comprehensive OCR processing dashboard data"""
        try:
            dashboard_data = {
                "overview": self._get_overview_stats(),
                "quality_metrics": self._get_quality_metrics(),
                "recent_activity": self._get_recent_activity(),
                "low_confidence_documents": self._get_low_confidence_documents(),
                "processing_errors": self._get_recent_errors(),
                "performance_trends": self._get_performance_trends()
            }
            
            return dashboard_data
            
        except Exception as e:
            self.logger.error(f"Error generating OCR dashboard: {str(e)}")
            return {"error": str(e)}
    
    def _get_overview_stats(self) -> Dict[str, Any]:
        """Get basic overview statistics"""
        try:
            total_documents = Document.query.count()
            processed_documents = Document.query.filter_by(is_processed=True).count()
            pending_documents = total_documents - processed_documents
            
            # Recent processing (last 24 hours)
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            recent_processed = OCRProcessing.query.filter(
                OCRProcessing.processing_start >= recent_cutoff
            ).count()
            
            return {
                "total_documents": total_documents,
                "processed_documents": processed_documents,
                "pending_documents": pending_documents,
                "processing_rate": (processed_documents / total_documents * 100) if total_documents > 0 else 0,
                "recent_24h": recent_processed
            }
            
        except Exception as e:
            self.logger.error(f"Error getting overview stats: {str(e)}")
            return {}
    
    def _get_quality_metrics(self) -> Dict[str, Any]:
        """Get OCR quality metrics"""
        try:
            # Confidence score statistics
            confidence_stats = db.session.query(
                func.avg(Document.ocr_confidence).label('avg_confidence'),
                func.min(Document.ocr_confidence).label('min_confidence'),
                func.max(Document.ocr_confidence).label('max_confidence'),
                func.count(Document.id).label('total_with_confidence')
            ).filter(
                and_(Document.ocr_confidence.isnot(None), Document.ocr_confidence > 0)
            ).first()
            
            # Confidence distribution
            confidence_ranges = [
                ("High (80-100%)", 80, 100),
                ("Medium (60-79%)", 60, 79),
                ("Low (40-59%)", 40, 59),
                ("Very Low (0-39%)", 0, 39)
            ]
            
            confidence_distribution = {}
            for label, min_conf, max_conf in confidence_ranges:
                count = Document.query.filter(
                    and_(
                        Document.ocr_confidence >= min_conf,
                        Document.ocr_confidence <= max_conf
                    )
                ).count()
                confidence_distribution[label] = count
            
            return {
                "average_confidence": round(confidence_stats.avg_confidence or 0, 2),
                "min_confidence": round(confidence_stats.min_confidence or 0, 2),
                "max_confidence": round(confidence_stats.max_confidence or 0, 2),
                "confidence_distribution": confidence_distribution,
                "total_scored": confidence_stats.total_with_confidence or 0
            }
            
        except Exception as e:
            self.logger.error(f"Error getting quality metrics: {str(e)}")
            return {}
    
    def _get_recent_activity(self) -> List[Dict[str, Any]]:
        """Get recent OCR processing activity"""
        try:
            recent_cutoff = datetime.utcnow() - timedelta(days=7)
            
            recent_processing = db.session.query(
                OCRProcessing,
                Document.filename,
                Document.document_type
            ).join(
                Document, OCRProcessing.document_id == Document.id
            ).filter(
                OCRProcessing.processing_start >= recent_cutoff
            ).order_by(
                OCRProcessing.processing_start.desc()
            ).limit(20).all()
            
            activity_list = []
            for ocr_proc, filename, doc_type in recent_processing:
                activity_list.append({
                    "document_id": ocr_proc.document_id,
                    "filename": filename,
                    "document_type": doc_type,
                    "processing_start": ocr_proc.processing_start,
                    "processing_end": ocr_proc.processing_end,
                    "success": ocr_proc.success,
                    "confidence": round(ocr_proc.confidence_score or 0, 2),
                    "error_message": ocr_proc.error_message
                })
            
            return activity_list
            
        except Exception as e:
            self.logger.error(f"Error getting recent activity: {str(e)}")
            return []
    
    def _get_low_confidence_documents(self) -> List[Dict[str, Any]]:
        """Get documents with low OCR confidence scores"""
        try:
            low_confidence_threshold = 60  # Below 60% confidence
            
            low_confidence_docs = db.session.query(
                Document.id,
                Document.filename,
                Document.document_type,
                Document.ocr_confidence,
                Document.date_created,
                Document.patient_id
            ).filter(
                and_(
                    Document.ocr_confidence.isnot(None),
                    Document.ocr_confidence < low_confidence_threshold
                )
            ).order_by(
                Document.ocr_confidence.asc()
            ).limit(15).all()
            
            low_confidence_list = []
            for doc in low_confidence_docs:
                low_confidence_list.append({
                    "document_id": doc.id,
                    "filename": doc.filename,
                    "document_type": doc.document_type,
                    "confidence": round(doc.ocr_confidence or 0, 2),
                    "date_created": doc.date_created,
                    "patient_id": doc.patient_id
                })
            
            return low_confidence_list
            
        except Exception as e:
            self.logger.error(f"Error getting low confidence documents: {str(e)}")
            return []
    
    def _get_recent_errors(self) -> List[Dict[str, Any]]:
        """Get recent OCR processing errors"""
        try:
            recent_cutoff = datetime.utcnow() - timedelta(days=7)
            
            error_processing = db.session.query(
                OCRProcessing,
                Document.filename,
                Document.document_type
            ).join(
                Document, OCRProcessing.document_id == Document.id
            ).filter(
                and_(
                    OCRProcessing.success == False,
                    OCRProcessing.processing_start >= recent_cutoff
                )
            ).order_by(
                OCRProcessing.processing_start.desc()
            ).limit(10).all()
            
            error_list = []
            for ocr_proc, filename, doc_type in error_processing:
                error_list.append({
                    "document_id": ocr_proc.document_id,
                    "filename": filename,
                    "document_type": doc_type,
                    "processing_start": ocr_proc.processing_start,
                    "error_message": ocr_proc.error_message
                })
            
            return error_list
            
        except Exception as e:
            self.logger.error(f"Error getting recent errors: {str(e)}")
            return []
    
    def _get_performance_trends(self) -> Dict[str, Any]:
        """Get OCR performance trends over time"""
        try:
            # Get daily processing counts for the last 30 days
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            daily_stats = db.session.query(
                func.date(OCRProcessing.processing_start).label('date'),
                func.count(OCRProcessing.id).label('total_processed'),
                func.sum(func.case([(OCRProcessing.success == True, 1)], else_=0)).label('successful'),
                func.avg(OCRProcessing.confidence_score).label('avg_confidence')
            ).filter(
                OCRProcessing.processing_start >= thirty_days_ago
            ).group_by(
                func.date(OCRProcessing.processing_start)
            ).order_by(
                func.date(OCRProcessing.processing_start)
            ).all()
            
            trend_data = []
            for stat in daily_stats:
                trend_data.append({
                    "date": stat.date.isoformat(),
                    "total_processed": stat.total_processed or 0,
                    "successful": stat.successful or 0,
                    "success_rate": (stat.successful / stat.total_processed * 100) if stat.total_processed > 0 else 0,
                    "avg_confidence": round(stat.avg_confidence or 0, 2)
                })
            
            return {
                "daily_trends": trend_data,
                "trend_period_days": 30
            }
            
        except Exception as e:
            self.logger.error(f"Error getting performance trends: {str(e)}")
            return {}
    
    def get_document_quality_assessment(self, document_id: int) -> Dict[str, Any]:
        """Get detailed quality assessment for a specific document"""
        try:
            document = Document.query.get(document_id)
            if not document:
                return {"error": "Document not found"}
            
            ocr_processing = OCRProcessing.query.filter_by(document_id=document_id).first()
            
            # Basic quality metrics
            quality_assessment = {
                "document_id": document_id,
                "filename": document.filename,
                "is_processed": document.is_processed,
                "ocr_confidence": document.ocr_confidence,
                "text_length": len(document.ocr_text) if document.ocr_text else 0,
                "processing_info": None,
                "quality_flags": [],
                "recommendations": []
            }
            
            if ocr_processing:
                processing_duration = None
                if ocr_processing.processing_end and ocr_processing.processing_start:
                    processing_duration = (ocr_processing.processing_end - ocr_processing.processing_start).total_seconds()
                
                quality_assessment["processing_info"] = {
                    "success": ocr_processing.success,
                    "processing_start": ocr_processing.processing_start,
                    "processing_end": ocr_processing.processing_end,
                    "processing_duration_seconds": processing_duration,
                    "error_message": ocr_processing.error_message
                }
            
            # Quality flags and recommendations
            if document.ocr_confidence:
                if document.ocr_confidence < 40:
                    quality_assessment["quality_flags"].append("Very low confidence score")
                    quality_assessment["recommendations"].append("Consider manual review or document reprocessing")
                elif document.ocr_confidence < 60:
                    quality_assessment["quality_flags"].append("Low confidence score")
                    quality_assessment["recommendations"].append("Review extracted text for accuracy")
                elif document.ocr_confidence > 90:
                    quality_assessment["quality_flags"].append("High confidence score")
            
            if document.ocr_text:
                if len(document.ocr_text) < 50:
                    quality_assessment["quality_flags"].append("Very short extracted text")
                    quality_assessment["recommendations"].append("Verify document contains readable text")
                
                # Check for common OCR artifacts
                common_artifacts = ['|||', '~~~', '###', 'lll', 'III']
                if any(artifact in document.ocr_text for artifact in common_artifacts):
                    quality_assessment["quality_flags"].append("Possible OCR artifacts detected")
                    quality_assessment["recommendations"].append("Review for scanning artifacts or poor image quality")
            
            return quality_assessment
            
        except Exception as e:
            self.logger.error(f"Error assessing document quality for {document_id}: {str(e)}")
            return {"error": str(e)}
    
    def generate_quality_report(self, days: int = 30) -> Dict[str, Any]:
        """Generate a comprehensive OCR quality report"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            report = {
                "report_period_days": days,
                "generated_at": datetime.utcnow().isoformat(),
                "summary": {},
                "quality_breakdown": {},
                "issues_identified": [],
                "recommendations": []
            }
            
            # Summary statistics
            total_processed = OCRProcessing.query.filter(
                OCRProcessing.processing_start >= cutoff_date
            ).count()
            
            successful = OCRProcessing.query.filter(
                and_(
                    OCRProcessing.processing_start >= cutoff_date,
                    OCRProcessing.success == True
                )
            ).count()
            
            avg_confidence = db.session.query(
                func.avg(OCRProcessing.confidence_score)
            ).filter(
                and_(
                    OCRProcessing.processing_start >= cutoff_date,
                    OCRProcessing.success == True
                )
            ).scalar() or 0
            
            report["summary"] = {
                "total_processed": total_processed,
                "successful": successful,
                "failed": total_processed - successful,
                "success_rate": (successful / total_processed * 100) if total_processed > 0 else 0,
                "average_confidence": round(avg_confidence, 2)
            }
            
            # Quality breakdown by confidence ranges
            confidence_ranges = [
                ("excellent", 90, 100),
                ("good", 70, 89),
                ("fair", 50, 69),
                ("poor", 0, 49)
            ]
            
            quality_breakdown = {}
            for label, min_conf, max_conf in confidence_ranges:
                count = db.session.query(func.count(Document.id)).filter(
                    and_(
                        Document.ocr_confidence >= min_conf,
                        Document.ocr_confidence <= max_conf,
                        Document.date_created >= cutoff_date
                    )
                ).scalar() or 0
                quality_breakdown[label] = count
            
            report["quality_breakdown"] = quality_breakdown
            
            # Identify issues and recommendations
            poor_quality_count = quality_breakdown.get("poor", 0)
            if poor_quality_count > 0:
                report["issues_identified"].append(f"{poor_quality_count} documents with poor OCR quality")
                report["recommendations"].append("Review scanning processes and document quality")
            
            if report["summary"]["success_rate"] < 95:
                report["issues_identified"].append("OCR success rate below 95%")
                report["recommendations"].append("Investigate processing errors and system performance")
            
            if report["summary"]["average_confidence"] < 75:
                report["issues_identified"].append("Average confidence score below 75%")
                report["recommendations"].append("Consider document quality improvements or OCR parameter tuning")
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating quality report: {str(e)}")
            return {"error": str(e)}
