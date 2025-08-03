from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, IntegerField, DateField, BooleanField, PasswordField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional
from datetime import date

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    password = PasswordField('Password', validators=[DataRequired()])

class PatientForm(FlaskForm):
    mrn = StringField('Medical Record Number', validators=[DataRequired(), Length(max=50)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=100)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=100)])
    date_of_birth = DateField('Date of Birth', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')], validators=[DataRequired()])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=120)])
    address = TextAreaField('Address', validators=[Optional()])

class ScreeningTypeForm(FlaskForm):
    name = StringField('Screening Name', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Description', validators=[Optional()])
    keywords = TextAreaField('Keywords (comma-separated)', validators=[Optional()])
    eligible_genders = SelectField('Eligible Genders', 
                                 choices=[('both', 'Both'), ('M', 'Male Only'), ('F', 'Female Only')],
                                 validators=[DataRequired()])
    min_age = IntegerField('Minimum Age', validators=[Optional(), NumberRange(min=0, max=120)])
    max_age = IntegerField('Maximum Age', validators=[Optional(), NumberRange(min=0, max=120)])
    frequency_number = IntegerField('Frequency Number', validators=[DataRequired(), NumberRange(min=1)])
    frequency_unit = SelectField('Frequency Unit', 
                               choices=[('months', 'Months'), ('years', 'Years')],
                               validators=[DataRequired()])
    trigger_conditions = TextAreaField('Trigger Conditions (one per line)', validators=[Optional()])
    is_active = BooleanField('Active', default=True)

class DocumentUploadForm(FlaskForm):
    file = FileField('Document File', validators=[
        FileRequired(),
        FileAllowed(['pdf', 'jpg', 'jpeg', 'png', 'tiff'], 'Only PDF and image files are allowed.')
    ])
    document_type = SelectField('Document Type', 
                              choices=[
                                  ('lab', 'Laboratory Results'),
                                  ('imaging', 'Imaging Studies'),
                                  ('consult', 'Specialist Consult'),
                                  ('hospital', 'Hospital Records'),
                                  ('other', 'Other')
                              ],
                              validators=[DataRequired()])
    document_date = DateField('Document Date', validators=[DataRequired()], default=date.today)

class ChecklistSettingsForm(FlaskForm):
    cutoff_labs = IntegerField('Labs Cutoff (months)', validators=[DataRequired(), NumberRange(min=1, max=120)], default=12)
    cutoff_imaging = IntegerField('Imaging Cutoff (months)', validators=[DataRequired(), NumberRange(min=1, max=120)], default=24)
    cutoff_consults = IntegerField('Consults Cutoff (months)', validators=[DataRequired(), NumberRange(min=1, max=120)], default=12)
    cutoff_hospital = IntegerField('Hospital Records Cutoff (months)', validators=[DataRequired(), NumberRange(min=1, max=120)], default=24)
