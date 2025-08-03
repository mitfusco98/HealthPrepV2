"""
Hours saved, compliance gaps closed analytics
Business intelligence and ROI tracking for healthcare preparation system
"""

from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from sqlalchemy import func, and_, or_
from app import db
from models import Patient, Screening, MedicalDocument, AdminLog, Visit, ScreeningType
import logging

class HealthPrepAnalytics:
    """Provides business analytics and ROI calculations for the healthcare preparation system"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Time saving estimates (in minutes)
        self.time_estimates = {
            'manual_prep_per_patient': 5,  # Minutes to manually prepare one patient
            'screening_review_per_item': 2,  # Minutes to manually review one screening
            'document_review_per_doc': 1.5,  # Minutes to manually review one document
            'gap_identification_per_patient': 3,  # Minutes to manually identify gaps
        }
    
    def get_roi_dashboard_data(self, period_days=30):
        """Get comprehensive ROI dashboard data"""
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=period_days)
            
            # Core metrics
            prep_sheets_generated = self._count_prep_sheets_generated(start_date, end_date)
            patients_processed = self._count_patients_processed(start_date, end_date)
            screenings_automated = self._count_screenings_automated(start_date, end_date)
            gaps_identified = self._count_gaps_identified(start_date, end_date)
            documents_processed = self._count_documents_processed(start_date, end_date)
            
            # Time savings calculations
            time_saved = self._calculate_time_saved(
                prep_sheets_generated, screenings_automated, documents_processed, gaps_identified
            )
            
            # Compliance metrics
            compliance_data = self._get_compliance_metrics()
            
            # Cost savings (based on average MA/nurse hourly rate)
            hourly_rate = 25  # Average MA/nurse hourly rate
            cost_savings = (time_saved['total_minutes'] / 60) * hourly_rate
            
            return {
                'period': {
                    'days': period_days,
                    'start_date': start_date.date(),
                    'end_date': end_date.date()
                },
                'activity_metrics': {
                    'prep_sheets_generated': prep_sheets_generated,
                    'patients_processed': patients_processed,
                    'screenings_automated': screenings_automated,
                    'gaps_identified': gaps_identified,
                    'documents_processed': documents_processed
                },
                'time_savings': time_saved,
                'cost_savings': {
                    'total_dollars': round(cost_savings, 2),
                    'hourly_rate_used': hourly_rate,
                    'total_hours_saved': round(time_saved['total_minutes'] / 60, 2)
                },
                'compliance_metrics': compliance_data,
                'roi_summary': self._calculate_roi_summary(cost_savings, period_days)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting ROI dashboard data: {str(e)}")
            return {}
    
    def _count_prep_sheets_generated(self, start_date, end_date):
        """Count prep sheets generated in period"""
        return AdminLog.query.filter(
            and_(
                AdminLog.action == 'prep_sheet_generated',
                AdminLog.created_at >= start_date,
                AdminLog.created_at <= end_date
            )
        ).count()
    
    def _count_patients_processed(self, start_date, end_date):
        """Count unique patients processed in period"""
        # Count patients who had prep sheets generated or screenings updated
        prep_patients = db.session.query(AdminLog.description).filter(
            and_(
                AdminLog.action == 'prep_sheet_generated',
                AdminLog.created_at >= start_date,
                AdminLog.created_at <= end_date
            )
        ).distinct().count()
        
        screening_patients = db.session.query(Screening.patient_id).filter(
            and_(
                Screening.updated_at >= start_date,
                Screening.updated_at <= end_date
            )
        ).distinct().count()
        
        return max(prep_patients, screening_patients)
    
    def _count_screenings_automated(self, start_date, end_date):
        """Count screenings processed by automation"""
        return Screening.query.filter(
            and_(
                Screening.updated_at >= start_date,
                Screening.updated_at <= end_date
            )
        ).count()
    
    def _count_gaps_identified(self, start_date, end_date):
        """Count screening gaps identified"""
        return Screening.query.filter(
            and_(
                Screening.updated_at >= start_date,
                Screening.updated_at <= end_date,
                Screening.status.in_(['Due', 'Overdue'])
            )
        ).count()
    
    def _count_documents_processed(self, start_date, end_date):
        """Count documents processed by OCR"""
        return MedicalDocument.query.filter(
            and_(
                MedicalDocument.updated_at >= start_date,
                MedicalDocument.updated_at <= end_date,
                MedicalDocument.is_processed == True
            )
        ).count()
    
    def _calculate_time_saved(self, prep_sheets, screenings, documents, gaps):
        """Calculate total time saved through automation"""
        # Manual prep time saved
        prep_time_saved = prep_sheets * self.time_estimates['manual_prep_per_patient']
        
        # Screening review time saved
        screening_time_saved = screenings * self.time_estimates['screening_review_per_item']
        
        # Document processing time saved
        document_time_saved = documents * self.time_estimates['document_review_per_doc']
        
        # Gap identification time saved
        gap_time_saved = gaps * self.time_estimates['gap_identification_per_patient']
        
        total_minutes = prep_time_saved + screening_time_saved + document_time_saved + gap_time_saved
        
        return {
            'prep_sheet_minutes': prep_time_saved,
            'screening_review_minutes': screening_time_saved,
            'document_processing_minutes': document_time_saved,
            'gap_identification_minutes': gap_time_saved,
            'total_minutes': total_minutes,
            'total_hours': round(total_minutes / 60, 2),
            'breakdown': {
                'prep_sheets': f"{prep_time_saved} min ({prep_sheets} sheets)",
                'screenings': f"{screening_time_saved} min ({screenings} items)",
                'documents': f"{document_time_saved} min ({documents} docs)",
                'gaps': f"{gap_time_saved} min ({gaps} gaps)"
            }
        }
    
    def _get_compliance_metrics(self):
        """Get compliance-related metrics"""
        try:
            total_screenings = Screening.query.count()
            
            if total_screenings == 0:
                return {
                    'total_screenings': 0,
                    'compliance_rate': 0,
                    'gaps_closed': 0,
                    'overdue_count': 0,
                    'due_count': 0,
                    'complete_count': 0
                }
            
            # Count by status
            overdue_count = Screening.query.filter_by(status='Overdue').count()
            due_count = Screening.query.filter_by(status='Due').count()
            due_soon_count = Screening.query.filter_by(status='Due Soon').count()
            complete_count = Screening.query.filter_by(status='Complete').count()
            
            # Calculate compliance rate (Complete + Due Soon = compliant)
            compliant_count = complete_count + due_soon_count
            compliance_rate = (compliant_count / total_screenings) * 100
            
            # Estimate gaps closed (screenings that moved from Due/Overdue to Complete)
            gaps_closed = AdminLog.query.filter(
                and_(
                    AdminLog.action == 'screening_status_updated',
                    AdminLog.description.contains('Complete'),
                    AdminLog.created_at >= datetime.utcnow() - timedelta(days=30)
                )
            ).count()
            
            return {
                'total_screenings': total_screenings,
                'compliance_rate': round(compliance_rate, 1),
                'gaps_closed': gaps_closed,
                'overdue_count': overdue_count,
                'due_count': due_count,
                'due_soon_count': due_soon_count,
                'complete_count': complete_count,
                'status_distribution': {
                    'Overdue': overdue_count,
                    'Due': due_count,
                    'Due Soon': due_soon_count,
                    'Complete': complete_count
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error getting compliance metrics: {str(e)}")
            return {}
    
    def _calculate_roi_summary(self, cost_savings, period_days):
        """Calculate ROI summary and projections"""
        # Annualized projections
        annual_multiplier = 365 / period_days
        annual_savings = cost_savings * annual_multiplier
        
        # Estimated system costs (placeholder - would be actual costs in production)
        estimated_monthly_cost = 500  # Estimated monthly operational cost
        estimated_annual_cost = estimated_monthly_cost * 12
        
        # ROI calculation
        net_annual_benefit = annual_savings - estimated_annual_cost
        roi_percentage = (net_annual_benefit / estimated_annual_cost) * 100 if estimated_annual_cost > 0 else 0
        
        return {
            'period_savings': cost_savings,
            'projected_annual_savings': round(annual_savings, 2),
            'estimated_annual_cost': estimated_annual_cost,
            'net_annual_benefit': round(net_annual_benefit, 2),
            'roi_percentage': round(roi_percentage, 1),
            'payback_period_months': round((estimated_annual_cost / (annual_savings / 12)), 1) if annual_savings > 0 else 'N/A'
        }
    
    def get_screening_effectiveness_report(self):
        """Generate report on screening program effectiveness"""
        try:
            # Get screening type performance
            screening_types = ScreeningType.query.filter_by(is_active=True).all()
            effectiveness_data = []
            
            for screening_type in screening_types:
                screenings = Screening.query.filter_by(screening_type_id=screening_type.id).all()
                
                if not screenings:
                    continue
                
                total_screenings = len(screenings)
                complete_screenings = len([s for s in screenings if s.status == 'Complete'])
                overdue_screenings = len([s for s in screenings if s.status == 'Overdue'])
                
                # Calculate effectiveness metrics
                completion_rate = (complete_screenings / total_screenings) * 100 if total_screenings > 0 else 0
                
                # Count eligible patients
                eligible_patients = Patient.query.count()  # Simplified - in reality would check eligibility
                coverage_rate = (total_screenings / eligible_patients) * 100 if eligible_patients > 0 else 0
                
                effectiveness_data.append({
                    'screening_name': screening_type.name,
                    'total_screenings': total_screenings,
                    'completion_rate': round(completion_rate, 1),
                    'coverage_rate': round(coverage_rate, 1),
                    'overdue_count': overdue_screenings,
                    'eligible_patients': eligible_patients,
                    'effectiveness_score': round((completion_rate + coverage_rate) / 2, 1)
                })
            
            # Sort by effectiveness score
            effectiveness_data.sort(key=lambda x: x['effectiveness_score'], reverse=True)
            
            return {
                'screening_effectiveness': effectiveness_data,
                'summary': {
                    'total_screening_types': len(effectiveness_data),
                    'average_completion_rate': round(
                        sum(item['completion_rate'] for item in effectiveness_data) / len(effectiveness_data), 1
                    ) if effectiveness_data else 0,
                    'average_coverage_rate': round(
                        sum(item['coverage_rate'] for item in effectiveness_data) / len(effectiveness_data), 1
                    ) if effectiveness_data else 0
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error generating screening effectiveness report: {str(e)}")
            return {}
    
    def get_operational_efficiency_metrics(self, days=30):
        """Get operational efficiency metrics"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Document processing efficiency
            total_docs = MedicalDocument.query.filter(MedicalDocument.created_at >= cutoff_date).count()
            processed_docs = MedicalDocument.query.filter(
                and_(
                    MedicalDocument.created_at >= cutoff_date,
                    MedicalDocument.is_processed == True
                )
            ).count()
            
            processing_efficiency = (processed_docs / total_docs) * 100 if total_docs > 0 else 0
            
            # OCR accuracy (based on confidence scores)
            confidence_scores = db.session.query(MedicalDocument.ocr_confidence).filter(
                and_(
                    MedicalDocument.created_at >= cutoff_date,
                    MedicalDocument.ocr_confidence.isnot(None)
                )
            ).all()
            
            avg_confidence = sum(score[0] for score in confidence_scores) / len(confidence_scores) if confidence_scores else 0
            
            # Screening automation rate
            total_screenings = Screening.query.filter(Screening.updated_at >= cutoff_date).count()
            automated_screenings = total_screenings  # All screenings are automated in this system
            automation_rate = 100 if total_screenings > 0 else 0
            
            return {
                'period_days': days,
                'document_processing': {
                    'total_documents': total_docs,
                    'processed_documents': processed_docs,
                    'processing_efficiency': round(processing_efficiency, 1),
                    'average_ocr_confidence': round(avg_confidence, 1)
                },
                'screening_automation': {
                    'total_screenings': total_screenings,
                    'automated_screenings': automated_screenings,
                    'automation_rate': automation_rate
                },
                'overall_efficiency': round((processing_efficiency + automation_rate) / 2, 1)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting operational efficiency metrics: {str(e)}")
            return {}
    
    def generate_monthly_roi_report(self, month=None, year=None):
        """Generate comprehensive monthly ROI report"""
        try:
            if not month or not year:
                now = datetime.now()
                month = now.month
                year = now.year
            
            # Calculate month boundaries
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = datetime(year, month + 1, 1) - timedelta(days=1)
            
            # Get all metrics for the month
            roi_data = self.get_roi_dashboard_data((end_date - start_date).days)
            effectiveness_data = self.get_screening_effectiveness_report()
            efficiency_data = self.get_operational_efficiency_metrics((end_date - start_date).days)
            
            report = {
                'report_period': {
                    'month': month,
                    'year': year,
                    'start_date': start_date.date(),
                    'end_date': end_date.date()
                },
                'executive_summary': {
                    'total_cost_savings': roi_data.get('cost_savings', {}).get('total_dollars', 0),
                    'total_hours_saved': roi_data.get('cost_savings', {}).get('total_hours_saved', 0),
                    'patients_served': roi_data.get('activity_metrics', {}).get('patients_processed', 0),
                    'compliance_rate': roi_data.get('compliance_metrics', {}).get('compliance_rate', 0),
                    'processing_efficiency': efficiency_data.get('overall_efficiency', 0)
                },
                'detailed_metrics': {
                    'roi_analysis': roi_data,
                    'screening_effectiveness': effectiveness_data,
                    'operational_efficiency': efficiency_data
                },
                'generated_at': datetime.utcnow()
            }
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating monthly ROI report: {str(e)}")
            return {}
    
    def track_user_productivity(self, days=30):
        """Track productivity metrics by user"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get user activity from admin logs
            from models import User
            
            users = User.query.filter_by(is_active=True).all()
            productivity_data = []
            
            for user in users:
                user_logs = AdminLog.query.filter(
                    and_(
                        AdminLog.user_id == user.id,
                        AdminLog.created_at >= cutoff_date
                    )
                ).all()
                
                # Categorize activities
                prep_sheets = len([log for log in user_logs if log.action == 'prep_sheet_generated'])
                document_uploads = len([log for log in user_logs if log.action == 'document_uploaded'])
                screening_updates = len([log for log in user_logs if log.action == 'screening_updated'])
                
                # Calculate productivity score
                productivity_score = (prep_sheets * 3) + (document_uploads * 2) + (screening_updates * 1)
                
                productivity_data.append({
                    'user_id': user.id,
                    'username': user.username,
                    'role': user.role,
                    'prep_sheets_generated': prep_sheets,
                    'documents_uploaded': document_uploads,
                    'screenings_updated': screening_updates,
                    'total_activities': len(user_logs),
                    'productivity_score': productivity_score,
                    'daily_average': round(len(user_logs) / days, 2)
                })
            
            # Sort by productivity score
            productivity_data.sort(key=lambda x: x['productivity_score'], reverse=True)
            
            return {
                'period_days': days,
                'user_productivity': productivity_data,
                'summary': {
                    'total_active_users': len(productivity_data),
                    'average_productivity': round(
                        sum(user['productivity_score'] for user in productivity_data) / len(productivity_data), 2
                    ) if productivity_data else 0,
                    'most_productive_user': productivity_data[0]['username'] if productivity_data else None
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error tracking user productivity: {str(e)}")
            return {}
