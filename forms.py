from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import SelectField, StringField, DateField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Optional
from datetime import date

class DocumentUploadForm(FlaskForm):
    patient_id = SelectField('Patient', coerce=int, validators=[DataRequired()], choices=[])
    file = FileField('Document File', validators=[
        FileRequired(),
        FileAllowed(['pdf', 'png', 'jpg', 'jpeg', 'tiff', 'tif'], 'Only PDF and image files allowed!')
    ])
    document_type = SelectField('Document Type', choices=[
        ('lab', 'Lab Results'),
        ('imaging', 'Imaging Study'),
        ('consult', 'Consultation'),
        ('hospital', 'Hospital Report'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    document_date = DateField('Document Date', validators=[Optional()], default=date.today)
    process_ocr = BooleanField('Process with OCR', default=True)
    apply_phi_filter = BooleanField('Apply PHI Filtering', default=True)
    submit = SubmitField('Upload Document')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = StringField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class ScreeningTypeForm(FlaskForm):
    name = StringField('Screening Name', validators=[DataRequired()])
    description = StringField('Description')
    keywords = StringField('Keywords (comma-separated)')
    frequency_value = SelectField('Frequency', coerce=int, choices=[
        (3, '3'), (6, '6'), (12, '12'), (18, '18'), (24, '24'), (36, '36')
    ])
    frequency_unit = SelectField('Unit', choices=[('months', 'Months'), ('years', 'Years')])
    gender = SelectField('Gender', choices=[('all', 'All'), ('male', 'Male'), ('female', 'Female')])
    min_age = SelectField('Min Age', coerce=int, choices=[(i, str(i)) for i in range(0, 101)])
    max_age = SelectField('Max Age', coerce=int, choices=[(i, str(i)) for i in range(0, 101)])
    submit = SubmitField('Save Screening Type')