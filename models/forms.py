from wtforms import Form
from flask_wtf import FlaskForm
from wtforms import StringField,IntegerField, TextAreaField, HiddenField, DecimalField, SelectField,DateField,SubmitField, BooleanField,FloatField
from wtforms import EmailField
from wtforms import validators
from wtforms.validators import DataRequired, NumberRange, Length, Email
from models.models import Proveedor



# Formulario para Cocinero
class GalletaForm(FlaskForm):
    nombre = StringField('Nombre', validators=[DataRequired()])
    precio_por_pieza = IntegerField('Precio por pieza', validators=[DataRequired()])
    precio_por_gramo = IntegerField('Precio por gramo', validators=[DataRequired()])
    cantidadGalletas = IntegerField('Cantidad de galletas', validators=[DataRequired()])

# Formulario para Cocinero
class PedidoForm(FlaskForm):
    observaciones = TextAreaField('Observaciones', [
        validators.Optional(),
        validators.Length(max=500)
    ])


class ActualizarInventarioForm(FlaskForm):
    id = IntegerField('ID Materia Prima')
    proveedor_id = SelectField('Proveedor', coerce=int)
    nombre = StringField('Nombre')
    descripcion = StringField('Descripción')
    unidad_medida = SelectField(
        'Unidad de Medida', coerce=str,
        choices=[
            ('kilogramo', 'Kilogramos'),
            ('gramo', 'Gramos'),
            ('litro', 'Litros'),
            ('mililitro', 'Mililitros'),
            ('pieza', 'Piezas'),
            ('bulto', 'Bultos')
        ],
        validators=[validators.DataRequired()]
    )
    
    cantidad_disponible = DecimalField('Cantidad Disponible', render_kw={'readonly': True})
    cantidad_minima = IntegerField('Cantidad Mínima')
    precio_compra = DecimalField('Precio de Compra')
    fecha_ultima_compra = DateField('Fecha de Última Compra')

    # Nuevo campo para agregar cantidad
    cantidadAgregar = IntegerField('Cantidad a Agregar', validators=[validators.Optional()])

# Formulario de Proveedores
class ProveedorForm(FlaskForm):
    id = HiddenField()  # Para editar proveedores existentes
    nombre_proveedor = StringField('Nombre', validators=[DataRequired(), Length(max=100)])
    telefono = StringField('Teléfono', validators=[DataRequired(), Length(max=15)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    direccion = StringField('Dirección')

# Formulario para mostrar mermas
class mostrarMermasForm(FlaskForm):
    id = IntegerField('ID Materia Prima')
    tipo = SelectField('Tipo', coerce=str,
        choices=[
            ('Materia Prima', 'Materia Prima'),
            ('Galleta Terminada', 'Galleta Terminada')
        ],
        validators=[validators.DataRequired()]
    )
    galleta_id = IntegerField('ID Galleta')
    cantidad = IntegerField('Cantidad')
    motivo = SelectField('Motivo', coerce=str,
        choices=[
            ('Caducidad', 'Caducidad'),
            ('Producción', 'Producción'),
            ('Dañado', 'Dañado'),
            ('Otro', 'Otro')
        ],
        validators=[validators.DataRequired()]
    )
    fecha_registro = DateField('Fecha de Registro')


# Formulario para agregar nueva receta
class RecetaForm(FlaskForm):
    nombreReceta = StringField('Nombre de la Receta', validators=[DataRequired()])
    descripcion = TextAreaField('Descripción', validators=[DataRequired()])
    cantidadGalletaProducida = IntegerField('Cantidad de Galletas Producidas', validators=[DataRequired()])
    diasCaducidad = IntegerField('Días de Caducidad', validators=[DataRequired()])
    ingredienteEspecial = StringField('Ingrediente Especial', validators=[DataRequired()])

class IngredientesRecetasForm(FlaskForm):
    ingrediente = SelectField('Ingrediente', coerce=int, validators=[DataRequired()])
    cantidadNecesaria = DecimalField('Cantidad Necesaria (g)', validators=[DataRequired()])
    observaciones = StringField('Observaciones')




class ProveedorForm(FlaskForm):
    id = HiddenField()  # Para editar proveedores existentes
    nombre_proveedor = StringField('Nombre', validators=[DataRequired(), Length(max=255)])
    telefono = StringField('Teléfono', validators=[DataRequired(), Length(max=20)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=100)])
    direccion = StringField('Dirección', validators=[Length(max=255)])

class PagoProveedorForm(FlaskForm):
    proveedor_id = SelectField('Proveedor', coerce=int, validators=[DataRequired()])
    cantidad_pago = DecimalField('Monto del Pago', validators=[DataRequired(), NumberRange(min=0.01)])
    ingrediente = StringField('Ingrediente', validators=[DataRequired()])
    cantidad_ingrediente = DecimalField('Cantidad', validators=[DataRequired(), NumberRange(min=0.01)])
    unidad_medida = SelectField('Unidad de Medida', choices=[
        ('kilogramos', 'Kilogramos'),
        ('litros', 'Litros'), 
        ('bultos', 'Bultos'),
        ('piezas', 'Piezas')
    ], validators=[DataRequired()])
    precio_unitario = DecimalField('Precio Unitario', validators=[DataRequired(), NumberRange(min=0.01)])
    pago_verificado = BooleanField('Pago Verificado')
    submit = SubmitField('Registrar Pago')
    
    def __init__(self, *args, **kwargs):
        super(PagoProveedorForm, self).__init__(*args, **kwargs)
        self.proveedor_id.choices = [(p.id, p.nombre_proveedor) for p in Proveedor.query.all()]



class ModificarMateriaForm(FlaskForm):
    nombre = StringField("Nombre", render_kw={'readonly': True})
    unidad_medida = StringField("Unidad de Medida", render_kw={'readonly': True})
    cantidad_actual = StringField("Cantidad Actual", render_kw={'readonly': True})
    cantidadAgregar = DecimalField(
        "Cantidad a Agregar",
        validators=[
            DataRequired(message="La cantidad es requerida"),
            NumberRange(min=0.01, message="La cantidad debe ser mayor a cero")
        ],
        places=2
    )
    
    precio_unitario = DecimalField(
        "Precio Unitario",
        validators=[
            DataRequired(message="El precio es requerido"),
            NumberRange(min=0.01, message="El precio debe ser mayor a cero")
        ],
        places=2
    )


class MateriaPrimaForm(FlaskForm):
    proveedor_id = SelectField('Proveedor', coerce=int, validators=[DataRequired()])
    nombre = StringField('Nombre', validators=[DataRequired()])
    descripcion = TextAreaField('Descripción')
    unidad_medida = SelectField('Unidad de Medida', choices=[
        ('kilogramo', 'Kilogramo'),
        ('litro', 'Litro'),
        ('bulto', 'Bulto'),
        ('pieza', 'Pieza')
    ], validators=[DataRequired()])
    cantidad_disponible = FloatField('Cantidad Disponible', validators=[DataRequired()])
    precio_compra = FloatField('Precio de Compra', validators=[DataRequired()])
    fecha_caducidad = DateField('Fecha de Caducidad')
    submit = SubmitField('Guardar')    




