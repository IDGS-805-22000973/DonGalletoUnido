from datetime import datetime, timedelta
from flask import Blueprint, flash, redirect, render_template, request, jsonify, make_response, url_for
from models.models import db, Usuarios, Galleta, Pedido, DetallePedido, Venta, DetalleVenta, Proveedor, PagoProveedor, MateriaPrima, Receta, IngredienteReceta, InventarioGalleta, EstadoGalleta
from flask_wtf.csrf import generate_csrf
from werkzeug.exceptions import BadRequest

chefCocinero = Blueprint('chefCocinero', __name__)

@chefCocinero.route('/produccion')
def produccion():
    try:
        galletas = (
            db.session.query(
                Galleta,
                EstadoGalleta.estatus,
                db.func.coalesce(db.func.sum(InventarioGalleta.stock), 0).label('total_stock')
            )
            .outerjoin(EstadoGalleta, Galleta.id == EstadoGalleta.galleta_id)
            .outerjoin(InventarioGalleta, Galleta.id == InventarioGalleta.galleta_id)
            .group_by(Galleta.id, EstadoGalleta.estatus)
            .having(db.func.coalesce(db.func.sum(InventarioGalleta.stock), 0) < 50)
            .all()
        )
        
        # Procesar resultados
        resultados = [(g, e if e else 'Pendiente', s) for g, e, s in galletas]
        
        csrf_token = generate_csrf()
        return render_template('cocina/produccion.html', 
                            galletas=resultados, 
                            csrf_token=csrf_token)
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return render_template('cocina/produccion.html', galletas=[])
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return render_template('cocina/produccion.html', galletas=[])

@chefCocinero.route('/actualizar_estado', methods=['POST'])
def actualizar_estado():
    try:
        data = request.get_json()
        id_galleta = int(data['idGalleta'])
        nuevo_estado = data['nuevo_estado']
        
        # Buscar o crear estado
        estado_galleta = EstadoGalleta.query.filter_by(galleta_id=id_galleta).first()
        if not estado_galleta:
            estado_galleta = EstadoGalleta(galleta_id=id_galleta, estatus=nuevo_estado)
            db.session.add(estado_galleta)
        else:
            estado_galleta.estatus = nuevo_estado
        
        # Si es Aprobada, verificar ingredientes
        if nuevo_estado == "Aprobada":
            galleta = Galleta.query.get(id_galleta)
            if not galleta:
                return jsonify({"error": f"Galleta con ID {id_galleta} no encontrada"}), 400
            
            # Verificar ingredientes
            for ingrediente in IngredienteReceta.query.filter_by(receta_id=galleta.receta_id):
                materia_prima = MateriaPrima.query.get(ingrediente.materia_prima_id)
                if materia_prima.cantidad_disponible < ingrediente.cantidad_necesaria:
                    return jsonify({
                        "error": "Ingredientes insuficientes",
                        "detalle": f"Falta {materia_prima.nombre} (necesario: {ingrediente.cantidad_necesaria}, disponible: {materia_prima.cantidad_disponible})"
                    }), 400
            
            # Descontar ingredientes
            for ingrediente in IngredienteReceta.query.filter_by(receta_id=galleta.receta_id):
                materia_prima = MateriaPrima.query.get(ingrediente.materia_prima_id)
                materia_prima.cantidad_disponible -= ingrediente.cantidad_necesaria
        
        db.session.commit()
        return jsonify({
            "message": "Estado actualizado",
            "nuevo_estado": nuevo_estado,
            "csrf_token": generate_csrf()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error actualizando estado: {str(e)}")
        return jsonify({"error": "Error interno", "detalle": str(e)}), 500

@chefCocinero.route('/guardar_cantidad', methods=['POST'])
def guardar_cantidad():
    try:
        data = request.get_json()
        id_galleta = int(data['idGalleta'])
        cantidad = int(data['cantidad'])
        
        galleta = Galleta.query.get(id_galleta)
        if not galleta:
            return jsonify({"error": "Galleta no encontrada"}), 404
        
        # Buscar o crear inventario
        inventario = InventarioGalleta.query.filter_by(
            galleta_id=id_galleta, 
            disponible=True
        ).first()
        
        if not inventario:
            inventario = InventarioGalleta(
                galleta_id=id_galleta,
                stock=cantidad,
                fecha_produccion=datetime.today(),
                fecha_caducidad=datetime.today() + timedelta(days=galleta.receta.dias_caducidad),
                lote=f"LOTE-{id_galleta}-{datetime.now().strftime('%Y%m%d')}",
                disponible=True
            )
            db.session.add(inventario)
        else:
            inventario.stock += cantidad
        
        # Resetear estado a Pendiente
        estado = EstadoGalleta.query.filter_by(galleta_id=id_galleta).first()
        if estado:
            estado.estatus = "Pendiente"
        
        db.session.commit()
        return jsonify({
            "message": f"Producción de {cantidad} unidades guardada",
            "csrf_token": generate_csrf()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error guardando cantidad: {str(e)}")
        return jsonify({"error": "Error interno", "detalle": str(e)}), 500
    
@chefCocinero.route('/inventario')
def inventario():
    inventario_data = (
        db.session.query(Galleta.nombre, InventarioGalleta.stock, Galleta.descripcion)
        .join(InventarioGalleta, Galleta.id == InventarioGalleta.galleta_id)
        .all()
    )
    return render_template('cocina/inventario.html', inventario_data=inventario_data)