from wtforms import Form
from flask_wtf import FlaskForm
from wtforms import StringField,IntegerField, TextAreaField, SelectMultipleField, SelectField, FieldList, DecimalField
from wtforms import EmailField
from wtforms import validators
from wtforms.validators import DataRequired

class GalletaForm(FlaskForm):
    nombre = StringField('Nombre', validators=[DataRequired()])
    receta_id = SelectField('Receta', coerce=int, choices=[], validators=[DataRequired()])
    descripcion = TextAreaField('Descripción')


class PedidoForm(FlaskForm):
    observaciones = TextAreaField('Observaciones', [
        validators.Optional(),
        validators.Length(max=500)
    ])

class RecetaForm(FlaskForm):
    nombreReceta = StringField('Nombre de la Receta', validators=[DataRequired()])
    descripcion = TextAreaField('Descripción', validators=[DataRequired()])
    cantidadGalletaProducida = IntegerField('Cantidad de Galletas Producidas', validators=[DataRequired()])
    tiempoPreparacion = IntegerField('Tiempo de Preparación (min)', validators=[DataRequired()])
    diasCaducidad = IntegerField('Días de Caducidad', validators=[DataRequired()])
    

class DeleteForm(FlaskForm):
    nombreReceta = StringField('Nombre de la Receta', validators=[DataRequired()])
    descripcion = TextAreaField('Descripción', validators=[DataRequired()])
    cantidadGalletaProducida = IntegerField('Cantidad de Galletas Producidas', validators=[DataRequired()])
    tiempoPreparacion = IntegerField('Tiempo de Preparación (min)', validators=[DataRequired()])
    diasCaducidad = IntegerField('Días de Caducidad', validators=[DataRequired()])


class IngredientesRecetasForm(FlaskForm):
    ingrediente = SelectField('Ingrediente', coerce=int, validators=[DataRequired()])
    cantidadNecesaria = DecimalField('Cantidad Necesaria (g)', validators=[DataRequired()])
    observaciones = StringField('Observaciones')  