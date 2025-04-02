from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.models import db, Usuarios, Galleta, Pedido, DetallePedido, Venta, DetalleVenta, InventarioGalleta
from datetime import datetime
from controller.auth import ventas_required
from sqlalchemy import or_
from decimal import Decimal

ventas_bp = Blueprint('ventas', __name__)

@ventas_bp.route("/menuVentas", methods=["GET", "POST"])
@ventas_required
def menuVentas():
    pedidos = Pedido.query.filter(Pedido.estado != 'Cancelado')\
                         .order_by(Pedido.fecha_pedido.desc())\
                         .all()
    return render_template("ventas/menuVentas.html", pedidos=pedidos)

@ventas_bp.route("/cambiar_estado/<int:pedido_id>", methods=["POST"])
@ventas_required
def cambiar_estado(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    nuevo_estado = request.form.get('nuevo_estado')
    
    if not nuevo_estado:
        flash('No se especificó un estado nuevo', 'error')
        return redirect(url_for('ventas.menuVentas'))
    
    try:
        estado_anterior = pedido.estado
        pedido.estado = nuevo_estado
        
        if nuevo_estado == 'Entregado' and estado_anterior != 'Entregado':
            # Si es entrega, redirigir a página de pago
            return redirect(url_for('ventas.procesar_pago', pedido_id=pedido.id))
            
        db.session.commit()
        flash(f'Estado del pedido #{pedido_id} cambiado a {nuevo_estado}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al cambiar estado: {str(e)}', 'error')
    
    return redirect(url_for('ventas.menuVentas'))

@ventas_bp.route("/procesar_pago/<int:pedido_id>", methods=["GET", "POST"])
@ventas_required
def procesar_pago(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    
    if request.method == 'POST':
        try:
            monto_recibido = Decimal(request.form.get('monto_recibido'))
            
            if monto_recibido < pedido.total:
                flash('El monto recibido no puede ser menor al total del pedido', 'error')
                return redirect(url_for('ventas.procesar_pago', pedido_id=pedido_id))
            
            # Calcular cambio
            cambio = monto_recibido - pedido.total
            
            # Verificar inventario antes de procesar
            for detalle in pedido.detalles:
                inventario = InventarioGalleta.query.filter_by(
                    galleta_id=detalle.galleta_id,
                    disponible=True
                ).order_by(InventarioGalleta.fecha_caducidad).first()
                
                if not inventario or inventario.stock < detalle.cantidad:
                    raise ValueError(f'No hay suficiente inventario para {detalle.galleta.nombre}')
            
            # Crear registro de venta
            nueva_venta = Venta(
                usuario_id=session['user_id'],
                fecha_venta=datetime.now(),
                total=float(pedido.total),
                monto_recibido=float(monto_recibido),
                cambio=float(cambio)
            )
            db.session.add(nueva_venta)
            db.session.flush()
            
            # Procesar cada detalle
            for detalle in pedido.detalles:
                # Actualizar inventario
                inventario = InventarioGalleta.query.filter_by(
                    galleta_id=detalle.galleta_id,
                    disponible=True
                ).order_by(InventarioGalleta.fecha_caducidad).first()
                
                inventario.stock -= detalle.cantidad
                if inventario.stock <= 0:
                    inventario.disponible = False
                
                # Crear detalle de venta
                detalle_venta = DetalleVenta(
                    venta_id=nueva_venta.id,
                    galleta_id=detalle.galleta_id,
                    cantidad=detalle.cantidad,
                    precio_unitario=detalle.precio_unitario,
                    subtotal=detalle.subtotal
                )
                db.session.add(detalle_venta)
            
            # Marcar pedido como entregado
            pedido.estado = 'Entregado'
            db.session.commit()
            
            flash(f'Venta registrada correctamente. Cambio: ${cambio:.2f}', 'success')
            return redirect(url_for('ventas.menuVentas'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al procesar pago: {str(e)}', 'error')
    
    return render_template("ventas/procesar_pago.html", pedido=pedido)

@ventas_bp.route("/detalle_pedido/<int:pedido_id>")
@ventas_required
def detalle_pedido(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    return render_template("ventas/detalle_pedido.html", pedido=pedido)