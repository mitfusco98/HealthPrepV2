#!/usr/bin/env python3
"""
Seed Test Appointments Script

Creates test appointment data for sandbox patients to enable testing of the
appointment window prioritization feature. Generates a mix of:
- Priority patients (appointments within the 14-day window)
- Dormant patients (no appointments in window, or only past appointments)

Usage:
    python scripts/seed_test_appointments.py [--org-id ORG_ID] [--clear]

Options:
    --org-id    Target organization ID (default: 1)
    --clear     Remove all existing test appointments before seeding
"""

import sys
import os
import argparse
from datetime import datetime, timedelta
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Patient, Appointment, Organization, Provider


def clear_test_appointments(org_id):
    """Remove all appointments for the specified organization"""
    count = Appointment.query.filter_by(org_id=org_id).delete()
    db.session.commit()
    print(f"Cleared {count} existing appointments for org_id={org_id}")


def seed_appointments(org_id, priority_ratio=0.6):
    """
    Seed appointments for existing patients.
    
    Args:
        org_id: Organization ID to seed appointments for
        priority_ratio: Fraction of patients to give upcoming appointments (default 60%)
    """
    org = Organization.query.get(org_id)
    if not org:
        print(f"Error: Organization {org_id} not found")
        return False
    
    patients = Patient.query.filter_by(org_id=org_id).all()
    if not patients:
        print(f"No patients found for organization {org_id}")
        return False
    
    print(f"Found {len(patients)} patients for organization '{org.name}'")
    
    provider = Provider.query.filter_by(org_id=org_id, is_active=True).first()
    provider_id = provider.id if provider else None
    
    now = datetime.utcnow()
    priority_window_days = getattr(org, 'prioritization_window_days', 14) or 14
    
    appointment_types = [
        'Annual Physical',
        'Follow-up Visit',
        'Preventive Care',
        'Wellness Check',
        'Lab Review',
        'Consultation',
        'Screening Visit'
    ]
    
    statuses = ['scheduled', 'confirmed', 'pending']
    
    random.shuffle(patients)
    priority_count = int(len(patients) * priority_ratio)
    
    priority_patients = patients[:priority_count]
    dormant_patients = patients[priority_count:]
    
    appointments_created = 0
    
    for patient in priority_patients:
        days_ahead = random.randint(1, priority_window_days - 1)
        hours = random.randint(8, 17)
        minutes = random.choice([0, 15, 30, 45])
        
        appt_date = now + timedelta(days=days_ahead)
        appt_date = appt_date.replace(hour=hours, minute=minutes, second=0, microsecond=0)
        
        appointment = Appointment(
            patient_id=patient.id,
            org_id=org_id,
            provider_id=provider_id,
            appointment_date=appt_date,
            appointment_type=random.choice(appointment_types),
            status=random.choice(statuses),
            notes=f"Test appointment for priority patient - seeded {now.strftime('%Y-%m-%d')}"
        )
        db.session.add(appointment)
        appointments_created += 1
    
    for patient in dormant_patients:
        if random.random() < 0.5:
            days_ago = random.randint(30, 180)
            appt_date = now - timedelta(days=days_ago)
            appt_date = appt_date.replace(hour=random.randint(8, 17), minute=0, second=0, microsecond=0)
            
            appointment = Appointment(
                patient_id=patient.id,
                org_id=org_id,
                provider_id=provider_id,
                appointment_date=appt_date,
                appointment_type=random.choice(appointment_types),
                status='completed',
                notes=f"Past appointment for dormant patient - seeded {now.strftime('%Y-%m-%d')}"
            )
            db.session.add(appointment)
            appointments_created += 1
    
    db.session.commit()
    
    print(f"\nSeeding complete:")
    print(f"  - Priority patients (appointments in next {priority_window_days} days): {len(priority_patients)}")
    print(f"  - Dormant patients (no upcoming appointments): {len(dormant_patients)}")
    print(f"  - Total appointments created: {appointments_created}")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Seed test appointments for sandbox patients')
    parser.add_argument('--org-id', type=int, default=1, help='Organization ID (default: 1)')
    parser.add_argument('--clear', action='store_true', help='Clear existing appointments first')
    parser.add_argument('--priority-ratio', type=float, default=0.6, 
                        help='Ratio of patients to give upcoming appointments (default: 0.6)')
    
    args = parser.parse_args()
    
    with app.app_context():
        if args.clear:
            clear_test_appointments(args.org_id)
        
        success = seed_appointments(args.org_id, args.priority_ratio)
        
        if success:
            print("\nYou can now test the appointment prioritization feature at /screening/list")
            print("Use the Priority/Dormant/All tabs to filter screenings by appointment window.")
        else:
            sys.exit(1)


if __name__ == '__main__':
    main()
