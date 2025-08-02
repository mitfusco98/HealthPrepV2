"""
WTForms for form handling and validation
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, TextAreaField, SelectField, IntegerField, BooleanField, PasswordField, DateField, FloatField
from wtforms.validators import DataRequired, Length, Email, NumberRange, Optional, ValidationError
from wtforms.widgets import TextArea
from config.settings import GENDER_OPTIONS, DOCUMENT_TYPES, SCREENING_STATUSES
from config.security import validate_password_strength
import re

class LoginForm(FlaskForm):
    """User login form"""
    username = StringField('Username', validators=[
        DataRequired(message="Username is required"),
        Length(min=3, max=64, message="Username must be between 3 and 64 characters")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required")
    ])

class PatientForm(FlaskForm):
    """Patient registration/edit form"""
    first_name = StringField('First Name', validators=[
        DataRequired(message="First name is required"),
        Length(min=1, max=100, message="First name must be between 1 and 100 characters")
    ])
    last_name = StringField('Last Name', validators=[
        DataRequired(message="Last name is required"),
        Length(min=1, max=100, message="Last name must be between 1 and 100 characters")
    ])
    date_of_birth = DateField('Date of Birth', validators=[
        DataRequired(message="Date of birth is required")
    ])
    gender = SelectField('Gender', choices=[
        ('M', 'Male'),
        ('F', 'Female'),
        ('Other', 'Other')
    ], validators=[DataRequired(message="Gender is required")])
    mrn = StringField('Medical Record Number', validators=[
        DataRequired(message="MRN is required"),
        Length(min=1, max=50, message="MRN must be between 1 and 50 characters")
    ])
    
    def validate_mrn(self, field):
        """Validate MRN format"""
        if not re.match(r'^[A-Za-z0-9\-]+$', field.data):
            raise ValidationError("MRN can only contain letters, numbers, and hyphens")

class ScreeningTypeForm(FlaskForm):
    """Screening type creation/edit form"""
    name = StringField('Screening Name', validators=[
        DataRequired(message="Screening name is required"),
        Length(min=1, max=200, message="Name must be between 1 and 200 characters")
    ])
    description = TextAreaField('Description', validators=[
        Optional(),
        Length(max=1000, message="Description cannot exceed 1000 characters")
    ])
    keywords = TextAreaField('Keywords (one per line)', validators=[
        Optional()
    ], description="Enter keywords that will be used to match documents to this screening type")
    
    gender_filter = SelectField('Gender Filter', choices=[
        ('', 'All Genders'),
        ('M', 'Male Only'),
        ('F', 'Female Only')
    ], validators=[Optional()])
    
    min_age = IntegerField('Minimum Age', validators=[
        Optional(),
        NumberRange(min=0, max=120, message="Age must be between 0 and 120")
    ])
    max_age = IntegerField('Maximum Age', validators=[
        Optional(),
        NumberRange(min=0, max=120, message="Age must be between 0 and 120")
    ])
    
    frequency_value = IntegerField('Frequency Value', validators=[
        DataRequired(message="Frequency value is required"),
        NumberRange(min=1, max=50, message="Frequency must be between 1 and 50")
    ])
    frequency_unit = SelectField('Frequency Unit', choices=[
        ('days', 'Days'),
        ('months', 'Months'),
        ('years', 'Years')
    ], validators=[DataRequired(message="Frequency unit is required")])
    
    trigger_conditions = TextAreaField('Trigger Conditions (one per line)', validators=[
        Optional()
    ], description="Medical conditions that trigger this screening")
    
    is_active = BooleanField('Active', default=True)
    
    def validate_max_age(self, field):
        """Validate max age is greater than min age"""
        if field.data and self.min_age.data and field.data <= self.min_age.data:
            raise ValidationError("Maximum age must be greater than minimum age")

class DocumentUploadForm(FlaskForm):
    """Document upload form"""
    file = FileField('Document File', validators=[
        FileRequired(message="Please select a file to upload"),
        FileAllowed(['pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'], 
                   message="Only PDF, PNG, JPG, JPEG, TIFF, and BMP files are allowed")
    ])
    patient_id = SelectField('Patient', coerce=int, validators=[
        DataRequired(message="Please select a patient")
    ])
    document_type = SelectField('Document Type', choices=[
        ('lab', 'Laboratory'),
        ('imaging', 'Imaging'),
        ('consult', 'Consultation'),
        ('hospital', 'Hospital'),
        ('general', 'General')
    ], validators=[DataRequired(message="Please select document type")])

class PrepSheetSettingsForm(FlaskForm):
    """Prep sheet cutoff settings form"""
    lab_cutoff_months = IntegerField('Lab Results Cutoff (months)', validators=[
        DataRequired(message="Lab cutoff is required"),
        NumberRange(min=1, max=60, message="Cutoff must be between 1 and 60 months")
    ], default=12)
    
    imaging_cutoff_months = IntegerField('Imaging Cutoff (months)', validators=[
        DataRequired(message="Imaging cutoff is required"),
        NumberRange(min=1, max=60, message="Cutoff must be between 1 and 60 months")
    ], default=12)
    
    consult_cutoff_months = IntegerField('Consultation Cutoff (months)', validators=[
        DataRequired(message="Consult cutoff is required"),
        NumberRange(min=1, max=60, message="Cutoff must be between 1 and 60 months")
    ], default=12)
    
    hospital_cutoff_months = IntegerField('Hospital Visit Cutoff (months)', validators=[
        DataRequired(message="Hospital cutoff is required"),
        NumberRange(min=1, max=60, message="Cutoff must be between 1 and 60 months")
    ], default=12)

class PHIFilterForm(FlaskForm):
    """PHI filtering settings form"""
    filter_enabled = BooleanField('Enable PHI Filtering', default=True)
    filter_ssn = BooleanField('Filter Social Security Numbers', default=True)
    filter_phone = BooleanField('Filter Phone Numbers', default=True)
    filter_mrn = BooleanField('Filter Medical Record Numbers', default=True)
    filter_insurance = BooleanField('Filter Insurance Information', default=True)
    filter_addresses = BooleanField('Filter Addresses', default=True)
    filter_names = BooleanField('Filter Patient Names', default=True)
    filter_dates = BooleanField('Filter Dates', default=True)

class UserForm(FlaskForm):
    """User creation/edit form"""
    username = StringField('Username', validators=[
        DataRequired(message="Username is required"),
        Length(min=3, max=64, message="Username must be between 3 and 64 characters")
    ])
    email = StringField('Email', validators=[
        DataRequired(message="Email is required"),
        Email(message="Please enter a valid email address"),
        Length(max=120, message="Email cannot exceed 120 characters")
    ])
    password = PasswordField('Password', validators=[
        Optional()  # Optional for edit forms
    ])
    is_admin = BooleanField('Administrator', default=False)
    
    def validate_username(self, field):
        """Validate username format"""
        if not re.match(r'^[A-Za-z0-9_]+$', field.data):
            raise ValidationError("Username can only contain letters, numbers, and underscores")
    
    def validate_password(self, field):
        """Validate password strength"""
        if field.data:  # Only validate if password is provided
            errors = validate_password_strength(field.data)
            if errors:
                raise ValidationError('; '.join(errors))

class AdminLogFilterForm(FlaskForm):
    """Admin log filtering form"""
    event_type = StringField('Event Type', validators=[Optional()])
    date_from = DateField('From Date', validators=[Optional()])
    date_to = DateField('To Date', validators=[Optional()])
    user_id = SelectField('User', coerce=int, validators=[Optional()])
    
    def validate_date_to(self, field):
        """Validate date range"""
        if field.data and self.date_from.data and field.data < self.date_from.data:
            raise ValidationError("End date must be after start date")

class FHIRSyncForm(FlaskForm):
    """FHIR data synchronization form"""
    fhir_patient_id = StringField('FHIR Patient ID', validators=[
        DataRequired(message="FHIR Patient ID is required"),
        Length(min=1, max=100, message="ID must be between 1 and 100 characters")
    ])
    local_patient_id = SelectField('Local Patient', coerce=int, validators=[
        DataRequired(message="Please select a local patient")
    ])
    sync_observations = BooleanField('Sync Observations', default=True)
    sync_reports = BooleanField('Sync Diagnostic Reports', default=True)
    sync_conditions = BooleanField('Sync Conditions', default=True)
    sync_medications = BooleanField('Sync Medications', default=True)

class ScreeningPresetForm(FlaskForm):
    """Screening preset import/export form"""
    preset_name = StringField('Preset Name', validators=[
        DataRequired(message="Preset name is required"),
        Length(min=1, max=100, message="Name must be between 1 and 100 characters")
    ])
    specialty = SelectField('Medical Specialty', choices=[
        ('primary_care', 'Primary Care'),
        ('cardiology', 'Cardiology'),
        ('oncology', 'Oncology'),
        ('womens_health', 'Women\'s Health'),
        ('geriatrics', 'Geriatrics'),
        ('pediatrics', 'Pediatrics'),
        ('endocrinology', 'Endocrinology'),
        ('custom', 'Custom')
    ], validators=[DataRequired(message="Please select a specialty")])
    description = TextAreaField('Description', validators=[
        Optional(),
        Length(max=500, message="Description cannot exceed 500 characters")
    ])

class BulkScreeningForm(FlaskForm):
    """Bulk screening processing form"""
    patient_filter = SelectField('Patient Filter', choices=[
        ('all', 'All Patients'),
        ('due', 'Patients with Due Screenings'),
        ('selected', 'Selected Patients')
    ], validators=[DataRequired(message="Please select patient filter")])
    
    screening_types = SelectField('Screening Types', choices=[
        ('all', 'All Active Screening Types'),
        ('selected', 'Selected Types')
    ], validators=[DataRequired(message="Please select screening types")])
    
    generate_prep_sheets = BooleanField('Generate Prep Sheets', default=False)
    send_notifications = BooleanField('Send Notifications', default=False)

