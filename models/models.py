from flask import url_for
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Numeric, Enum
from datetime import datetime, timedelta, date
from sqlalchemy.dialects.mysql import ENUM
from sqlalchemy.orm import validates
from decimal import Decimal

db = SQLAlchemy()

class Usuarios(db.Model, UserMixin):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # Cambiado a id
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    telefono = db.Column(db.String(20))
    direccion = db.Column(db.Text)
    rol = db.Column(db.Enum('Admin', 'Ventas', 'Cocina', 'Cliente'), nullable=False)
    fechaRegistro = db.Column(db.DateTime, default=datetime.utcnow)
    two_factor_secret = db.Column(db.String(255))  # Almacena el secreto para 2FA
    two_factor_enabled = db.Column(db.Boolean, default=False)  # Si tiene 2FA activado



class Proveedor(db.Model):
    __tablename__ = 'proveedores'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre_proveedor = db.Column(db.String(255), nullable=False)
    telefono = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.Text)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

class PagoProveedor(db.Model):
    __tablename__ = 'pagos_proveedores'
    
    id = db.Column(db.Integer, primary_key=True)
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'))
    materia_prima_id = db.Column(db.Integer, db.ForeignKey('materias_primas.id'))
    cantidad_pago = db.Column(db.Numeric(10, 2), nullable=False)
    fecha_pago = db.Column(db.DateTime, default=datetime.utcnow)
    ingrediente = db.Column(db.String(100))
    cantidad_ingrediente = db.Column(db.Numeric(10, 2))
    precio_unitario = db.Column(db.Numeric(10, 2))
    unidad_medida = db.Column(db.String(20))
    pago_verificado = db.Column(db.Boolean, default=False)
    
    # Relaciones
    proveedor = db.relationship('Proveedor', backref='pagos')

    materia_prima = db.relationship('MateriaPrima', backref='pagos')
    @validates('cantidad_ingrediente', 'precio_unitario', 'cantidad_pago')
    def validate_positive_values(self, key, value):
        """Valida que los valores numéricos sean positivos"""
        if value is not None and Decimal(str(value)) <= 0:
            raise ValueError(f"{key} debe ser un valor positivo")
        return value


class MateriaPrima(db.Model):
    __tablename__ = 'materias_primas'

    id = db.Column(db.Integer, primary_key=True)
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    unidad_almacenamiento = db.Column(ENUM('gramo', 'mililitro', 'pieza', name='unidades_almacenamiento'), nullable=False)
    unidad_medida = db.Column(ENUM('kilogramo', 'kilogramos', 'litro', 'litros', 'bulto', 'bultos', 'pieza', 'piezas', name='unidades_medida'), nullable=False)
    cantidad_disponible = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    cantidad_minima = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    precio_compra = db.Column(db.Numeric(10, 2), nullable=False)
    fecha_caducidad = db.Column(db.Date)
    fecha_ultima_compra = db.Column(db.Date)
    activa = db.Column(db.Boolean, default=True) 

    proveedor = db.relationship('Proveedor', backref='materias_primas')
    
    @property
    def es_bajo_stock(self):
        """Determina si el stock está por debajo del mínimo, considerando conversión de unidades"""
        try:
            if self.unidad_medida == 'kilogramo' and self.unidad_almacenamiento == 'gramo':
                cantidad_min_convertida = self.cantidad_minima * 1000
            elif self.unidad_medida == 'litro' and self.unidad_almacenamiento == 'mililitro':
                cantidad_min_convertida = self.cantidad_minima * 1000
            else:
                cantidad_min_convertida = self.cantidad_minima
                
            return self.cantidad_disponible < Decimal(str(cantidad_min_convertida))
        except Exception as e:
            app.logger.error(f"Error calculando bajo stock: {str(e)}")
            return False
    
    @property
    def porcentaje_stock(self):
        """Devuelve el porcentaje de stock disponible respecto al mínimo"""
        try:
            if self.cantidad_minima <= 0:
                return 100
                
            if self.unidad_medida == 'kilogramo' and self.unidad_almacenamiento == 'gramo':
                cantidad_min_convertida = self.cantidad_minima * 1000
            elif self.unidad_medida == 'litro' and self.unidad_almacenamiento == 'mililitro':
                cantidad_min_convertida = self.cantidad_minima * 1000
            else:
                cantidad_min_convertida = self.cantidad_minima
                
            return (self.cantidad_disponible / Decimal(str(cantidad_min_convertida))) * 100
        except:
            return 0
            
    @property
    def esta_por_caducar(self):
        """Determina si el producto está por caducar (15 días o menos)"""
        try:
            if not self.fecha_caducidad:
                return False
                
            hoy = datetime.now().date()
            
            # Si fecha_caducidad es datetime, convertirlo a date
            if isinstance(self.fecha_caducidad, datetime):
                fecha_cad = self.fecha_caducidad.date()
            else:
                fecha_cad = self.fecha_caducidad
                
            dias_para_caducar = (fecha_cad - hoy).days
            
            # Considerar productos que ya caducaron o caducarán en 15 días
            return dias_para_caducar <= 15
        except Exception as e:
            app.logger.error(f"Error verificando caducidad: {str(e)}")
            return False

