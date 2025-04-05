from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, NumberRange

class RecetaForm(FlaskForm):
    nombre_receta = StringField('Nombre de la Receta', validators=[DataRequired()])
    descripcion = TextAreaField('Descripción')
    ingrediente_especial = StringField('Ingrediente Especial', validators=[DataRequired()])
    cantidad_galletas = IntegerField('Cantidad de Galletas', validators=[DataRequired(), NumberRange(min=1)])
    tiempo_preparacion = IntegerField('Tiempo de Preparación (min)', validators=[DataRequired(), NumberRange(min=1)])
    dias_caducidad = IntegerField('Días de Caducidad', validators=[DataRequired(), NumberRange(min=1)])