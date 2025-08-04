from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, IntegerField, BooleanField, DateField, PasswordField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional
from wtforms.widgets import TextArea

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')

class ScreeningTypeForm(FlaskForm):
    name = StringField('Screening Name', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description')
    keywords = TextAreaField('Keywords (one per line)', widget=TextArea())
    min_age = IntegerField('Minimum Age', validators=[Optional(), NumberRange(min=0, max=150)])
    max_age = IntegerField('Maximum Age', validators=[Optional(), NumberRange(min=0, max=150)])
    gender_restriction = SelectField('Gender', choices=[('', 'Any'), ('M', 'Male'), ('F', 'Female')])
    frequency_value = IntegerField('Frequency', validators=[DataRequired(), NumberRange(min=1)])
    frequency_unit = SelectField('Unit', choices=[('months', 'Months'), ('years', 'Years')], validators=[DataRequired()])
    trigger_conditions = TextAreaField('Trigger Conditions (one per line)', widget=TextArea())
    is_active = BooleanField('Active', default=True)

class PatientForm(FlaskForm):
    mrn = StringField('MRN', validators=[DataRequired(), Length(max=50)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=100)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=100)])
    date_of_birth = DateField('Date of Birth', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('M', 'Male'), ('F', 'Female')], validators=[DataRequired()])

class DocumentUploadForm(FlaskForm):
    document_type = SelectField('Document Type', 
                               choices=[('lab', 'Laboratory'), ('imaging', 'Imaging'), 
                                      ('consult', 'Consult'), ('hospital', 'Hospital')],
                               validators=[DataRequired()])
    document_date = DateField('Document Date', validators=[DataRequired()])

class ChecklistSettingsForm(FlaskForm):
    labs_cutoff_months = IntegerField('Labs Cutoff (months)', validators=[DataRequired(), NumberRange(min=1, max=120)])
    imaging_cutoff_months = IntegerField('Imaging Cutoff (months)', validators=[DataRequired(), NumberRange(min=1, max=120)])
    consults_cutoff_months = IntegerField('Consults Cutoff (months)', validators=[DataRequired(), NumberRange(min=1, max=120)])
    hospital_cutoff_months = IntegerField('Hospital Cutoff (months)', validators=[DataRequired(), NumberRange(min=1, max=120)])

class PHISettingsForm(FlaskForm):
    filter_enabled = BooleanField('Enable PHI Filtering')
    filter_ssn = BooleanField('Filter SSN')
    filter_phone = BooleanField('Filter Phone Numbers')
    filter_mrn = BooleanField('Filter MRN')
    filter_addresses = BooleanField('Filter Addresses')
    filter_names = BooleanField('Filter Names')
    filter_dates = BooleanField('Filter Dates')