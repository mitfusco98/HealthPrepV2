from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, IntegerField, BooleanField, PasswordField, DateField, FloatField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange
from wtforms.widgets import TextArea

class LoginForm(FlaskForm):
    """User login form"""
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    password = PasswordField('Password', validators=[DataRequired()])

class ScreeningTypeForm(FlaskForm):
    """Form for creating/editing screening types"""
    name = StringField('Screening Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=500)])
    keywords = TextAreaField('Keywords (one per line)', validators=[Optional()], 
                           render_kw={"rows": 4, "placeholder": "mammogram\nbreast screening\nmammo"})
    gender_criteria = SelectField('Gender Criteria', 
                                choices=[('ALL', 'All Genders'), ('M', 'Male Only'), ('F', 'Female Only')],
                                default='ALL')
    min_age = IntegerField('Minimum Age', validators=[Optional(), NumberRange(min=0, max=120)])
    max_age = IntegerField('Maximum Age', validators=[Optional(), NumberRange(min=0, max=120)])
    frequency_years = IntegerField('Frequency (Years)', validators=[Optional(), NumberRange(min=0, max=10)])
    frequency_months = IntegerField('Frequency (Months)', validators=[Optional(), NumberRange(min=0, max=60)])
    trigger_conditions = TextAreaField('Trigger Conditions (one per line)', validators=[Optional()],
                                     render_kw={"rows": 3, "placeholder": "diabetes\nhypertension"})
    is_active = BooleanField('Active', default=True)

class PatientForm(FlaskForm):
    """Form for patient data entry"""
    mrn = StringField('Medical Record Number', validators=[DataRequired(), Length(max=50)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=100)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=100)])
    date_of_birth = DateField('Date of Birth', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('M', 'Male'), ('F', 'Female'), ('Other', 'Other')],
                        validators=[DataRequired()])
    phone = StringField('Phone Number', validators=[Optional(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    address = TextAreaField('Address', validators=[Optional()], render_kw={"rows": 3})
    emergency_contact = StringField('Emergency Contact', validators=[Optional(), Length(max=200)])

class PHISettingsForm(FlaskForm):
    """Form for PHI filtering settings"""
    filter_enabled = BooleanField('Enable PHI Filtering', default=True)
    filter_ssn = BooleanField('Filter Social Security Numbers', default=True)
    filter_phone = BooleanField('Filter Phone Numbers', default=True)
    filter_mrn = BooleanField('Filter Medical Record Numbers', default=True)
    filter_addresses = BooleanField('Filter Addresses', default=True)
    filter_names = BooleanField('Filter Patient Names', default=True)
    filter_dates = BooleanField('Filter Dates (Be Careful - May Remove Medical Dates)', default=False)
    custom_patterns = TextAreaField('Custom Regex Patterns (one per line)', validators=[Optional()],
                                  render_kw={"rows": 4, "placeholder": "\\d{3}-\\d{2}-\\d{4}"})

class ChecklistSettingsForm(FlaskForm):
    """Form for prep sheet checklist settings"""
    labs_cutoff_months = IntegerField('Labs Cutoff (Months)', 
                                    validators=[NumberRange(min=1, max=120)], default=12)
    imaging_cutoff_months = IntegerField('Imaging Cutoff (Months)', 
                                       validators=[NumberRange(min=1, max=120)], default=24)
    consults_cutoff_months = IntegerField('Consults Cutoff (Months)', 
                                        validators=[NumberRange(min=1, max=120)], default=12)
    hospital_cutoff_months = IntegerField('Hospital Stays Cutoff (Months)', 
                                        validators=[NumberRange(min=1, max=120)], default=24)
    default_items = TextAreaField('Default Checklist Items (one per line)', validators=[Optional()],
                                render_kw={"rows": 6, "placeholder": "Review current medications\nCheck vital signs\nUpdate allergies"})
