"""
Forms for First Login Flow
"""
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
import re


class FirstLoginPasswordForm(FlaskForm):
    """Form for changing temporary password"""
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match')
    ])
    
    def validate_new_password(self, field):
        """Validate password strength"""
        password = field.data
        
        # Check for at least one uppercase letter
        if not re.search(r'[A-Z]', password):
            raise ValidationError('Password must contain at least one uppercase letter')
        
        # Check for at least one lowercase letter
        if not re.search(r'[a-z]', password):
            raise ValidationError('Password must contain at least one lowercase letter')
        
        # Check for at least one digit
        if not re.search(r'\d', password):
            raise ValidationError('Password must contain at least one number')
        
        # Check for at least one special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError('Password must contain at least one special character')


class SecurityQuestionsForm(FlaskForm):
    """Form for setting up security questions"""
    # Question 1: What year did you graduate high school?
    security_answer_1 = StringField(
        'What year did you graduate high school?',
        validators=[
            DataRequired(message='Please answer this security question'),
            Length(min=4, max=4, message='Please enter a 4-digit year')
        ]
    )
    
    # Question 2: What is your mother's maiden name?
    security_answer_2 = StringField(
        "What is your mother's maiden name?",
        validators=[
            DataRequired(message='Please answer this security question'),
            Length(min=2, max=50, message='Please enter a valid name')
        ]
    )
    
    def validate_security_answer_1(self, field):
        """Validate year is numeric and reasonable"""
        try:
            year = int(field.data)
            if year < 1940 or year > 2030:
                raise ValidationError('Please enter a valid graduation year')
        except ValueError:
            raise ValidationError('Please enter a valid 4-digit year')
