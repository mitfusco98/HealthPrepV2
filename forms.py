from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, IntegerField, SelectField, BooleanField, PasswordField, DateField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange
from wtforms.widgets import TextArea

class LoginForm(FlaskForm):
    """User login form"""
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    password = PasswordField('Password', validators=[DataRequired()])

class ScreeningTypeForm(FlaskForm):
    """Form for creating/editing screening types"""
    name = StringField('Screening Name', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description')
    keywords = TextAreaField('Keywords (one per line)', widget=TextArea())
    min_age = IntegerField('Minimum Age', validators=[Optional(), NumberRange(min=0, max=120)])
    max_age = IntegerField('Maximum Age', validators=[Optional(), NumberRange(min=0, max=120)])
    gender = SelectField('Gender', choices=[('', 'Any'), ('M', 'Male'), ('F', 'Female')], default='')
    frequency_number = IntegerField('Frequency Number', validators=[DataRequired(), NumberRange(min=1)])
    frequency_unit = SelectField('Frequency Unit', 
                                choices=[('years', 'Years'), ('months', 'Months'), ('days', 'Days')],
                                default='years')
    trigger_conditions = TextAreaField('Trigger Conditions (one per line)', widget=TextArea())
    is_active = BooleanField('Active', default=True)

class PatientForm(FlaskForm):
    """Form for creating/editing patients"""
    mrn = StringField('Medical Record Number', validators=[DataRequired(), Length(max=50)])
    name = StringField('Full Name', validators=[DataRequired(), Length(max=200)])
    date_of_birth = DateField('Date of Birth', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')], 
                        validators=[DataRequired()])

class DocumentUploadForm(FlaskForm):
    """Form for uploading medical documents"""
    document = FileField('Medical Document', 
                        validators=[DataRequired(), 
                                  FileAllowed(['pdf', 'jpg', 'jpeg', 'png', 'tiff'], 
                                            'Only PDF and image files allowed')])
    document_type = SelectField('Document Type', 
                               choices=[('lab', 'Laboratory'), ('imaging', 'Imaging'), 
                                      ('consult', 'Consultation'), ('hospital', 'Hospital')],
                               validators=[DataRequired()])

class ChecklistSettingsForm(FlaskForm):
    """Form for configuring prep sheet settings"""
    lab_cutoff_months = IntegerField('Lab Results Cutoff (months)', 
                                   validators=[DataRequired(), NumberRange(min=1, max=120)],
                                   default=12)
    imaging_cutoff_months = IntegerField('Imaging Studies Cutoff (months)', 
                                       validators=[DataRequired(), NumberRange(min=1, max=120)],
                                       default=24)
    consult_cutoff_months = IntegerField('Consultations Cutoff (months)', 
                                       validators=[DataRequired(), NumberRange(min=1, max=120)],
                                       default=12)
    hospital_cutoff_months = IntegerField('Hospital Stays Cutoff (months)', 
                                        validators=[DataRequired(), NumberRange(min=1, max=120)],
                                        default=24)

class PHIFilterForm(FlaskForm):
    """Form for PHI filtering settings"""
    is_enabled = BooleanField('Enable PHI Filtering', default=True)
    filter_ssn = BooleanField('Filter Social Security Numbers', default=True)
    filter_phone = BooleanField('Filter Phone Numbers', default=True)
    filter_mrn = BooleanField('Filter Medical Record Numbers', default=True)
    filter_insurance = BooleanField('Filter Insurance Information', default=True)
    filter_addresses = BooleanField('Filter Addresses', default=True)
    filter_names = BooleanField('Filter Patient Names', default=True)
    filter_dates = BooleanField('Filter Dates (preserve medical values)', default=True)
