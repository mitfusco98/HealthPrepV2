"""
Admin analytics for hours saved, gaps closed, and system performance metrics.
Provides ROI calculations and business intelligence for the healthcare prep system.
"""

import logging
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func, and_, or_
from app import db
from models import Patient, Screening, MedicalDocument, ScreeningType, AdminLog

logger = logging.getLogger(__name__)

class HealthPrepAnalytics:
    """Provides business analytics and ROI calculations for HealthPrep system"""
    
    def __init__(self):
        # Time estimates (in minutes) for manual prep activities
        self.time_estimates = {
            'manual_prep_per_patient': 30,  # Minutes for manual prep without system
            'automated_prep_per_patient': 5,  # Minutes with system
            'screening_review_per_item': 3,   # Minutes to review each screening
            'document_search_per_document': 2,  # Minutes to manually find document
            'manual_screening_check': 10,     # Minutes to manually check screening status
            'automated_screening_check': 1    # Minutes with automated system
        }
        
        # Cost estimates (hourly rates in USD)
        self.cost_estimates = {
            'medical_assistant': 18.50,
            'nurse': 32.00,
            'physician': 150.00,
            'admin_staff': 16.00
        }
    
    def get_system_roi_metrics(self, days: int = 30) -> Dict:
        """
        Calculate comprehensive ROI metrics for the system
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with ROI calculations
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get basic counts
            total_patients = Patient.query.count()
            active_screenings = Screening.query.count()
            processed_documents = MedicalDocument.query.filter(
                MedicalDocument.ocr_processed == True
            ).count()
            
            # Prep sheets generated (estimated from patient activity)
            prep_sheets_generated = self._estimate_prep_sheets_generated(cutoff_date)
            
            # Time saved calculations
            time_savings = self._calculate_time_savings(prep_sheets_generated, active_screenings, processed_documents)
            
            # Cost savings
            cost_savings = self._calculate_cost_savings(time_savings)
            
            # Quality metrics
            quality_metrics = self._calculate_quality_metrics(cutoff_date)
            
            # System usage metrics
            usage_metrics = self._get_usage_metrics(cutoff_date)
            
            return {
                'period_days': days,
                'basic_metrics': {
                    'total_patients': total_patients,
                    'active_screenings': active_screenings,
                    'processed_documents': processed_documents,
                    'prep_sheets_generated': prep_sheets_generated
                },
                'time_savings': time_savings,
                'cost_savings': cost_savings,
                'quality_metrics': quality_metrics,
                'usage_metrics': usage_metrics,
                'roi_summary': self._calculate_roi_summary(cost_savings, quality_metrics)
            }
            
        except Exception as e:
            logger.error(f"Error calculating ROI metrics: {str(e)}")
            return self._empty_roi_metrics()
    
    def _estimate_prep_sheets_generated(self, cutoff_date: datetime) -> int:
        """Estimate number of prep sheets generated based on activity"""
        # Use admin logs to estimate prep sheet generation
        prep_activities = AdminLog.query.filter(
            and_(
                AdminLog.timestamp >= cutoff_date,
                or_(
                    AdminLog.action.like('%prep%'),
                    AdminLog.action.like('%screening%'),
                    AdminLog.action == 'patient_viewed'
                )
            )
        ).count()
        
        # Estimate that each 3 activities represents 1 prep sheet
        return max(1, prep_activities // 3)
    
    def _calculate_time_savings(self, prep_sheets: int, screenings: int, documents: int) -> Dict:
        """Calculate time savings from automation"""
        try:
            # Prep sheet time savings
            manual_prep_time = prep_sheets * self.time_estimates['manual_prep_per_patient']
            automated_prep_time = prep_sheets * self.time_estimates['automated_prep_per_patient']
            prep_time_saved = manual_prep_time - automated_prep_time
            
            # Screening check time savings
            manual_screening_time = screenings * self.time_estimates['manual_screening_check']
            automated_screening_time = screenings * self.time_estimates['automated_screening_check']
            screening_time_saved = manual_screening_time - automated_screening_time
            
            # Document processing time savings
            document_time_saved = documents * self.time_estimates['document_search_per_document']
            
            total_time_saved_minutes = prep_time_saved + screening_time_saved + document_time_saved
            total_time_saved_hours = total_time_saved_minutes / 60
            
            return {
                'prep_time_saved_minutes': prep_time_saved,
                'screening_time_saved_minutes': screening_time_saved,
                'document_time_saved_minutes': document_time_saved,
                'total_time_saved_minutes': total_time_saved_minutes,
                'total_time_saved_hours': round(total_time_saved_hours, 2),
                'equivalent_full_days': round(total_time_saved_hours / 8, 1)
            }
            
        except Exception as e:
            logger.error(f"Error calculating time savings: {str(e)}")
            return {
                'prep_time_saved_minutes': 0,
                'screening_time_saved_minutes': 0,
                'document_time_saved_minutes': 0,
                'total_time_saved_minutes': 0,
                'total_time_saved_hours': 0,
                'equivalent_full_days': 0
            }
    
    def _calculate_cost_savings(self, time_savings: Dict) -> Dict:
        """Calculate cost savings based on time savings"""
        try:
            time_saved_hours = time_savings['total_time_saved_hours']
            
            # Calculate savings by staff type (assuming mixed usage)
            ma_hours = time_saved_hours * 0.6  # 60% MA time
            nurse_hours = time_saved_hours * 0.3  # 30% nurse time
            physician_hours = time_saved_hours * 0.1  # 10% physician time
            
            ma_savings = ma_hours * self.cost_estimates['medical_assistant']
            nurse_savings = nurse_hours * self.cost_estimates['nurse']
            physician_savings = physician_hours * self.cost_estimates['physician']
            
            total_cost_savings = ma_savings + nurse_savings + physician_savings
            
            return {
                'medical_assistant_savings': round(ma_savings, 2),
                'nurse_savings': round(nurse_savings, 2),
                'physician_savings': round(physician_savings, 2),
                'total_cost_savings': round(total_cost_savings, 2),
                'hourly_breakdown': {
                    'ma_hours': round(ma_hours, 2),
                    'nurse_hours': round(nurse_hours, 2),
                    'physician_hours': round(physician_hours, 2)
                },
                'annualized_savings': round(total_cost_savings * 12, 2)  # Monthly to annual
            }
            
        except Exception as e:
            logger.error(f"Error calculating cost savings: {str(e)}")
            return {
                'medical_assistant_savings': 0,
                'nurse_savings': 0,
                'physician_savings': 0,
                'total_cost_savings': 0,
                'hourly_breakdown': {'ma_hours': 0, 'nurse_hours': 0, 'physician_hours': 0},
                'annualized_savings': 0
            }
    
    def _calculate_quality_metrics(self, cutoff_date: datetime) -> Dict:
        """Calculate quality improvement metrics"""
        try:
            # Screening compliance
            total_screenings = Screening.query.count()
            due_screenings = Screening.query.filter(
                Screening.status.in_(['due', 'overdue'])
            ).count()
            
            compliance_rate = ((total_screenings - due_screenings) / total_screenings * 100) if total_screenings > 0 else 0
            
            # Gaps closed (screenings moved from due to complete)
            gaps_closed = self._estimate_gaps_closed(cutoff_date)
            
            # Document accuracy
            high_confidence_docs = MedicalDocument.query.filter(
                MedicalDocument.ocr_confidence >= 85
            ).count()
            total_processed_docs = MedicalDocument.query.filter(
                MedicalDocument.ocr_processed == True
            ).count()
            
            doc_accuracy_rate = (high_confidence_docs / total_processed_docs * 100) if total_processed_docs > 0 else 0
            
            # PHI protection rate
            phi_protected_docs = MedicalDocument.query.filter(
                MedicalDocument.phi_filtered == True
            ).count()
            phi_protection_rate = (phi_protected_docs / total_processed_docs * 100) if total_processed_docs > 0 else 0
            
            return {
                'screening_compliance_rate': round(compliance_rate, 1),
                'gaps_closed': gaps_closed,
                'document_accuracy_rate': round(doc_accuracy_rate, 1),
                'phi_protection_rate': round(phi_protection_rate, 1),
                'total_screenings_managed': total_screenings,
                'due_screenings': due_screenings,
                'high_confidence_documents': high_confidence_docs
            }
            
        except Exception as e:
            logger.error(f"Error calculating quality metrics: {str(e)}")
            return {
                'screening_compliance_rate': 0,
                'gaps_closed': 0,
                'document_accuracy_rate': 0,
                'phi_protection_rate': 0,
                'total_screenings_managed': 0,
                'due_screenings': 0,
                'high_confidence_documents': 0
            }
    
    def _estimate_gaps_closed(self, cutoff_date: datetime) -> int:
        """Estimate number of screening gaps closed"""
        # This would ideally track status changes from due->complete
        # For now, estimate based on complete screenings with recent last_completed_date
        recent_completed = Screening.query.filter(
            and_(
                Screening.status == 'complete',
                Screening.last_completed_date >= cutoff_date.date()
            )
        ).count()
        
        return recent_completed
    
    def _get_usage_metrics(self, cutoff_date: datetime) -> Dict:
        """Get system usage metrics"""
        try:
            # Admin activity
            admin_activities = AdminLog.query.filter(
                AdminLog.timestamp >= cutoff_date
            ).count()
            
            # Active users
            active_users = db.session.query(AdminLog.user_id).filter(
                and_(
                    AdminLog.timestamp >= cutoff_date,
                    AdminLog.user_id.isnot(None)
                )
            ).distinct().count()
            
            # Document processing volume
            documents_processed = MedicalDocument.query.filter(
                MedicalDocument.created_at >= cutoff_date
            ).count()
            
            # Average processing time (simulated - would come from actual metrics)
            avg_processing_time = 8.5  # seconds
            
            return {
                'admin_activities': admin_activities,
                'active_users': active_users,
                'documents_processed': documents_processed,
                'avg_processing_time_seconds': avg_processing_time,
                'system_uptime_percentage': 99.8  # Would come from monitoring
            }
            
        except Exception as e:
            logger.error(f"Error getting usage metrics: {str(e)}")
            return {
                'admin_activities': 0,
                'active_users': 0,
                'documents_processed': 0,
                'avg_processing_time_seconds': 0,
                'system_uptime_percentage': 0
            }
    
    def _calculate_roi_summary(self, cost_savings: Dict, quality_metrics: Dict) -> Dict:
        """Calculate high-level ROI summary"""
        try:
            monthly_savings = cost_savings['total_cost_savings']
            annual_savings = cost_savings['annualized_savings']
            
            # Estimate system costs (placeholder - would be actual costs)
            estimated_monthly_cost = 2500  # Software licensing, hosting, etc.
            estimated_annual_cost = estimated_monthly_cost * 12
            
            monthly_roi = ((monthly_savings - estimated_monthly_cost) / estimated_monthly_cost * 100) if estimated_monthly_cost > 0 else 0
            annual_roi = ((annual_savings - estimated_annual_cost) / estimated_annual_cost * 100) if estimated_annual_cost > 0 else 0
            
            payback_months = (estimated_annual_cost / monthly_savings) if monthly_savings > 0 else float('inf')
            
            return {
                'monthly_net_savings': round(monthly_savings - estimated_monthly_cost, 2),
                'annual_net_savings': round(annual_savings - estimated_annual_cost, 2),
                'monthly_roi_percentage': round(monthly_roi, 1),
                'annual_roi_percentage': round(annual_roi, 1),
                'payback_period_months': round(payback_months, 1) if payback_months != float('inf') else 'N/A',
                'gaps_closed_value': quality_metrics['gaps_closed'],
                'compliance_improvement': quality_metrics['screening_compliance_rate']
            }
            
        except Exception as e:
            logger.error(f"Error calculating ROI summary: {str(e)}")
            return {
                'monthly_net_savings': 0,
                'annual_net_savings': 0,
                'monthly_roi_percentage': 0,
                'annual_roi_percentage': 0,
                'payback_period_months': 'N/A',
                'gaps_closed_value': 0,
                'compliance_improvement': 0
            }
    
    def get_screening_performance_analytics(self, days: int = 30) -> Dict:
        """Get detailed screening performance analytics"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Screening type performance
            screening_types = ScreeningType.query.filter_by(is_active=True).all()
            type_performance = []
            
            for st in screening_types:
                screenings = Screening.query.filter_by(screening_type_id=st.id).all()
                
                total_count = len(screenings)
                complete_count = len([s for s in screenings if s.status == 'complete'])
                due_count = len([s for s in screenings if s.status in ['due', 'overdue']])
                
                compliance_rate = (complete_count / total_count * 100) if total_count > 0 else 0
                
                type_performance.append({
                    'name': st.name,
                    'total_screenings': total_count,
                    'complete': complete_count,
                    'due': due_count,
                    'compliance_rate': round(compliance_rate, 1)
                })
            
            # Sort by compliance rate
            type_performance.sort(key=lambda x: x['compliance_rate'], reverse=True)
            
            return {
                'period_days': days,
                'screening_type_performance': type_performance,
                'top_performers': type_performance[:5],
                'needs_attention': [st for st in type_performance if st['compliance_rate'] < 80]
            }
            
        except Exception as e:
            logger.error(f"Error getting screening performance analytics: {str(e)}")
            return {
                'period_days': days,
                'screening_type_performance': [],
                'top_performers': [],
                'needs_attention': []
            }
    
    def get_monthly_trends(self, months: int = 12) -> Dict:
        """Get monthly trend data for analytics dashboard"""
        try:
            trends = []
            
            for i in range(months):
                month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0) - relativedelta(months=i)
                month_end = month_start + relativedelta(months=1)
                
                # Documents processed
                docs_processed = MedicalDocument.query.filter(
                    and_(
                        MedicalDocument.created_at >= month_start,
                        MedicalDocument.created_at < month_end
                    )
                ).count()
                
                # Screenings completed
                screenings_completed = Screening.query.filter(
                    and_(
                        Screening.updated_at >= month_start,
                        Screening.updated_at < month_end,
                        Screening.status == 'complete'
                    )
                ).count()
                
                # Admin activities
                admin_activities = AdminLog.query.filter(
                    and_(
                        AdminLog.timestamp >= month_start,
                        AdminLog.timestamp < month_end
                    )
                ).count()
                
                trends.append({
                    'month': month_start.strftime('%Y-%m'),
                    'documents_processed': docs_processed,
                    'screenings_completed': screenings_completed,
                    'admin_activities': admin_activities
                })
            
            trends.reverse()  # Oldest first
            
            return {
                'monthly_trends': trends,
                'trend_summary': {
                    'avg_documents_per_month': sum(t['documents_processed'] for t in trends) / len(trends),
                    'avg_screenings_per_month': sum(t['screenings_completed'] for t in trends) / len(trends),
                    'total_activities': sum(t['admin_activities'] for t in trends)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting monthly trends: {str(e)}")
            return {
                'monthly_trends': [],
                'trend_summary': {
                    'avg_documents_per_month': 0,
                    'avg_screenings_per_month': 0,
                    'total_activities': 0
                }
            }
    
    def _empty_roi_metrics(self) -> Dict:
        """Return empty ROI metrics structure"""
        return {
            'period_days': 0,
            'basic_metrics': {
                'total_patients': 0,
                'active_screenings': 0,
                'processed_documents': 0,
                'prep_sheets_generated': 0
            },
            'time_savings': {
                'total_time_saved_hours': 0,
                'equivalent_full_days': 0
            },
            'cost_savings': {
                'total_cost_savings': 0,
                'annualized_savings': 0
            },
            'quality_metrics': {
                'screening_compliance_rate': 0,
                'gaps_closed': 0
            },
            'usage_metrics': {
                'admin_activities': 0,
                'active_users': 0
            },
            'roi_summary': {
                'annual_roi_percentage': 0,
                'payback_period_months': 'N/A'
            }
        }

# Global analytics instance
analytics = HealthPrepAnalytics()
