from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, IntegerField, SelectField, BooleanField, DateField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange
from wtforms.widgets import TextArea

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

class PatientForm(FlaskForm):
    mrn = StringField('MRN', validators=[DataRequired(), Length(max=50)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=100)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=100)])
    date_of_birth = DateField('Date of Birth', validators=[Optional()])
    gender = SelectField('Gender', choices=[('', 'Select...'), ('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')], validators=[Optional()])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    address = TextAreaField('Address', validators=[Optional()])
    submit = SubmitField('Save Patient')

class ScreeningTypeForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Optional()])
    keywords = TextAreaField('Keywords (one per line)', validators=[Optional()])
    frequency_number = IntegerField('Frequency Number', validators=[DataRequired(), NumberRange(min=1)])
    frequency_unit = SelectField('Frequency Unit', 
                                choices=[('days', 'Days'), ('weeks', 'Weeks'), ('months', 'Months'), ('years', 'Years')],
                                validators=[DataRequired()])
    min_age = IntegerField('Minimum Age', validators=[Optional(), NumberRange(min=0, max=150)])
    max_age = IntegerField('Maximum Age', validators=[Optional(), NumberRange(min=0, max=150)])
    gender_criteria = SelectField('Gender Criteria',
                                 choices=[('Both', 'Both'), ('Male', 'Male'), ('Female', 'Female')],
                                 validators=[DataRequired()])
    trigger_conditions = TextAreaField('Trigger Conditions (one per line)', validators=[Optional()])
    is_active = BooleanField('Active')
    submit = SubmitField('Save Screening Type')

class ConditionForm(FlaskForm):
    condition_name = StringField('Condition Name', validators=[DataRequired(), Length(max=200)])
    icd_code = StringField('ICD Code', validators=[Optional(), Length(max=20)])
    diagnosis_date = DateField('Diagnosis Date', validators=[Optional()])
    status = SelectField('Status', 
                        choices=[('active', 'Active'), ('resolved', 'Resolved'), ('inactive', 'Inactive')],
                        validators=[DataRequired()])
    submit = SubmitField('Save Condition')

class DocumentUploadForm(FlaskForm):
    document_type = SelectField('Document Type',
                               choices=[('lab', 'Lab Result'), ('consult', 'Consultation'), ('imaging', 'Imaging'), ('other', 'Other')],
                               validators=[DataRequired()])
    document_date = DateField('Document Date', validators=[Optional()])
    submit = SubmitField('Upload Document')