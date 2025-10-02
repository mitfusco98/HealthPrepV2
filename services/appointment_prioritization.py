"""
Appointment-Based Prioritization Service
Identifies patients with upcoming appointments for prioritized screening processing
"""

import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional, Tuple
from sqlalchemy import and_

from models import db, Patient, Appointment, Organization

logger = logging.getLogger(__name__)


class AppointmentBasedPrioritization:
    """
    Service to identify and prioritize patients based on upcoming appointments
    Reduces screening workload by focusing on patients scheduled to be seen soon
    """
    
    def __init__(self, organization_id: int):
        self.organization_id = organization_id
        self.organization = Organization.query.get(organization_id)
        
        if not self.organization:
            raise ValueError(f"Organization {organization_id} not found")
        
        logger.info(f"Initialized AppointmentBasedPrioritization for organization {organization_id}")
    
    def get_priority_patients(self) -> List[int]:
        """
        Get list of patient IDs with appointments in the configured time window
        
        Returns:
            List of patient IDs to prioritize for screening
        """
        try:
            # Check if appointment prioritization is enabled
            if not self.organization.appointment_based_prioritization:
                logger.info("Appointment-based prioritization is disabled for this organization")
                return []
            
            # Get the prioritization window (default 14 days)
            window_days = self.organization.prioritization_window_days or 14
            today = date.today()
            cutoff_date = today + timedelta(days=window_days)
            
            logger.info(f"Getting priority patients with appointments between {today} and {cutoff_date}")
            
            # Query appointments in the window
            upcoming_appointments = Appointment.query.filter(
                and_(
                    Appointment.org_id == self.organization_id,
                    Appointment.appointment_date >= datetime.combine(today, datetime.min.time()),
                    Appointment.appointment_date <= datetime.combine(cutoff_date, datetime.max.time()),
                    Appointment.status.in_(['scheduled', 'booked', 'pending', 'arrived'])
                )
            ).all()
            
            # Extract unique patient IDs
            priority_patient_ids = list(set([apt.patient_id for apt in upcoming_appointments]))
            
            logger.info(f"Found {len(priority_patient_ids)} priority patients with {len(upcoming_appointments)} appointments")
            
            return priority_patient_ids
            
        except Exception as e:
            logger.error(f"Error getting priority patients: {str(e)}")
            return []
    
    def get_priority_patients_with_appointments(self) -> List[Tuple[int, List[Dict]]]:
        """
        Get list of patient IDs with their appointment details
        
        Returns:
            List of tuples (patient_id, [appointment_dicts])
        """
        try:
            if not self.organization.appointment_based_prioritization:
                return []
            
            window_days = self.organization.prioritization_window_days or 14
            today = date.today()
            cutoff_date = today + timedelta(days=window_days)
            
            # Query appointments in the window
            upcoming_appointments = Appointment.query.filter(
                and_(
                    Appointment.org_id == self.organization_id,
                    Appointment.appointment_date >= datetime.combine(today, datetime.min.time()),
                    Appointment.appointment_date <= datetime.combine(cutoff_date, datetime.max.time()),
                    Appointment.status.in_(['scheduled', 'booked', 'pending', 'arrived'])
                )
            ).order_by(Appointment.appointment_date).all()
            
            # Group appointments by patient
            patient_appointments = {}
            for apt in upcoming_appointments:
                if apt.patient_id not in patient_appointments:
                    patient_appointments[apt.patient_id] = []
                
                patient_appointments[apt.patient_id].append({
                    'id': apt.id,
                    'date': apt.appointment_date,
                    'type': apt.appointment_type,
                    'provider': apt.provider,
                    'status': apt.status
                })
            
            # Convert to list of tuples
            result = [(patient_id, apts) for patient_id, apts in patient_appointments.items()]
            
            logger.info(f"Found {len(result)} priority patients with appointments")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting priority patients with appointments: {str(e)}")
            return []
    
    def get_non_scheduled_patients(self, exclude_patient_ids: List[int] = None) -> List[int]:
        """
        Get list of patient IDs without appointments in the window
        Used when process_non_scheduled_patients setting is enabled
        
        Args:
            exclude_patient_ids: List of patient IDs to exclude (already processed)
        
        Returns:
            List of patient IDs without upcoming appointments
        """
        try:
            if exclude_patient_ids is None:
                exclude_patient_ids = []
            
            # Get all patients for this organization
            query = Patient.query.filter_by(org_id=self.organization_id)
            
            # Exclude patients already in the priority list
            if exclude_patient_ids:
                query = query.filter(~Patient.id.in_(exclude_patient_ids))
            
            non_scheduled_patients = query.all()
            patient_ids = [p.id for p in non_scheduled_patients]
            
            logger.info(f"Found {len(patient_ids)} non-scheduled patients")
            
            return patient_ids
            
        except Exception as e:
            logger.error(f"Error getting non-scheduled patients: {str(e)}")
            return []
    
    def get_prioritization_stats(self) -> Dict:
        """
        Get statistics about appointment-based prioritization
        
        Returns:
            Dictionary with prioritization statistics
        """
        try:
            window_days = self.organization.prioritization_window_days or 14
            today = date.today()
            cutoff_date = today + timedelta(days=window_days)
            
            # Count upcoming appointments
            upcoming_count = Appointment.query.filter(
                and_(
                    Appointment.org_id == self.organization_id,
                    Appointment.appointment_date >= datetime.combine(today, datetime.min.time()),
                    Appointment.appointment_date <= datetime.combine(cutoff_date, datetime.max.time()),
                    Appointment.status.in_(['scheduled', 'booked', 'pending', 'arrived'])
                )
            ).count()
            
            # Count unique patients with appointments
            upcoming_appointments = Appointment.query.filter(
                and_(
                    Appointment.org_id == self.organization_id,
                    Appointment.appointment_date >= datetime.combine(today, datetime.min.time()),
                    Appointment.appointment_date <= datetime.combine(cutoff_date, datetime.max.time()),
                    Appointment.status.in_(['scheduled', 'booked', 'pending', 'arrived'])
                )
            ).all()
            
            priority_patient_count = len(set([apt.patient_id for apt in upcoming_appointments]))
            
            # Total patient count
            total_patients = Patient.query.filter_by(org_id=self.organization_id).count()
            
            # Workload reduction percentage
            workload_reduction = 0
            if total_patients > 0:
                workload_reduction = round((1 - priority_patient_count / total_patients) * 100, 1)
            
            return {
                'enabled': self.organization.appointment_based_prioritization,
                'window_days': window_days,
                'window_start': today.isoformat(),
                'window_end': cutoff_date.isoformat(),
                'upcoming_appointments': upcoming_count,
                'priority_patients': priority_patient_count,
                'total_patients': total_patients,
                'non_scheduled_patients': total_patients - priority_patient_count,
                'workload_reduction_pct': workload_reduction,
                'last_appointment_sync': self.organization.last_appointment_sync.isoformat() if self.organization.last_appointment_sync else None
            }
            
        except Exception as e:
            logger.error(f"Error getting prioritization stats: {str(e)}")
            return {
                'enabled': False,
                'error': str(e)
            }
