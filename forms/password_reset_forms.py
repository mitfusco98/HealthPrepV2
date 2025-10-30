"""
Forms for Password Reset Flow
"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
import re


class ForgotPasswordForm(FlaskForm):
    """Form for initiating password reset"""
    email = StringField('Email Address', validators=[
        DataRequired(message='Email is required'),
        Email(message='Please enter a valid email address')
    ])


class SecurityAnswerForm(FlaskForm):
    """Form for answering security questions"""
    answer_1 = StringField(
        'What year did you graduate high school?',
        validators=[
            DataRequired(message='Please answer this question'),
            Length(min=4, max=4, message='Please enter a 4-digit year')
        ]
    )
    
    answer_2 = StringField(
        "What is your mother's maiden name?",
        validators=[
            DataRequired(message='Please answer this question'),
            Length(min=2, max=50, message='Please enter a valid name')
        ]
    )


class ResetPasswordForm(FlaskForm):
    """Form for setting new password after reset"""
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
