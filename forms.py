from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, IntegerField, SelectField, BooleanField, DateField, PasswordField, SubmitField, FloatField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional, EqualTo
from wtforms.widgets import TextArea

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=64, message='Username must be between 3 and 64 characters long')
    ])
    email = StringField('Email', validators=[
        DataRequired(),
        Email(),
        Length(max=120)
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    password_confirm = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Create Account')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match')
    ])
    submit = SubmitField('Change Password')

class ScreeningTypeForm(FlaskForm):
    name = StringField('Screening Name', validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField('Description', validators=[Length(max=500)])
    keywords = TextAreaField('Keywords (comma-separated)', 
                           validators=[Length(max=1000)],
                           render_kw={'placeholder': 'mammogram, breast cancer screening, mammography'})
    eligible_genders = SelectField('Eligible Genders', 
                                 choices=[('both', 'Both Genders'), ('M', 'Male Only'), ('F', 'Female Only')],
                                 default='both')
    min_age = IntegerField('Minimum Age', validators=[Optional(), NumberRange(min=0, max=150)])
    max_age = IntegerField('Maximum Age', validators=[Optional(), NumberRange(min=0, max=150)])
    frequency_years = FloatField('Frequency (Years)', 
                               validators=[DataRequired(), NumberRange(min=0.08, max=50)],  # 0.08 = ~1 month
                               render_kw={'step': '0.25', 'placeholder': '1.0 for annual, 0.25 for quarterly'})
    trigger_conditions = TextAreaField('Trigger Conditions (comma-separated)', 
                                     validators=[Length(max=1000)],
                                     render_kw={'placeholder': 'diabetes, hypertension, family history'})
    submit = SubmitField('Save Screening Type')

class ScreeningSettingsForm(FlaskForm):
    """Form for configuring screening settings"""
    lab_cutoff_months = IntegerField('Lab Results Cutoff (months)', 
                                   validators=[DataRequired(), NumberRange(min=1, max=60)],
                                   default=12)
    imaging_cutoff_months = IntegerField('Imaging Studies Cutoff (months)', 
                                       validators=[DataRequired(), NumberRange(min=1, max=60)],
                                       default=12)
    consult_cutoff_months = IntegerField('Specialist Consults Cutoff (months)', 
                                       validators=[DataRequired(), NumberRange(min=1, max=60)],
                                       default=12)
    hospital_cutoff_months = IntegerField('Hospital Visits Cutoff (months)', 
                                        validators=[DataRequired(), NumberRange(min=1, max=60)],
                                        default=12)
    default_status_options = TextAreaField('Default Status Options', 
                                         validators=[DataRequired()],
                                         default="Due\nDue Soon\nComplete\nOverdue")
    default_checklist_items = TextAreaField('Default Checklist Items', 
                                          validators=[DataRequired()],
                                          default="Review screening results\nDiscuss recommendations\nSchedule follow-up\nUpdate care plan")
    submit = SubmitField('Save Settings')

# Keep ChecklistSettingsForm as an alias for backward compatibility
ChecklistSettingsForm = ScreeningSettingsForm

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