class Receta(db.Model):
    __tablename__ = 'recetas'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre_receta = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    ingrediente_especial = db.Column(db.String(50), nullable=False)
    cantidad_galletas_producidas = db.Column(db.Integer, nullable=False)
    tiempo_preparacion = db.Column(db.Integer, nullable=False)
    dias_caducidad = db.Column(db.Integer, nullable=False)
    activa = db.Column(db.Boolean, default=True)
    
    ingredientes = db.relationship('IngredienteReceta', backref='receta', cascade='all, delete-orphan')
    galletas = db.relationship('Galleta', backref='receta')

class IngredienteReceta(db.Model):
    __tablename__ = 'ingredientes_receta'
    
    id = db.Column(db.Integer, primary_key=True)
    receta_id = db.Column(db.Integer, db.ForeignKey('recetas.id'), nullable=False)
    materia_prima_id = db.Column(db.Integer, db.ForeignKey('materias_primas.id'), nullable=False)
    cantidad_necesaria = db.Column(db.Numeric(10,2), nullable=False)
    observaciones = db.Column(db.Text)
    
    materia_prima = db.relationship('MateriaPrima')


#Modificación de ModelGalletas
class Galleta(db.Model):
    __tablename__ = 'galletas'
    
    id = db.Column(db.Integer, primary_key=True)
    receta_id = db.Column(db.Integer, db.ForeignKey('recetas.id'), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    costo_galleta = db.Column(db.Numeric(10,2), nullable=False)
    precio = db.Column(db.Numeric(10,2), nullable=False)
    descripcion = db.Column(db.Text)
    url_imagen = db.Column(db.String(255))  
    activa = db.Column(db.Boolean, default=True)
    
    inventario = db.relationship('InventarioGalleta', backref='galleta')
    detalles_pedido = db.relationship('DetallePedido', backref='galleta')
    detalles_venta = db.relationship('DetalleVenta', backref='galleta')
    solicitudes = db.relationship('SolicitudProduccion', backref='galleta')
    def imagen_url(self):
        if self.url_imagen:
            return url_for('static', filename=self.url_imagen.replace('static/', ''))
        return url_for('static', filename='imagenGalletas/default.jpg')

class InventarioGalleta(db.Model):
    __tablename__ = 'inventario_galletas'
    
    id = db.Column(db.Integer, primary_key=True)
    galleta_id = db.Column(db.Integer, db.ForeignKey('galletas.id'), nullable=False)
    stock = db.Column(db.Integer, default=0, nullable=False)
    fecha_produccion = db.Column(db.Date, nullable=False)
    fecha_caducidad = db.Column(db.Date, nullable=False)
    lote = db.Column(db.String(50))
    disponible = db.Column(db.Boolean, default=True)

class Pedido(db.Model):
    __tablename__ = 'pedidos'
    
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha_pedido = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_entrega = db.Column(db.Date)
    total = db.Column(db.Numeric(10,2), nullable=False)
    estado = db.Column(db.Enum('Pendiente', 'En Proceso', 'Listo', 'Entregado', 'Cancelado', name='estados_pedido'), default='Pendiente')
    observaciones = db.Column(db.Text)
    
    cliente = db.relationship('Usuarios')
    detalles = db.relationship('DetallePedido', backref='pedido', cascade='all, delete-orphan')

class DetallePedido(db.Model):
    __tablename__ = 'detalle_pedido'
    
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    galleta_id = db.Column(db.Integer, db.ForeignKey('galletas.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Numeric(10,2), nullable=False)
    subtotal = db.Column(db.Numeric(10,2), nullable=False)

class Venta(db.Model):
    __tablename__ = 'ventas'
    
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha_venta = db.Column(db.DateTime, default=datetime.utcnow)
    total = db.Column(db.Numeric(10,2), nullable=False)
    costo_total = db.Column(db.Numeric(10,2), nullable=False)
    ganancia = db.Column(db.Numeric(10,2), nullable=False)
    monto_recibido = db.Column(db.Numeric(10,2), nullable=False)
    cambio = db.Column(db.Numeric(10,2), nullable=False)
    
    usuario = db.relationship('Usuarios')
    detalles = db.relationship('DetalleVenta', backref='venta', cascade='all, delete-orphan')

class DetalleVenta(db.Model):
    __tablename__ = 'detalle_venta'
    
    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey('ventas.id'), nullable=False)
    galleta_id = db.Column(db.Integer, db.ForeignKey('galletas.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    galletas_descontadas = db.Column(db.Integer, nullable=False) #Nuevo campo
    precio_unitario = db.Column(db.Numeric(10,2), nullable=False)
    subtotal = db.Column(db.Numeric(10,2), nullable=False)

class Produccion(db.Model):
    __tablename__ = 'produccion'
    
    id = db.Column(db.Integer, primary_key=True)
    receta_id = db.Column(db.Integer, db.ForeignKey('recetas.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    fecha_produccion = db.Column(db.DateTime, default=datetime.utcnow)
    cantidad = db.Column(db.Integer, nullable=False)
    
    receta = db.relationship('Receta')
    usuario = db.relationship('Usuarios')

class SolicitudProduccion(db.Model):
    __tablename__ = 'solicitudes_produccion'
    
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    galleta_id = db.Column(db.Integer, db.ForeignKey('galletas.id'), nullable=False)
    cantidad_solicitada = db.Column(db.Integer, nullable=False)
    fecha_solicitud = db.Column(db.DateTime, default=datetime.utcnow)
    estado = db.Column(db.Enum('Pendiente', 'Aprobada', 'Rechazada', 'Completada', name='estados_solicitud'), default='Pendiente')
    
    usuario = db.relationship('Usuarios')

class Merma(db.Model):
    __tablename__ = 'mermas'
    
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.Enum('Materia Prima', 'Galleta Terminada', name='tipos_merma'), nullable=False)
    materia_prima_id = db.Column(db.Integer, db.ForeignKey('materias_primas.id'))
    galleta_id = db.Column(db.Integer, db.ForeignKey('galletas.id'))
    cantidad = db.Column(db.Numeric(10,2), nullable=False)
    motivo = db.Column(db.Enum('Caducidad', 'Producción', 'Dañado', 'Otro', name='motivos_merma'), nullable=False)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    
    materia_prima = db.relationship('MateriaPrima')
    galleta = db.relationship('Galleta')
    usuario = db.relationship('Usuarios')

class EstadoGalleta(db.Model):
    __tablename__ = 'estado_galleta'  # Cambiado a minúsculas y doble underscore
    id = db.Column(db.Integer, primary_key=True)  # Nombre estándar
    galleta_id = db.Column(db.Integer, db.ForeignKey('galletas.id'), nullable=False)
    estatus = db.Column(db.Enum('Pendiente', 'Aprobada', 'Completada'), nullable=False)
    
    # Relación explícita
    galleta = db.relationship('Galleta', backref='estados')