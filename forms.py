from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, IntegerField, SelectField, BooleanField, DateField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = StringField('Password', validators=[DataRequired(), Length(min=6)])

class ScreeningTypeForm(FlaskForm):
    name = StringField('Screening Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description')
    keywords = TextAreaField('Keywords (comma-separated)', 
                            description='Keywords to match in document names and content')
    min_age = IntegerField('Minimum Age', validators=[Optional(), NumberRange(min=0, max=120)])
    max_age = IntegerField('Maximum Age', validators=[Optional(), NumberRange(min=0, max=120)])
    gender_restriction = SelectField('Gender Restriction', 
                                   choices=[('any', 'Any'), ('male', 'Male'), ('female', 'Female')])
    frequency_value = IntegerField('Frequency Value', validators=[DataRequired(), NumberRange(min=1)])
    frequency_unit = SelectField('Frequency Unit', 
                               choices=[('months', 'Months'), ('years', 'Years')])
    trigger_conditions = TextAreaField('Trigger Conditions (comma-separated)',
                                     description='Medical conditions that trigger this screening')

class PatientForm(FlaskForm):
    mrn = StringField('Medical Record Number', validators=[DataRequired(), Length(max=50)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    date_of_birth = DateField('Date of Birth', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('male', 'Male'), ('female', 'Female')])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Length(max=120)])
    address = TextAreaField('Address')

class ChecklistSettingsForm(FlaskForm):
    labs_cutoff_months = IntegerField('Labs Cutoff (months)', 
                                    validators=[DataRequired(), NumberRange(min=1, max=60)],
                                    default=12)
    imaging_cutoff_months = IntegerField('Imaging Cutoff (months)', 
                                       validators=[DataRequired(), NumberRange(min=1, max=60)],
                                       default=12)
    consults_cutoff_months = IntegerField('Consults Cutoff (months)', 
                                        validators=[DataRequired(), NumberRange(min=1, max=60)],
                                        default=6)
    hospital_cutoff_months = IntegerField('Hospital Visits Cutoff (months)', 
                                        validators=[DataRequired(), NumberRange(min=1, max=60)],
                                        default=12)

class PHIFilterSettingsForm(FlaskForm):
    filter_enabled = BooleanField('Enable PHI Filtering')
    filter_ssn = BooleanField('Filter Social Security Numbers')
    filter_phone = BooleanField('Filter Phone Numbers')
    filter_mrn = BooleanField('Filter Medical Record Numbers')
    filter_insurance = BooleanField('Filter Insurance Information')
    filter_addresses = BooleanField('Filter Addresses')
    filter_names = BooleanField('Filter Patient Names')
    filter_dates = BooleanField('Filter Dates (preserve medical values)')

class DocumentUploadForm(FlaskForm):
    file = StringField('Document File', validators=[DataRequired()])
    document_type = SelectField('Document Type', 
                               choices=[('lab', 'Lab Results'), ('imaging', 'Imaging'), 
                                       ('consult', 'Consult Note'), ('hospital', 'Hospital Visit'),
                                       ('other', 'Other')])
    document_date = DateField('Document Date', validators=[Optional()])
