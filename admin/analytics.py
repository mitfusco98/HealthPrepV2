"""
Hours saved, compliance gaps closed analytics
Provides ROI and performance metrics for the admin dashboard
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy import func
from app import db
from models import Patient, Screening, Document, AdminLog

logger = logging.getLogger(__name__)

def calculate_hours_saved(days=30):
    """Calculate estimated hours saved by the system"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Base calculations
    patients_processed = Patient.query.count()
    documents_processed = Document.query.filter(
        Document.upload_date >= cutoff_date,
        Document.ocr_processed == True
    ).count()
    
    screenings_automated = Screening.query.filter(
        Screening.updated_at >= cutoff_date
    ).count()
    
    # Time savings estimates (in minutes)
    time_per_patient_prep = 10  # Manual prep sheet creation
    time_per_document_review = 2  # Manual document review
    time_per_screening_check = 1  # Manual screening status check
    
    total_minutes_saved = (
        patients_processed * time_per_patient_prep +
        documents_processed * time_per_document_review +
        screenings_automated * time_per_screening_check
    )
    
    hours_saved = total_minutes_saved / 60
    
    return round(hours_saved, 1)

class HealthcareAnalytics:
    """Provides comprehensive analytics for healthcare operations"""
    
    def __init__(self):
        pass
    
    def get_efficiency_metrics(self, days=30):
        """Calculate efficiency metrics for the specified period"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Document processing efficiency
        total_docs = Document.query.filter(Document.upload_date >= cutoff_date).count()
        processed_docs = Document.query.filter(
            Document.upload_date >= cutoff_date,
            Document.ocr_processed == True
        ).count()
        
        processing_rate = (processed_docs / total_docs * 100) if total_docs > 0 else 0
        
        # Screening completion rates
        total_screenings = Screening.query.count()
        complete_screenings = Screening.query.filter_by(status='complete').count()
        due_screenings = Screening.query.filter_by(status='due').count()
        
        completion_rate = (complete_screenings / total_screenings * 100) if total_screenings > 0 else 0
        
        # Average confidence scores
        avg_confidence = db.session.query(func.avg(Document.ocr_confidence)).filter(
            Document.ocr_processed == True,
            Document.ocr_confidence > 0
        ).scalar() or 0
        
        return {
            'document_processing_rate': round(processing_rate, 1),
            'screening_completion_rate': round(completion_rate, 1),
            'average_ocr_confidence': round(float(avg_confidence), 2),
            'total_documents_period': total_docs,
            'processed_documents_period': processed_docs,
            'total_screenings': total_screenings,
            'due_screenings': due_screenings
        }
    
    def calculate_roi_metrics(self, days=30):
        """Calculate return on investment metrics"""
        hours_saved = calculate_hours_saved(days)
        
        # Assumptions for ROI calculation
        average_hourly_wage = 25  # Average MA/nurse wage
        prep_sheets_generated = Patient.query.count()
        
        # Calculate cost savings
        labor_cost_saved = hours_saved * average_hourly_wage
        cost_per_prep_sheet = labor_cost_saved / prep_sheets_generated if prep_sheets_generated > 0 else 0
        
        # Calculate productivity gains
        manual_time_per_prep = 10  # minutes
        automated_time_per_prep = 2  # minutes
        time_reduction_percentage = ((manual_time_per_prep - automated_time_per_prep) / manual_time_per_prep) * 100
        
        return {
            'hours_saved': hours_saved,
            'labor_cost_saved': round(labor_cost_saved, 2),
            'cost_per_prep_sheet': round(cost_per_prep_sheet, 2),
            'time_reduction_percentage': round(time_reduction_percentage, 1),
            'prep_sheets_generated': prep_sheets_generated,
            'period_days': days
        }
    
    def get_compliance_metrics(self):
        """Calculate compliance and quality metrics"""
        # Screening compliance
        total_screenings = Screening.query.count()
        due_screenings = Screening.query.filter_by(status='due').count()
        overdue_screenings = Screening.query.filter(
            Screening.status == 'due',
            Screening.next_due < datetime.utcnow()
        ).count()
        
        compliance_rate = ((total_screenings - due_screenings) / total_screenings * 100) if total_screenings > 0 else 0
        
        # Gap closure metrics
        gaps_identified = due_screenings
        gaps_closed_this_month = Screening.query.filter(
            Screening.status == 'complete',
            Screening.updated_at >= datetime.utcnow() - timedelta(days=30)
        ).count()
        
        # Document quality metrics
        high_confidence_docs = Document.query.filter(
            Document.ocr_confidence >= 0.8,
            Document.ocr_processed == True
        ).count()
        total_processed_docs = Document.query.filter_by(ocr_processed=True).count()
        
        document_quality_rate = (high_confidence_docs / total_processed_docs * 100) if total_processed_docs > 0 else 0
        
        return {
            'screening_compliance_rate': round(compliance_rate, 1),
            'gaps_identified': gaps_identified,
            'gaps_closed_this_month': gaps_closed_this_month,
            'overdue_screenings': overdue_screenings,
            'document_quality_rate': round(document_quality_rate, 1),
            'high_confidence_documents': high_confidence_docs
        }
    
    def get_patient_population_insights(self):
        """Get insights about patient population and screening needs"""
        # Age distribution
        age_groups = db.session.query(
            func.case(
                (func.extract('year', func.current_date()) - func.extract('year', Patient.date_of_birth) < 30, '18-29'),
                (func.extract('year', func.current_date()) - func.extract('year', Patient.date_of_birth) < 40, '30-39'),
                (func.extract('year', func.current_date()) - func.extract('year', Patient.date_of_birth) < 50, '40-49'),
                (func.extract('year', func.current_date()) - func.extract('year', Patient.date_of_birth) < 65, '50-64'),
                else_='65+'
            ).label('age_group'),
            func.count(Patient.id).label('count')
        ).group_by('age_group').all()
        
        # Gender distribution
        gender_dist = db.session.query(
            Patient.gender,
            func.count(Patient.id).label('count')
        ).group_by(Patient.gender).all()
        
        # Most common screening gaps
        screening_gaps = db.session.query(
            Screening.screening_type.has(name=True),
            func.count(Screening.id).label('gap_count')
        ).filter_by(status='due').group_by(Screening.screening_type_id).all()
        
        return {
            'age_distribution': [
                {'age_group': row.age_group, 'count': row.count}
                for row in age_groups
            ],
            'gender_distribution': [
                {'gender': row.gender, 'count': row.count}
                for row in gender_dist
            ],
            'common_screening_gaps': screening_gaps[:10]  # Top 10
        }
    
    def get_system_utilization_metrics(self, days=7):
        """Get system utilization and performance metrics"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Daily usage patterns
        daily_usage = db.session.query(
            func.date(AdminLog.timestamp).label('date'),
            func.count(AdminLog.id).label('activity_count')
        ).filter(
            AdminLog.timestamp >= cutoff_date
        ).group_by(func.date(AdminLog.timestamp)).all()
        
        # Most active users
        active_users = db.session.query(
            AdminLog.user_id,
            func.count(AdminLog.id).label('action_count')
        ).filter(
            AdminLog.timestamp >= cutoff_date
        ).group_by(AdminLog.user_id).order_by(
            func.count(AdminLog.id).desc()
        ).limit(5).all()
        
        # System health indicators
        total_patients = Patient.query.count()
        recent_documents = Document.query.filter(
            Document.upload_date >= cutoff_date
        ).count()
        
        processing_backlog = Document.query.filter_by(ocr_processed=False).count()
        
        return {
            'daily_usage_pattern': [
                {'date': row.date.isoformat(), 'activity_count': row.activity_count}
                for row in daily_usage
            ],
            'most_active_users': [
                {'user_id': row.user_id, 'action_count': row.action_count}
                for row in active_users
            ],
            'system_health': {
                'total_patients': total_patients,
                'recent_documents': recent_documents,
                'processing_backlog': processing_backlog,
                'system_load': 'Normal' if processing_backlog < 10 else 'High'
            }
        }
    
    def generate_executive_summary(self, days=30):
        """Generate an executive summary for stakeholders"""
        roi_metrics = self.calculate_roi_metrics(days)
        efficiency_metrics = self.get_efficiency_metrics(days)
        compliance_metrics = self.get_compliance_metrics()
        
        summary = {
            'period': f"Last {days} days",
            'generated_at': datetime.utcnow().isoformat(),
            'key_achievements': {
                'hours_saved': roi_metrics['hours_saved'],
                'cost_savings': roi_metrics['labor_cost_saved'],
                'prep_sheets_generated': roi_metrics['prep_sheets_generated'],
                'screening_compliance': compliance_metrics['screening_compliance_rate'],
                'gaps_closed': compliance_metrics['gaps_closed_this_month']
            },
            'efficiency_gains': {
                'document_processing_rate': efficiency_metrics['document_processing_rate'],
                'time_reduction': roi_metrics['time_reduction_percentage'],
                'average_confidence': efficiency_metrics['average_ocr_confidence']
            },
            'quality_metrics': {
                'compliance_rate': compliance_metrics['screening_compliance_rate'],
                'document_quality': compliance_metrics['document_quality_rate'],
                'gaps_identified': compliance_metrics['gaps_identified']
            },
            'recommendations': self.generate_recommendations(efficiency_metrics, compliance_metrics)
        }
        
        return summary
    
    def generate_recommendations(self, efficiency_metrics, compliance_metrics):
        """Generate actionable recommendations based on metrics"""
        recommendations = []
        
        if efficiency_metrics['document_processing_rate'] < 95:
            recommendations.append({
                'category': 'efficiency',
                'priority': 'high',
                'recommendation': 'Document processing rate is below optimal. Consider reviewing OCR settings or document quality.',
                'metric': f"Current rate: {efficiency_metrics['document_processing_rate']}%"
            })
        
        if compliance_metrics['screening_compliance_rate'] < 80:
            recommendations.append({
                'category': 'compliance',
                'priority': 'high',
                'recommendation': 'Screening compliance is below target. Review screening protocols and follow-up procedures.',
                'metric': f"Current compliance: {compliance_metrics['screening_compliance_rate']}%"
            })
        
        if efficiency_metrics['average_ocr_confidence'] < 0.7:
            recommendations.append({
                'category': 'quality',
                'priority': 'medium',
                'recommendation': 'OCR confidence is low. Consider improving document scan quality or preprocessing.',
                'metric': f"Average confidence: {efficiency_metrics['average_ocr_confidence']}"
            })
        
        if compliance_metrics['overdue_screenings'] > 50:
            recommendations.append({
                'category': 'workflow',
                'priority': 'medium',
                'recommendation': 'High number of overdue screenings. Implement automated reminders or workflow improvements.',
                'metric': f"Overdue screenings: {compliance_metrics['overdue_screenings']}"
            })
        
        return recommendations
