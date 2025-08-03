from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, IntegerField, BooleanField, DateField, PasswordField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional
from wtforms.widgets import TextArea
from models import ScreeningType, Patient

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired()])

class PatientForm(FlaskForm):
    mrn = StringField('Medical Record Number', validators=[DataRequired(), Length(max=20)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    date_of_birth = DateField('Date of Birth', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('M', 'Male'), ('F', 'Female'), ('Other', 'Other')], validators=[DataRequired()])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    address = TextAreaField('Address', validators=[Optional()])
    emergency_contact = StringField('Emergency Contact', validators=[Optional(), Length(max=100)])
    emergency_phone = StringField('Emergency Phone', validators=[Optional(), Length(max=20)])
    insurance_id = StringField('Insurance ID', validators=[Optional(), Length(max=50)])
    primary_physician = StringField('Primary Physician', validators=[Optional(), Length(max=100)])

class ScreeningTypeForm(FlaskForm):
    name = StringField('Screening Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Optional()])
    keywords = TextAreaField('Keywords (one per line)', validators=[Optional()], 
                           render_kw={"rows": 5, "placeholder": "Enter keywords that identify this screening type in documents"})
    eligible_genders = SelectField('Eligible Genders', 
                                 choices=[('all', 'All Genders'), ('M', 'Male Only'), ('F', 'Female Only')],
                                 validators=[DataRequired()])
    min_age = IntegerField('Minimum Age', validators=[Optional(), NumberRange(min=0, max=120)])
    max_age = IntegerField('Maximum Age', validators=[Optional(), NumberRange(min=0, max=120)])
    frequency_years = IntegerField('Frequency (Years)', validators=[Optional(), NumberRange(min=0, max=10)])
    frequency_months = IntegerField('Frequency (Months)', validators=[Optional(), NumberRange(min=0, max=60)])
    trigger_conditions = TextAreaField('Trigger Conditions (one per line)', validators=[Optional()],
                                     render_kw={"rows": 3, "placeholder": "Enter conditions that trigger this screening"})
    is_active = BooleanField('Active')

class DocumentUploadForm(FlaskForm):
    patient_id = SelectField('Patient', coerce=int, validators=[DataRequired()])
    document_type = SelectField('Document Type', 
                               choices=[('lab', 'Laboratory'), ('imaging', 'Imaging'), 
                                      ('consult', 'Consult'), ('hospital', 'Hospital'), 
                                      ('screening', 'Screening')],
                               validators=[DataRequired()])
    document_date = DateField('Document Date', validators=[Optional()])
    file = FileField('Document File', validators=[
        DataRequired(),
        FileAllowed(['pdf', 'jpg', 'jpeg', 'png', 'tiff', 'tif'], 'Only PDF and image files are allowed!')
    ])
    
    def __init__(self, *args, **kwargs):
        super(DocumentUploadForm, self).__init__(*args, **kwargs)
        # Populate patient choices
        self.patient_id.choices = [(0, 'Select Patient')] + [
            (p.id, f"{p.mrn} - {p.full_name}") 
            for p in Patient.query.order_by(Patient.last_name, Patient.first_name).all()
        ]

class ScreeningForm(FlaskForm):
    patient_id = SelectField('Patient', coerce=int, validators=[DataRequired()])
    screening_type_id = SelectField('Screening Type', coerce=int, validators=[DataRequired()])
    status = SelectField('Status', 
                        choices=[('Due', 'Due'), ('Due Soon', 'Due Soon'), 
                               ('Complete', 'Complete'), ('Overdue', 'Overdue')],
                        validators=[DataRequired()])
    last_completed_date = DateField('Last Completed Date', validators=[Optional()])
    notes = TextAreaField('Notes', validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super(ScreeningForm, self).__init__(*args, **kwargs)
        # Populate choices
        self.patient_id.choices = [(0, 'Select Patient')] + [
            (p.id, f"{p.mrn} - {p.full_name}") 
            for p in Patient.query.order_by(Patient.last_name, Patient.first_name).all()
        ]
        self.screening_type_id.choices = [(0, 'Select Screening Type')] + [
            (st.id, st.name) 
            for st in ScreeningType.query.filter_by(is_active=True).order_by(ScreeningType.name).all()
        ]

class ChecklistSettingsForm(FlaskForm):
    name = StringField('Settings Name', validators=[DataRequired(), Length(max=100)])
    lab_cutoff_months = IntegerField('Lab Results Cutoff (Months)', 
                                   validators=[DataRequired(), NumberRange(min=1, max=60)], 
                                   default=12)
    imaging_cutoff_months = IntegerField('Imaging Cutoff (Months)', 
                                       validators=[DataRequired(), NumberRange(min=1, max=60)], 
                                       default=24)
    consult_cutoff_months = IntegerField('Consult Cutoff (Months)', 
                                       validators=[DataRequired(), NumberRange(min=1, max=60)], 
                                       default=12)
    hospital_cutoff_months = IntegerField('Hospital Visits Cutoff (Months)', 
                                        validators=[DataRequired(), NumberRange(min=1, max=60)], 
                                        default=24)
    
class PHIFilterSettingsForm(FlaskForm):
    is_enabled = BooleanField('Enable PHI Filtering')
    filter_ssn = BooleanField('Filter Social Security Numbers')
    filter_phone = BooleanField('Filter Phone Numbers')
    filter_mrn = BooleanField('Filter Medical Record Numbers')
    filter_insurance = BooleanField('Filter Insurance Information')
    filter_addresses = BooleanField('Filter Addresses')
    filter_names = BooleanField('Filter Patient Names')
    filter_dates = BooleanField('Filter Dates (except medical values)')
    preserve_medical_terms = BooleanField('Preserve Medical Terminology')
    confidence_threshold = IntegerField('OCR Confidence Threshold (%)', 
                                      validators=[NumberRange(min=0, max=100)], 
                                      default=80)
