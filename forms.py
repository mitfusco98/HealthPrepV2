from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, TextAreaField, IntegerField, SelectField, DateField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')

class ScreeningTypeForm(FlaskForm):
    name = StringField('Screening Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description')
    keywords = TextAreaField('Keywords (comma-separated)', 
                            description='Keywords to match in documents')
    gender = SelectField('Gender', choices=[('any', 'Any'), ('M', 'Male'), ('F', 'Female')])
    min_age = IntegerField('Minimum Age', validators=[Optional(), NumberRange(min=0, max=150)])
    max_age = IntegerField('Maximum Age', validators=[Optional(), NumberRange(min=0, max=150)])
    frequency_value = IntegerField('Frequency', validators=[DataRequired(), NumberRange(min=1)])
    frequency_unit = SelectField('Frequency Unit', 
                               choices=[('months', 'Months'), ('years', 'Years')],
                               validators=[DataRequired()])
    trigger_conditions = TextAreaField('Trigger Conditions (comma-separated)',
                                     description='Medical conditions that trigger this screening')

class PatientForm(FlaskForm):
    mrn = StringField('MRN', validators=[DataRequired(), Length(max=50)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=100)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=100)])
    date_of_birth = DateField('Date of Birth', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    address = TextAreaField('Address')

class ChecklistSettingsForm(FlaskForm):
    labs_cutoff_months = IntegerField('Labs Cutoff (months)', 
                                    validators=[DataRequired(), NumberRange(min=1, max=60)],
                                    default=12)
    imaging_cutoff_months = IntegerField('Imaging Cutoff (months)',
                                       validators=[DataRequired(), NumberRange(min=1, max=60)],
                                       default=24)
    consults_cutoff_months = IntegerField('Consults Cutoff (months)',
                                        validators=[DataRequired(), NumberRange(min=1, max=60)],
                                        default=12)
    hospital_cutoff_months = IntegerField('Hospital Visits Cutoff (months)',
                                        validators=[DataRequired(), NumberRange(min=1, max=60)],
                                        default=12)

class PHIFilterForm(FlaskForm):
    is_enabled = BooleanField('Enable PHI Filtering', default=True)
    filter_ssn = BooleanField('Filter Social Security Numbers', default=True)
    filter_phone = BooleanField('Filter Phone Numbers', default=True)
    filter_mrn = BooleanField('Filter Medical Record Numbers', default=True)
    filter_insurance = BooleanField('Filter Insurance IDs', default=True)
    filter_addresses = BooleanField('Filter Addresses', default=True)
    filter_names = BooleanField('Filter Names', default=True)
    filter_dates = BooleanField('Filter Dates', default=True)
    preserve_medical_terms = BooleanField('Preserve Medical Terms', default=True)
