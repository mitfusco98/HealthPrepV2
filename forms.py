from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, IntegerField, SelectField, BooleanField, DateField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional
from wtforms.widgets import TextArea

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

class ScreeningTypeForm(FlaskForm):
    name = StringField('Screening Name', validators=[DataRequired(), Length(min=1, max=100)])
    description = TextAreaField('Description')
    keywords = TextAreaField('Keywords (one per line)', widget=TextArea())
    min_age = IntegerField('Minimum Age', validators=[Optional(), NumberRange(min=0, max=150)])
    max_age = IntegerField('Maximum Age', validators=[Optional(), NumberRange(min=0, max=150)])
    gender = SelectField('Gender', choices=[('', 'Both'), ('M', 'Male'), ('F', 'Female')])
    frequency_value = IntegerField('Frequency', validators=[Optional(), NumberRange(min=1)])
    frequency_unit = SelectField('Frequency Unit', choices=[('years', 'Years'), ('months', 'Months')])
    trigger_conditions = TextAreaField('Trigger Conditions (one per line)', widget=TextArea())
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Save Screening Type')

class PatientForm(FlaskForm):
    mrn = StringField('MRN', validators=[DataRequired(), Length(min=1, max=50)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(min=1, max=100)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(min=1, max=100)])
    date_of_birth = DateField('Date of Birth', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')], validators=[DataRequired()])
    submit = SubmitField('Add Patient')

class DocumentUploadForm(FlaskForm):
    file = FileField('Document File', validators=[DataRequired()])
    document_type = SelectField('Document Type', choices=[
        ('lab', 'Lab Results'),
        ('imaging', 'Imaging'),
        ('consult', 'Consult Note'),
        ('hospital', 'Hospital Record'),
        ('other', 'Other')
    ])
    document_date = DateField('Document Date')
    submit = SubmitField('Upload Document')

class PrepSheetSettingsForm(FlaskForm):
    labs_cutoff_months = IntegerField('Labs Cutoff (months)',
                                     validators=[DataRequired(), NumberRange(min=1, max=120)],
                                     default=12)
    imaging_cutoff_months = IntegerField('Imaging Cutoff (months)',
                                        validators=[DataRequired(), NumberRange(min=1, max=120)],
                                        default=12)
    consults_cutoff_months = IntegerField('Consults Cutoff (months)',
                                         validators=[DataRequired(), NumberRange(min=1, max=120)],
                                         default=12)
    hospital_cutoff_months = IntegerField('Hospital Records Cutoff (months)',
                                         validators=[DataRequired(), NumberRange(min=1, max=120)],
                                         default=12)
    submit = SubmitField('Save Settings')

class PHIFilterForm(FlaskForm):
    filter_enabled = BooleanField('Enable PHI Filtering', default=True)
    filter_ssn = BooleanField('Filter SSN', default=True)
    filter_phone = BooleanField('Filter Phone Numbers', default=True)
    filter_mrn = BooleanField('Filter MRN', default=True)
    filter_insurance = BooleanField('Filter Insurance Info', default=True)
    filter_addresses = BooleanField('Filter Addresses', default=True)
    filter_names = BooleanField('Filter Names', default=True)
    filter_dates = BooleanField('Filter Dates', default=True)
    submit = SubmitField('Save PHI Settings')

class ChecklistSettingsForm(FlaskForm):
    lab_cutoff_months = IntegerField('Lab Results Cutoff (Months)', validators=[DataRequired()])
    imaging_cutoff_months = IntegerField('Imaging Results Cutoff (Months)', validators=[DataRequired()])
    consult_cutoff_months = IntegerField('Consult Notes Cutoff (Months)', validators=[DataRequired()])
    hospital_cutoff_months = IntegerField('Hospital Records Cutoff (Months)', validators=[DataRequired()])
    submit = SubmitField('Update Settings')