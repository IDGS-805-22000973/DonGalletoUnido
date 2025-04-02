from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.models import db, Usuarios, Galleta, Pedido, DetallePedido, InventarioGalleta
from datetime import datetime, timedelta
from decimal import Decimal
from controller.auth import cliente_required

cliente_bp = Blueprint('cliente', __name__)
# Factor de conversión para presentaciones (unidades por presentación)
PRESENTACIONES = {
    'pieza': {'nombre': 'Por pieza', 'factor': 1, 'unidad': 'unidad'},
    'gramos': {'nombre': 'Por gramos', 'factor': 0.01, 'unidad': '100g'},  # Asumiendo 100g por galleta
    '700g': {'nombre': 'Paquete 700g', 'factor': 7, 'unidad': 'paquete'},
    '1kg': {'nombre': 'Paquete 1kg', 'factor': 10, 'unidad': 'paquete'}
}

@cliente_bp.route("/menuCliente", methods=["GET", "POST"])
@cliente_required
def menuCliente():
    # Configurar fechas
    hoy = datetime.now().date()
    min_date = hoy + timedelta(days=2)
    max_date = hoy + timedelta(days=30)
    
    galletas_activas = Galleta.query.filter_by(activa=True).all()
    
    if request.method == 'POST':
        try:
            # Validar fecha
            fecha_entrega = datetime.strptime(request.form.get('fecha_entrega'), '%Y-%m-%d').date()
            if fecha_entrega < min_date or fecha_entrega > max_date:
                flash('Fecha de entrega inválida', 'error')
                return redirect(url_for('cliente.menuCliente'))
            
            # Crear pedido
            nuevo_pedido = Pedido(
                cliente_id=session['user_id'],
                fecha_pedido=datetime.now(),
                fecha_entrega=fecha_entrega,
                total=0,
                estado='Pendiente',
                observaciones=request.form.get('observaciones', '')
            )
            db.session.add(nuevo_pedido)
            db.session.flush()
            
            total = Decimal('0')
            items_pedido = 0
            
            for galleta in galletas_activas:
                galleta_id = str(galleta.id)
                presentacion = request.form.get(f"presentacion_{galleta_id}")
                cantidad = Decimal(request.form.get(f"cantidad_{galleta_id}", '0'))
                
                if cantidad > Decimal('0'):
                    # Calcular unidades equivalentes
                    factor = Decimal(str(PRESENTACIONES[presentacion]['factor']))
                    unidades = cantidad * factor
                    
                    # Calcular precio
                    precio_galleta = Decimal(str(galleta.precio))
                    subtotal = precio_galleta * unidades
                    
                    # Crear detalle (sin verificar inventario aún)
                    detalle = DetallePedido(
                        pedido_id=nuevo_pedido.id,
                        galleta_id=galleta_id,
                        cantidad=float(unidades),
                        precio_unitario=float(precio_galleta),
                        subtotal=float(subtotal),
                    )
                    db.session.add(detalle)
                    
                    total += subtotal
                    items_pedido += 1
            
            if items_pedido == 0:
                db.session.rollback()
                flash('Seleccione al menos un producto', 'error')
                return redirect(url_for('cliente.menuCliente'))
            
            nuevo_pedido.total = float(total)
            db.session.commit()
            flash('Pedido realizado con éxito! Será confirmado cuando verifiquemos disponibilidad.', 'success')
            return redirect(url_for('cliente.misPedidos'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
    
    return render_template("cliente/menuCliente.html",
                         galletas=galletas_activas,
                         presentaciones=PRESENTACIONES,
                         min_date=min_date.strftime('%Y-%m-%d'),
                         max_date=max_date.strftime('%Y-%m-%d'))

@cliente_bp.route("/misPedidos")
@cliente_required
def misPedidos():
    # Obtener pedidos ordenados por fecha descendente
    pedidos = Pedido.query.filter_by(cliente_id=session['user_id'])\
                         .order_by(Pedido.fecha_pedido.desc())\
                         .all()
    return render_template("cliente/misPedidos.html", pedidos=pedidos)