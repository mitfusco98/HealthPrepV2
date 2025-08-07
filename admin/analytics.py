"""
Hours saved, compliance gaps closed analytics
"""
from datetime import datetime, timedelta
from app import db
from models import AdminLog, Screening, Document, Patient, ScreeningType
import json
import logging

class HealthPrepAnalytics:
    """Analytics for measuring HealthPrep system impact"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Time savings assumptions (in minutes)
        self.time_savings = {
            'prep_sheet_generation': 15,  # vs manual prep
            'document_processing': 5,     # vs manual filing
            'screening_identification': 10, # vs manual review
            'automated_matching': 8       # vs manual matching
        }
    
    def calculate_time_savings(self, days=30):
        """Calculate total time saved in the specified period"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Count automated activities
        prep_sheets = AdminLog.query.filter(
            AdminLog.action == 'prep_sheet_generated',
            AdminLog.timestamp >= cutoff_date
        ).count()
        
        documents_processed = Document.query.filter(
            Document.processed_at >= cutoff_date,
            Document.content.isnot(None)
        ).count()
        
        screenings_updated = AdminLog.query.filter(
            AdminLog.action == 'screenings_refreshed',
            AdminLog.timestamp >= cutoff_date
        ).count()
        
        # Calculate time saved
        total_minutes_saved = (
            prep_sheets * self.time_savings['prep_sheet_generation'] +
            documents_processed * self.time_savings['document_processing'] +
            screenings_updated * self.time_savings['screening_identification']
        )
        
        return {
            'total_minutes_saved': total_minutes_saved,
            'total_hours_saved': round(total_minutes_saved / 60, 2),
            'breakdown': {
                'prep_sheets_generated': prep_sheets,
                'documents_processed': documents_processed,
                'screenings_updated': screenings_updated
            },
            'period_days': days
        }
    
    def calculate_compliance_gaps_closed(self, days=30):
        """Calculate screening compliance gaps identified and closed"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Count screenings moved from 'due' to 'complete'
        compliance_improvements = AdminLog.query.filter(
            AdminLog.action.like('%screening%'),
            AdminLog.timestamp >= cutoff_date
        ).count()
        
        # Count currently due screenings (gaps still open)
        open_gaps = Screening.query.filter_by(status='due').count()
        
        # Count screenings due soon (preventive identification)
        due_soon = Screening.query.filter_by(status='due_soon').count()
        
        # Count completed screenings in period
        recent_completions = Screening.query.filter(
            Screening.status == 'complete',
            Screening.updated_at >= cutoff_date
        ).count()
        
        return {
            'gaps_identified': open_gaps + due_soon,
            'gaps_closed': recent_completions,
            'preventive_identification': due_soon,
            'compliance_rate': self._calculate_compliance_rate(),
            'period_days': days
        }
    
    def _calculate_compliance_rate(self):
        """Calculate overall screening compliance rate"""
        total_screenings = Screening.query.count()
        complete_screenings = Screening.query.filter_by(status='complete').count()
        
        if total_screenings == 0:
            return 0.0
        
        return round((complete_screenings / total_screenings) * 100, 1)
    
    def get_roi_metrics(self, days=30):
        """Calculate return on investment metrics"""
        time_saved = self.calculate_time_savings(days)
        compliance_data = self.calculate_compliance_gaps_closed(days)
        
        # Estimate cost savings (assuming $30/hour for medical assistant time)
        hourly_rate = 30
        cost_savings = time_saved['total_hours_saved'] * hourly_rate
        
        # Estimate value of compliance improvements
        # Assume each gap closed prevents a potential issue worth $500
        compliance_value = compliance_data['gaps_closed'] * 500
        
        return {
            'time_savings': time_saved,
            'compliance_improvements': compliance_data,
            'financial_impact': {
                'labor_cost_savings': round(cost_savings, 2),
                'compliance_value': compliance_value,
                'total_value': round(cost_savings + compliance_value, 2)
            },
            'efficiency_metrics': {
                'documents_per_hour': self._calculate_processing_efficiency(),
                'average_prep_time': 10,  # Estimated 10 seconds per prep sheet
                'accuracy_rate': self._calculate_accuracy_rate()
            }
        }
    
    def _calculate_processing_efficiency(self):
        """Calculate document processing efficiency"""
        # Get processing stats from last 24 hours
        yesterday = datetime.utcnow() - timedelta(hours=24)
        
        docs_processed = Document.query.filter(
            Document.processed_at >= yesterday,
            Document.content.isnot(None)
        ).count()
        
        # Assume 24 hours of potential processing time
        return round(docs_processed / 24, 2) if docs_processed > 0 else 0
    
    def _calculate_accuracy_rate(self):
        """Calculate system accuracy rate"""
        # Use OCR confidence as a proxy for accuracy
        avg_confidence = db.session.query(
            db.func.avg(Document.ocr_confidence)
        ).scalar()
        
        return round(avg_confidence * 100, 1) if avg_confidence else 85.0
    
    def get_usage_statistics(self, days=30):
        """Get system usage statistics"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # User activity
        active_users = db.session.query(
            db.func.count(db.distinct(AdminLog.user_id))
        ).filter(AdminLog.timestamp >= cutoff_date).scalar()
        
        # Document activity
        new_documents = Document.query.filter(
            Document.created_at >= cutoff_date
        ).count()
        
        # Patient activity
        new_patients = Patient.query.filter(
            Patient.created_at >= cutoff_date
        ).count()
        
        # Screening activity
        screening_updates = AdminLog.query.filter(
            AdminLog.action.like('%screening%'),
            AdminLog.timestamp >= cutoff_date
        ).count()
        
        return {
            'active_users': active_users,
            'new_documents': new_documents,
            'new_patients': new_patients,
            'screening_updates': screening_updates,
            'total_activities': AdminLog.query.filter(
                AdminLog.timestamp >= cutoff_date
            ).count(),
            'period_days': days
        }
    
    def generate_executive_summary(self, days=30):
        """Generate executive summary for stakeholders"""
        roi_data = self.get_roi_metrics(days)
        usage_data = self.get_usage_statistics(days)
        
        summary = {
            'reporting_period': f"Last {days} days",
            'key_metrics': {
                'hours_saved': roi_data['time_savings']['total_hours_saved'],
                'cost_savings': roi_data['financial_impact']['labor_cost_savings'],
                'compliance_gaps_closed': roi_data['compliance_improvements']['gaps_closed'],
                'documents_processed': usage_data['new_documents'],
                'system_accuracy': roi_data['efficiency_metrics']['accuracy_rate']
            },
            'highlights': self._generate_highlights(roi_data, usage_data),
            'recommendations': self._generate_recommendations(roi_data, usage_data)
        }
        
        return summary
    
    def _generate_highlights(self, roi_data, usage_data):
        """Generate key highlights for executive summary"""
        highlights = []
        
        hours_saved = roi_data['time_savings']['total_hours_saved']
        if hours_saved > 0:
            highlights.append(f"Saved {hours_saved} hours of manual work")
        
        cost_savings = roi_data['financial_impact']['labor_cost_savings']
        if cost_savings > 0:
            highlights.append(f"Generated ${cost_savings:,.2f} in labor cost savings")
        
        gaps_closed = roi_data['compliance_improvements']['gaps_closed']
        if gaps_closed > 0:
            highlights.append(f"Closed {gaps_closed} compliance gaps")
        
        accuracy = roi_data['efficiency_metrics']['accuracy_rate']
        if accuracy >= 90:
            highlights.append(f"Maintained {accuracy}% system accuracy")
        
        return highlights
    
    def _generate_recommendations(self, roi_data, usage_data):
        """Generate recommendations based on analytics"""
        recommendations = []
        
        # Check compliance rate
        compliance_rate = roi_data['compliance_improvements']['compliance_rate']
        if compliance_rate < 80:
            recommendations.append("Focus on improving screening compliance rates")
        
        # Check accuracy
        accuracy = roi_data['efficiency_metrics']['accuracy_rate']
        if accuracy < 85:
            recommendations.append("Review OCR processing quality and settings")
        
        # Check usage
        if usage_data['active_users'] < 5:
            recommendations.append("Increase user adoption through training")
        
        # Check processing efficiency
        efficiency = roi_data['efficiency_metrics']['documents_per_hour']
        if efficiency < 10:
            recommendations.append("Optimize document processing workflow")
        
        return recommendations
    
    def export_analytics_report(self, days=30):
        """Export comprehensive analytics report"""
        report = {
            'report_generated': datetime.utcnow().isoformat(),
            'reporting_period_days': days,
            'executive_summary': self.generate_executive_summary(days),
            'detailed_metrics': {
                'time_savings': self.calculate_time_savings(days),
                'compliance_gaps': self.calculate_compliance_gaps_closed(days),
                'roi_metrics': self.get_roi_metrics(days),
                'usage_statistics': self.get_usage_statistics(days)
            },
            'system_performance': {
                'total_patients': Patient.query.count(),
                'total_documents': Document.query.count(),
                'total_screenings': Screening.query.count(),
                'active_screening_types': ScreeningType.query.filter_by(is_active=True).count()
            }
        }
        
        return report
    
    def get_trend_analysis(self, weeks=4):
        """Analyze trends over multiple weeks"""
        trends = []
        
        for week in range(weeks):
            start_date = datetime.utcnow() - timedelta(weeks=week+1)
            end_date = datetime.utcnow() - timedelta(weeks=week)
            
            week_data = {
                'week': week + 1,
                'start_date': start_date.date(),
                'end_date': end_date.date(),
                'metrics': self.get_roi_metrics(7)  # 7 days per week
            }
            
            trends.append(week_data)
        
        return trends
