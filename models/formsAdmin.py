from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, PasswordField, DateField, IntegerField
from wtforms.validators import DataRequired, Length, Email, Optional
from datetime import date

class RegistrarEmpleadosForm(FlaskForm):
    nombre = StringField('Nombre', validators=[
        DataRequired(message="El nombre es obligatorio"),
        Length(min=3, max=100, message="El nombre debe tener entre 3 y 100 caracteres")
    ])
    
    email = StringField('Email', validators=[
        DataRequired(message="El email es obligatorio"),
        Email(message="Ingrese un email válido"),
        Length(max=100, message="El email no puede exceder 100 caracteres")
    ])
    
    password = PasswordField('Contraseña', validators=[
        DataRequired(message="La contraseña es obligatoria"),
        Length(min=8, message="La contraseña debe tener al menos 8 caracteres")
    ])
    
    telefono = StringField('Teléfono', validators=[
        DataRequired(message="El teléfono es obligatorio"),
        Length(min=10, max=15, message="El teléfono debe tener entre 10 y 15 caracteres")
    ])
    
    direccion = StringField('Dirección', validators=[
        DataRequired(message="La dirección es obligatoria"),
        Length(max=200, message="La dirección no puede exceder 200 caracteres")
    ])
    
    rol = SelectField('Rol', choices=[
        ('Ventas', 'Ventas'),
        ('Cocina', 'Cocina'),
    ], validators=[DataRequired(message="Seleccione un rol")])
    
    fechaRegistro = DateField('Fecha de registro', default=date.today, validators=[Optional()])

class ModificarEmpleadosForm(FlaskForm):
    id = IntegerField('ID', validators=[DataRequired(message="El ID es obligatorio")])
    nombre = StringField('Nombre', validators=[
        DataRequired(message="El nombre es obligatorio"),
        Length(min=3, max=100, message="El nombre debe tener entre 3 y 100 caracteres")
    ])
    email = StringField('Email', validators=[
        DataRequired(message="El email es obligatorio"),
        Email(message="Ingrese un email válido"),
        Length(max=100, message="El email no puede exceder 100 caracteres")
    ])
    
    password = PasswordField('Contraseña', validators=[
        Optional(),
        Length(min=8, message="La contraseña debe tener al menos 8 caracteres")
    ])
    
    telefono = StringField('Teléfono', validators=[
        DataRequired(message="El teléfono es obligatorio"),
        Length(min=10, max=15, message="El teléfono debe tener entre 10 y 15 caracteres")
    ])
    
    direccion = StringField('Dirección', validators=[
        DataRequired(message="La dirección es obligatoria"),
        Length(max=200, message="La dirección no puede exceder 200 caracteres")
    ])
    
    rol = SelectField('Rol', choices=[
        ('Admin', 'Administrador'),
        ('Ventas', 'Ventas'),
        ('Cocina', 'Cocina'),
        ('Cliente', 'Cliente')
    ])
    
    fechaRegistro = DateField('Fecha de registro', default=date.today, validators=[Optional()])