from datetime import datetime, timedelta
from models import Patient, MedicalDocument, PatientScreening, ScreeningType, AdminLog
from app import db
import logging

class HealthPrepAnalytics:
    """Analytics for HealthPrep system performance and ROI"""
    
    def __init__(self):
        pass
    
    def calculate_time_saved(self, days_back=30):
        """Calculate time saved through automation"""
        try:
            # Base calculation: 5 minutes per prep sheet generated
            # Additional time saved from document processing and screening automation
            
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            
            # Count prep sheets generated (proxy: patient document uploads)
            recent_uploads = MedicalDocument.query.filter(
                MedicalDocument.created_at >= cutoff_date
            ).count()
            
            # Count automated screenings processed
            recent_screenings = PatientScreening.query.filter(
                PatientScreening.updated_at >= cutoff_date
            ).count()
            
            # Time savings calculation
            prep_sheet_time = recent_uploads * 5  # 5 minutes per document processed
            screening_time = recent_screenings * 2  # 2 minutes per screening automated
            ocr_time = recent_uploads * 3  # 3 minutes saved per OCR document
            
            total_minutes = prep_sheet_time + screening_time + ocr_time
            total_hours = total_minutes / 60
            
            return {
                'total_minutes': total_minutes,
                'total_hours': round(total_hours, 2),
                'documents_processed': recent_uploads,
                'screenings_automated': recent_screenings,
                'estimated_cost_savings': round(total_hours * 25, 2),  # $25/hour MA wage
                'period_days': days_back
            }
            
        except Exception as e:
            logging.error(f"Error calculating time saved: {str(e)}")
            return {
                'total_minutes': 0,
                'total_hours': 0,
                'documents_processed': 0,
                'screenings_automated': 0,
                'estimated_cost_savings': 0,
                'period_days': days_back
            }
    
    def get_screening_compliance_gaps(self):
        """Identify compliance gaps that have been closed"""
        try:
            # Count screenings by status
            due = PatientScreening.query.filter_by(status='due').count()
            due_soon = PatientScreening.query.filter_by(status='due_soon').count()
            complete = PatientScreening.query.filter_by(status='complete').count()
            
            total_screenings = due + due_soon + complete
            
            # Calculate compliance rate
            compliance_rate = (complete / total_screenings * 100) if total_screenings > 0 else 0
            
            # Gaps identified in last 30 days
            month_ago = datetime.utcnow() - timedelta(days=30)
            recent_due = PatientScreening.query.filter(
                PatientScreening.updated_at >= month_ago,
                PatientScreening.status.in_(['due', 'due_soon'])
            ).count()
            
            return {
                'total_screenings': total_screenings,
                'due_screenings': due,
                'due_soon_screenings': due_soon,
                'complete_screenings': complete,
                'compliance_rate': round(compliance_rate, 1),
                'gaps_identified_30_days': recent_due,
                'potential_revenue_impact': recent_due * 150  # $150 average per screening
            }
            
        except Exception as e:
            logging.error(f"Error calculating compliance gaps: {str(e)}")
            return {
                'total_screenings': 0,
                'due_screenings': 0,
                'due_soon_screenings': 0,
                'complete_screenings': 0,
                'compliance_rate': 0,
                'gaps_identified_30_days': 0,
                'potential_revenue_impact': 0
            }
    
    def get_system_performance_metrics(self):
        """Get system performance and usage metrics"""
        try:
            # Patient volume
            total_patients = Patient.query.count()
            month_ago = datetime.utcnow() - timedelta(days=30)
            new_patients_30_days = Patient.query.filter(
                Patient.created_at >= month_ago
            ).count()
            
            # Document processing
            total_documents = MedicalDocument.query.count()
            processed_documents = MedicalDocument.query.filter(
                MedicalDocument.ocr_text.isnot(None)
            ).count()
            
            processing_rate = (processed_documents / total_documents * 100) if total_documents > 0 else 0
            
            # High confidence OCR rate
            high_confidence_docs = MedicalDocument.query.filter(
                MedicalDocument.ocr_confidence >= 0.8
            ).count()
            
            confidence_rate = (high_confidence_docs / processed_documents * 100) if processed_documents > 0 else 0
            
            # Active screening types
            active_screenings = ScreeningType.query.filter_by(is_active=True).count()
            
            # System usage (admin actions in last 30 days)
            admin_activity = AdminLog.query.filter(
                AdminLog.timestamp >= month_ago
            ).count()
            
            return {
                'patient_metrics': {
                    'total_patients': total_patients,
                    'new_patients_30_days': new_patients_30_days,
                    'growth_rate': round((new_patients_30_days / max(total_patients - new_patients_30_days, 1)) * 100, 1)
                },
                'document_metrics': {
                    'total_documents': total_documents,
                    'processed_documents': processed_documents,
                    'processing_rate': round(processing_rate, 1),
                    'high_confidence_rate': round(confidence_rate, 1)
                },
                'screening_metrics': {
                    'active_screening_types': active_screenings,
                    'admin_actions_30_days': admin_activity
                }
            }
            
        except Exception as e:
            logging.error(f"Error getting performance metrics: {str(e)}")
            return {
                'patient_metrics': {'total_patients': 0, 'new_patients_30_days': 0, 'growth_rate': 0},
                'document_metrics': {'total_documents': 0, 'processed_documents': 0, 'processing_rate': 0, 'high_confidence_rate': 0},
                'screening_metrics': {'active_screening_types': 0, 'admin_actions_30_days': 0}
            }
    
    def generate_roi_report(self, months_back=6):
        """Generate comprehensive ROI report"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=30 * months_back)
            
            # Time savings
            time_savings = self.calculate_time_saved(days_back=30 * months_back)
            
            # Compliance improvements
            compliance_data = self.get_screening_compliance_gaps()
            
            # Performance metrics
            performance_data = self.get_system_performance_metrics()
            
            # Calculate estimated ROI
            monthly_savings = time_savings['estimated_cost_savings'] / months_back
            potential_revenue = compliance_data['potential_revenue_impact']
            
            total_value = time_savings['estimated_cost_savings'] + (potential_revenue * 0.3)  # 30% conversion rate assumption
            
            roi_report = {
                'report_period': f"{months_back} months",
                'generated_at': datetime.utcnow().isoformat(),
                'time_savings': time_savings,
                'compliance_data': compliance_data,
                'performance_data': performance_data,
                'roi_summary': {
                    'total_estimated_value': round(total_value, 2),
                    'monthly_savings': round(monthly_savings, 2),
                    'hours_saved': time_savings['total_hours'],
                    'compliance_rate': compliance_data['compliance_rate'],
                    'processing_efficiency': performance_data['document_metrics']['processing_rate']
                }
            }
            
            return roi_report
            
        except Exception as e:
            logging.error(f"Error generating ROI report: {str(e)}")
            return None
    
    def get_trending_data(self, days_back=30):
        """Get trending data for dashboard charts"""
        try:
            # Daily document uploads for the period
            daily_uploads = db.session.query(
                db.func.date(MedicalDocument.created_at).label('date'),
                db.func.count(MedicalDocument.id).label('count')
            ).filter(
                MedicalDocument.created_at >= datetime.utcnow() - timedelta(days=days_back)
            ).group_by(
                db.func.date(MedicalDocument.created_at)
            ).order_by('date').all()
            
            # Daily screening updates
            daily_screenings = db.session.query(
                db.func.date(PatientScreening.updated_at).label('date'),
                db.func.count(PatientScreening.id).label('count')
            ).filter(
                PatientScreening.updated_at >= datetime.utcnow() - timedelta(days=days_back)
            ).group_by(
                db.func.date(PatientScreening.updated_at)
            ).order_by('date').all()
            
            return {
                'document_uploads': [
                    {'date': upload[0].isoformat(), 'count': upload[1]}
                    for upload in daily_uploads
                ],
                'screening_updates': [
                    {'date': screening[0].isoformat(), 'count': screening[1]}
                    for screening in daily_screenings
                ]
            }
            
        except Exception as e:
            logging.error(f"Error getting trending data: {str(e)}")
            return {
                'document_uploads': [],
                'screening_updates': []
            }
