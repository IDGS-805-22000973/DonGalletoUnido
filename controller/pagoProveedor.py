from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
from models.models import db, PagoProveedor, Proveedor, MateriaPrima
from models import forms
from decimal import Decimal
from sqlalchemy.orm import joinedload

pago_proveedor_bp = Blueprint('pagoProveedor', __name__)

def verificar_pago(pago_id):
    """Función mejorada para verificar si el pago coincide con el costo del insumo"""
    pago = PagoProveedor.query.get(pago_id)
    if not pago:
        return False
    
    # Verificación basada en la materia prima relacionada
    if pago.materia_prima:
        costo_esperado = pago.materia_prima.precio_compra * pago.cantidad_ingrediente
        return pago.cantidad_pago >= costo_esperado
    
    # Si no hay materia prima relacionada, verificar por nombre
    materia_prima = MateriaPrima.query.filter_by(nombre=pago.ingrediente).first()
    if materia_prima:
        costo_esperado = materia_prima.precio_compra * pago.cantidad_ingrediente
        return pago.cantidad_pago >= costo_esperado
    
    return False

@pago_proveedor_bp.route('/pagos', methods=['GET', 'POST'])
def pagos():
    form = forms.PagoProveedorForm(request.form)
    pagos = PagoProveedor.query.options(
        joinedload(PagoProveedor.proveedor),
        joinedload(PagoProveedor.materia_prima)
    ).order_by(PagoProveedor.fecha_pago.desc()).all()
    
    # Cargar opciones de proveedores
    form.proveedor_id.choices = [(p.id, p.nombre_proveedor) for p in Proveedor.query.all()]
    
   # Cálculo de estadísticas 
    total_pagado = sum(p.cantidad_pago for p in pagos if p.pago_verificado)  # Solo pagos verificados
    pagos_verificados = sum(1 for p in pagos if p.pago_verificado)
    pagos_pendientes = sum(1 for p in pagos if not p.pago_verificado)

    if request.method == 'POST' and form.validate():
        try:
            # Calcular precio unitario
            precio_unitario = Decimal(form.cantidad_pago.data) / Decimal(form.cantidad_ingrediente.data)
            
            nuevo_pago = PagoProveedor(
                proveedor_id=form.proveedor_id.data,
                cantidad_pago=Decimal(form.cantidad_pago.data),
                ingrediente=form.ingrediente.data,
                cantidad_ingrediente=Decimal(form.cantidad_ingrediente.data),
                fecha_pago=datetime.now(),
                pago_verificado=False,
                precio_unitario=precio_unitario,
                unidad_medida=form.unidad_medida.data
            )
            
            db.session.add(nuevo_pago)
            db.session.commit()
            
            # Verificación automática
            if verificar_pago(nuevo_pago.id):
                nuevo_pago.pago_verificado = True
                db.session.commit()
                flash("Pago registrado y verificado correctamente", "success")
            else:
                flash("Pago registrado, pero no coincide con el costo esperado", "warning")
                
            return redirect(url_for('pagoProveedor.pagos'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error al registrar el pago: {str(e)}", "danger")

    return render_template("cocina/pagos.html", 
                         form=form, 
                         pagos=pagos, 
                         total_pagado=total_pagado,
                         pagos_verificados=pagos_verificados,
                         pagos_pendientes=pagos_pendientes,
                         format_price=lambda x: f"${float(x):,.2f}" if x is not None else '$0.00')

@pago_proveedor_bp.route('/pagos/verificar/<int:id>')
def verificar_pago_endpoint(id):
    try:
        if verificar_pago(id):
            pago = PagoProveedor.query.get(id)
            pago.pago_verificado = True
            db.session.commit()
            flash("Pago verificado correctamente", "success")
        else:
            flash("El pago no coincide con el costo esperado", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al verificar el pago: {str(e)}", "danger")
        
    return redirect(url_for('pagoProveedor.pagos'))

@pago_proveedor_bp.route('/pagos/eliminar/<int:id>')
def eliminar_pago(id):
    try:
        pago = PagoProveedor.query.get(id)
        if pago:
            db.session.delete(pago)
            db.session.commit()
            flash("Pago eliminado correctamente", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al eliminar el pago: {str(e)}", "danger")
        
    return redirect(url_for('pagoProveedor.pagos'))