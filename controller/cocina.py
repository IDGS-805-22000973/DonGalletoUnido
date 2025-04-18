from datetime import datetime, timedelta
from decimal import Decimal
from flask import Blueprint, flash, redirect, render_template, request, jsonify, make_response, session, url_for
from wtforms import DateField
from models.models import Merma, db, Usuarios, Galleta, Pedido, DetallePedido, Venta, DetalleVenta, Proveedor, PagoProveedor, MateriaPrima, Receta, IngredienteReceta, InventarioGalleta, EstadoGalleta
from flask_wtf.csrf import generate_csrf
from werkzeug.exceptions import BadRequest
from controller.auth import cocina_required
from models.forms import GalletaForm, PedidoForm, MateriasPrimasForm, ActualizarInventarioForm, RecetaForm, IngredientesRecetasForm
#otros
from sqlalchemy.orm import joinedload
from flask import jsonify, request, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from flask_wtf.csrf import generate_csrf

chefCocinero = Blueprint('chefCocinero', __name__)

@chefCocinero.route('/produccion')
@cocina_required
def produccion():
    try:
        # Obtener galletas con stock bajo (<50) y recetas activas
        galletas = (
            db.session.query(
                Galleta,
                EstadoGalleta.estatus,
                db.func.coalesce(db.func.sum(InventarioGalleta.stock), 0).label('total_stock')
            )
            .join(Receta, Galleta.receta_id == Receta.id)
            .outerjoin(EstadoGalleta, Galleta.id == EstadoGalleta.galleta_id)
            .outerjoin(InventarioGalleta, Galleta.id == InventarioGalleta.galleta_id)
            .filter(Receta.activa == True)  # Solo recetas activas
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



@chefCocinero.route('/actualizar_estado', methods=['POST'])
@cocina_required
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
        return jsonify({"error": "Error interno (guardar_estado)", "detalle": str(e)}), 500
    
        
    
@chefCocinero.route('/guardar_cantidad', methods=['POST'])
@cocina_required
def guardar_cantidad():
    try:
        if current_user.is_anonymous:
            return jsonify({
                "error": "No autenticado",
                "redirect": url_for('auth.login')
            }), 401

        data = request.get_json()
        if not data or 'idGalleta' not in data:
            return jsonify({"error": "Datos incompletos"}), 400

        try:
            id_galleta = int(data['idGalleta'])
            hubo_merma = bool(data.get('huboMerma', False))
            cantidad_merma = float(data.get('cantidadMerma', 0))
            motivo_merma = data.get('motivoMerma', '')
        except (ValueError, TypeError) as e:
            return jsonify({"error": "Datos inválidos", "detalle": str(e)}), 400

        # Cargar galleta con relaciones
        galleta = Galleta.query.options(joinedload(Galleta.receta)).get(id_galleta)
        if not galleta or not galleta.receta:
            return jsonify({"error": "Galleta o receta no encontrada"}), 404

        cantidad_producida = galleta.receta.cantidad_galletas_producidas
        
        # Validaciones de merma
        motivos_permitidos = ['Caducidad', 'Producción', 'Dañado', 'Otro']
        if hubo_merma:
            if not motivo_merma or motivo_merma not in motivos_permitidos:
                return jsonify({
                    "error": "Motivo inválido",
                    "detalle": f"Motivos permitidos: {', '.join(motivos_permitidos)}"
                }), 400
            if cantidad_merma <= 0:
                return jsonify({"error": "Cantidad de merma debe ser positiva"}), 400
            if cantidad_merma > cantidad_producida:
                return jsonify({
                    "error": "Cantidad excede producción",
                    "detalle": f"Merma: {cantidad_merma}, Producción: {cantidad_producida}"
                }), 400

        # Operaciones con la base de datos
        inventario = InventarioGalleta.query.filter_by(galleta_id=id_galleta, disponible=True).first()
        
        if not inventario:
            inventario = InventarioGalleta(
                galleta_id=id_galleta,
                stock=cantidad_producida,
                fecha_produccion=datetime.now(),
                fecha_caducidad=datetime.now() + timedelta(days=galleta.receta.dias_caducidad),
                lote=f"LOTE-{id_galleta}-{datetime.now().strftime('%Y%m%d')}",
                disponible=True
            )
            db.session.add(inventario)
        else:
            inventario.stock += cantidad_producida
        
        if hubo_merma and cantidad_merma > 0:
            inventario.stock -= cantidad_merma
            db.session.add(Merma(
                tipo='Galleta Terminada',
                galleta_id=id_galleta,
                cantidad=cantidad_merma,
                motivo=motivo_merma,
                usuario_id=current_user.id
            ))

        # Actualizar estado
        estado = EstadoGalleta.query.filter_by(galleta_id=id_galleta).first()
        if estado:
            estado.estatus = "Pendiente"
        
        db.session.commit()
        return jsonify({
            "message": f"Producción de {cantidad_producida} unidades registrada",
            "merma": cantidad_merma if hubo_merma else None,
            "csrf_token": generate_csrf()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error en guardar_cantidad: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Error interno del servidor",
            "detalle": str(e)
        }), 500

    
@chefCocinero.route('/inventario')
@cocina_required
def inventario():
    inventario_data = (
        db.session.query(Galleta.nombre, InventarioGalleta.stock, Galleta.descripcion)
        .join(InventarioGalleta, Galleta.id == InventarioGalleta.galleta_id)
        .all()
    )
    return render_template('cocina/inventario.html', inventario_data=inventario_data)




@chefCocinero.route("/insumos", methods=['GET', 'POST'])
@cocina_required
def insumos():
    create_form = MateriasPrimasForm()
    proveedores = Proveedor.query.all()
    create_form.proveedor_id.choices = [(p.id, p.nombre_proveedor) for p in proveedores]

    if request.method == 'POST' and create_form.validate_on_submit():
        try:
            nueva_materia = MateriaPrima(
            proveedor_id=create_form.proveedor_id.data,
            nombre=create_form.nombre.data,
            descripcion=create_form.descripcion.data,
            unidad_medida=create_form.unidad_medida.data,
            cantidad_disponible=Decimal(create_form.cantidad_disponible.data),
            cantidad_minima=Decimal(create_form.cantidad_minima.data),
            precio_compra=Decimal(create_form.precio_compra.data),
            fecha_ultima_compra=datetime.now().date(),  
            fecha_caducidad=create_form.fecha_caducidad.data  
        )

            db.session.add(nueva_materia)
            db.session.commit()
            flash("Materia prima agregada correctamente", "success")
            return redirect(url_for('chefCocinero.insumos'))

        except Exception as e:
            db.session.rollback()
            flash(f"Error al agregar materia prima: {str(e)}", "danger")

    materias_primas = MateriaPrima.query.all()

    return render_template("cocina/insumos.html", form=create_form, materias_primas=materias_primas, proveedores=proveedores)



@chefCocinero.route("/modificar_materia/<int:id>", methods=['GET', 'POST'])
@cocina_required
def modificar_materia(id):

    materia = MateriaPrima.query.get_or_404(id)
    form = ActualizarInventarioForm(obj=materia)
    # Poblar el select de proveedores
    proveedores = Proveedor.query.all()
    form.proveedor_id.choices = [(p.id, p.nombre_proveedor) for p in proveedores]
    if form.validate_on_submit():
        try:
            cantidad_a_agregar = form.cantidadAgregar.data or 0  # Si no hay dato, usar 0
            if cantidad_a_agregar < 0:
                flash("La cantidad a agregar no puede ser negativa.", "danger")
            else:
                materia.cantidad_disponible += cantidad_a_agregar
                db.session.commit()
                flash("Cantidad actualizada correctamente.", "success")
                return redirect(url_for('chefCocinero.insumos'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error al actualizar la cantidad: {str(e)}", "danger")
    return render_template("cocina/modificarInsumos.html", form=form, materia=materia)





# Funciones de recetas

@chefCocinero.route('/crear_receta', methods=['GET', 'POST'])
@cocina_required
def crear_receta():
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            data = request.form
            nombre_receta = data.get('nombre_receta')
            descripcion = data.get('descripcion')
            tiempo_preparacion = int(data.get('tiempo_preparacion'))
            dias_caducidad = int(data.get('dias_caducidad'))
            porcentaje_ganancia = Decimal(data.get('porcentaje_ganancia'))
            peso_galleta = Decimal(data.get('peso_galleta', 100))  # Default 100g
            
            # Validaciones básicas
            if peso_galleta <= 0:
                flash('El peso por galleta debe ser mayor a cero', 'danger')
                return redirect(url_for('chefCocinero.crear_receta'))

            ingredientes = request.form.getlist('ingredientes[]')
            cantidades = request.form.getlist('cantidades[]')
            unidades = request.form.getlist('unidades[]')
            
            if not ingredientes:
                flash('Debe agregar al menos un ingrediente', 'danger')
                return redirect(url_for('chefCocinero.crear_receta'))

            # Crear nueva receta
            nueva_receta = Receta(
                nombre_receta=nombre_receta,
                descripcion=descripcion,
                ingrediente_especial='',
                cantidad_galletas_producidas=0,
                tiempo_preparacion=tiempo_preparacion,
                dias_caducidad=dias_caducidad,
                activa=True
            )
            db.session.add(nueva_receta)
            db.session.flush()
            
            costo_total_receta = Decimal('0')
            peso_total = Decimal('0')
            
            # Procesar cada ingrediente
            for i, ingrediente_id in enumerate(ingredientes):
                materia_prima = MateriaPrima.query.get_or_404(ingrediente_id)
                cantidad = Decimal(cantidades[i])
                unidad = unidades[i]
                
                # Convertir a gramos o mililitros
                cantidad_base = convertir_a_unidad_base(cantidad, unidad, materia_prima.unidad_medida)
                
                if cantidad_base <= 0:
                    flash(f'Cantidad inválida para {materia_prima.nombre}', 'danger')
                    return redirect(url_for('chefCocinero.crear_receta'))
                
                # Calcular costo (precio_compra ya está en gramos/ml)
                costo_ingrediente = cantidad_base * materia_prima.precio_compra
                costo_total_receta += costo_ingrediente
                peso_total += cantidad_base
                
                # Registrar ingrediente
                db.session.add(IngredienteReceta(
                    receta_id=nueva_receta.id,
                    materia_prima_id=materia_prima.id,
                    cantidad_necesaria=cantidad_base,
                    observaciones=f"{cantidades[i]} {unidad}"
                ))
            
            # Validar y calcular cantidad de galletas
            if peso_total <= 0:
                flash('El peso total debe ser mayor a cero', 'danger')
                return redirect(url_for('chefCocinero.crear_receta'))

            cantidad_galletas = int((peso_total / peso_galleta).to_integral_value())
            if cantidad_galletas <= 0:
                flash('La receta no produce galletas válidas', 'danger')
                return redirect(url_for('chefCocinero.crear_receta'))

            nueva_receta.cantidad_galletas_producidas = cantidad_galletas
            
            # Cálculos financieros
            costo_por_galleta = costo_total_receta / Decimal(cantidad_galletas)
            precio_venta = costo_por_galleta * (1 + (porcentaje_ganancia / Decimal('100')))
            
            # Crear galleta asociada
            db.session.add(Galleta(
                receta_id=nueva_receta.id,
                nombre=nombre_receta,
                costo_galleta=round(costo_por_galleta, 2),
                precio=round(precio_venta, 2),
                descripcion=descripcion,
                activa=True
            ))
            
            db.session.commit()
            
            flash(
                f'Receta creada: {cantidad_galletas} galletas de {peso_galleta}g\n'
                f'Costo: ${round(costo_por_galleta, 2)} c/u | '
                f'Precio: ${round(precio_venta, 2)} | '
                f'Ganancia: {round(((precio_venta - costo_por_galleta) / costo_por_galleta * 100), 1)}%',
                'success'
            )
            return redirect(url_for('chefCocinero.listar_recetas'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear receta: {str(e)}', 'danger')
            app.logger.error(f'Error en crear_receta: {str(e)}', exc_info=True)
    
    # GET: Mostrar formulario
    materias_primas = MateriaPrima.query.filter_by(activa=True).order_by(MateriaPrima.nombre).all()
    return render_template('cocina/crear_receta.html', materias_primas=materias_primas)

def convertir_a_unidad_base(cantidad, unidad_origen, unidad_base_ingrediente):
    """Convierte a gramos o mililitros según la unidad base del ingrediente"""
    # Factores de conversión a gramos o ml
    factores = {
        'gramo': Decimal('1'),
        'kilogramo': Decimal('1000'),
        'mililitro': Decimal('1'),
        'litro': Decimal('1000'),
        'onza': Decimal('28.3495'),    # a gramos
        'libra': Decimal('453.592'),    # a gramos
        'onza_liquida': Decimal('29.5735'),  # a ml
        'taza': Decimal('240'),         # a ml (líquidos)
        'pieza': Decimal('50')          # 1 huevo = 50g aprox
    }
    
    try:
        cantidad_dec = Decimal(str(cantidad))
        
        # Si la unidad de origen existe en los factores
        if unidad_origen in factores:
            # Convertir a gramos o ml primero
            cantidad_base = cantidad_dec * factores[unidad_origen]
            
            # Si la unidad base del ingrediente es kg/lt, convertir a gramos/ml
            if unidad_base_ingrediente in ['kilogramo', 'litro']:
                cantidad_base *= Decimal('1000')
                
            return cantidad_base
        
        return cantidad_dec
    
    except Exception as e:
        app.logger.error(f'Error en conversión de unidades: {str(e)}')
        return Decimal('0')

@chefCocinero.route('/api/unidades_ingrediente/<int:id>')
@cocina_required
def get_unidades_ingrediente(id):
    """Endpoint para obtener unidades compatibles"""
    materia_prima = MateriaPrima.query.get_or_404(id)
    
    # Unidades compatibles basadas en gramos/ml
    if materia_prima.unidad_medida in ['gramo', 'kilogramo']:
        unidades = [
            {'valor': 'gramo', 'texto': 'Gramos (g)'},
            {'valor': 'kilogramo', 'texto': 'Kilogramos (kg)'},
            {'valor': 'onza', 'texto': 'Onzas (oz)'},
            {'valor': 'libra', 'texto': 'Libras (lb)'}
        ]
    elif materia_prima.unidad_medida in ['mililitro', 'litro']:
        unidades = [
            {'valor': 'mililitro', 'texto': 'Mililitros (ml)'},
            {'valor': 'litro', 'texto': 'Litros (L)'},
            {'valor': 'onza_liquida', 'texto': 'Onzas líquidas (fl oz)'},
            {'valor': 'taza', 'texto': 'Tazas (cup)'}
        ]
    else:  # pieza
        unidades = [
            {'valor': 'pieza', 'texto': 'Unidades'}
        ]
    
    return jsonify({
        'unidades': unidades,
        'unidad_base': materia_prima.unidad_medida
    })

@chefCocinero.route('/listar_recetas')
@cocina_required
def listar_recetas():
    recetas = Receta.query.order_by(Receta.nombre_receta).all()  # Removed filter to show all recipes
    return render_template('cocina/listar_recetas.html', recetas=recetas)

@chefCocinero.route('/detalle_receta/<int:id>')
@cocina_required
def detalle_receta(id):
    receta = Receta.query.get_or_404(id)
    return render_template('cocina/detalle_receta.html', receta=receta)

@chefCocinero.route('/cambiar_estado_receta/<int:id>', methods=['POST'])
@cocina_required
def cambiar_estado_receta(id):
    receta = Receta.query.get_or_404(id)
    nuevo_estado = not receta.activa
    receta.activa = nuevo_estado
    
    # Si se está desactivando la receta, buscar y desactivar la galleta asociada
    if not nuevo_estado:
        galleta_asociada = Galleta.query.filter_by(receta_id=receta.id).first()
        if galleta_asociada:
            galleta_asociada.activa = False
            flash(f'Receta {receta.nombre_receta} y su galleta asociada han sido desactivadas', 'warning')
        else:
            flash(f'Receta {receta.nombre_receta} desactivada (no tenía galleta asociada)', 'success')
    else:
        flash(f'Receta {receta.nombre_receta} activada correctamente', 'success')
    
    db.session.commit()
    return redirect(url_for('chefCocinero.listar_recetas'))


@chefCocinero.route('/modificar_receta/<int:id>', methods=['GET', 'POST'])
@cocina_required
def modificar_receta(id):
    receta = Receta.query.get_or_404(id)
    galleta = Galleta.query.filter_by(receta_id=receta.id).first()
    
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            data = request.form
            receta.nombre_receta = data.get('nombre_receta')
            receta.descripcion = data.get('descripcion')
            receta.tiempo_preparacion = int(data.get('tiempo_preparacion'))
            receta.dias_caducidad = int(data.get('dias_caducidad'))
            porcentaje_ganancia = Decimal(data.get('porcentaje_ganancia'))
            peso_galleta = Decimal(data.get('peso_galleta', 100))  # Default 100g
            
            # Validaciones básicas
            if peso_galleta <= 0:
                flash('El peso por galleta debe ser mayor a cero', 'danger')
                return redirect(url_for('chefCocinero.modificar_receta', id=id))

            ingredientes = request.form.getlist('ingredientes[]')
            cantidades = request.form.getlist('cantidades[]')
            unidades = request.form.getlist('unidades[]')
            
            if not ingredientes:
                flash('Debe agregar al menos un ingrediente', 'danger')
                return redirect(url_for('chefCocinero.modificar_receta', id=id))

            # Eliminar ingredientes antiguos
            IngredienteReceta.query.filter_by(receta_id=receta.id).delete()
            db.session.flush()
            
            costo_total_receta = Decimal('0')
            peso_total = Decimal('0')
            
            # Procesar cada ingrediente
            for i, ingrediente_id in enumerate(ingredientes):
                materia_prima = MateriaPrima.query.get_or_404(ingrediente_id)
                cantidad = Decimal(cantidades[i])
                unidad = unidades[i]
                
                # Convertir a gramos o mililitros
                cantidad_base = convertir_a_unidad_base(cantidad, unidad, materia_prima.unidad_medida)
                
                if cantidad_base <= 0:
                    flash(f'Cantidad inválida para {materia_prima.nombre}', 'danger')
                    return redirect(url_for('chefCocinero.modificar_receta', id=id))
                
                # Calcular costo (precio_compra ya está en gramos/ml)
                costo_ingrediente = cantidad_base * materia_prima.precio_compra
                costo_total_receta += costo_ingrediente
                peso_total += cantidad_base
                
                # Registrar ingrediente
                db.session.add(IngredienteReceta(
                    receta_id=receta.id,
                    materia_prima_id=materia_prima.id,
                    cantidad_necesaria=cantidad_base,
                    observaciones=f"{cantidades[i]} {unidad}"
                ))
            
            # Validar y calcular cantidad de galletas
            if peso_total <= 0:
                flash('El peso total debe ser mayor a cero', 'danger')
                return redirect(url_for('chefCocinero.modificar_receta', id=id))

            cantidad_galletas = int((peso_total / peso_galleta).to_integral_value())
            if cantidad_galletas <= 0:
                flash('La receta no produce galletas válidas', 'danger')
                return redirect(url_for('chefCocinero.modificar_receta', id=id))

            receta.cantidad_galletas_producidas = cantidad_galletas
            
            # Cálculos financieros
            costo_por_galleta = costo_total_receta / Decimal(cantidad_galletas)
            precio_venta = costo_por_galleta * (1 + (porcentaje_ganancia / Decimal('100')))
            
            # Actualizar galleta asociada
            galleta.nombre = receta.nombre_receta
            galleta.costo_galleta = round(costo_por_galleta, 2)
            galleta.precio = round(precio_venta, 2)
            galleta.descripcion = receta.descripcion
            
            db.session.commit()
            
            flash(
                f'✅ Receta actualizada: {cantidad_galletas} galletas de {peso_galleta}g\n'
                f'💰 Costo: ${round(costo_por_galleta, 2)} c/u | '
                f'Precio: ${round(precio_venta, 2)} | '
                f'Ganancia: {round(((precio_venta - costo_por_galleta) / costo_por_galleta * 100), 1)}%',
                'success'
            )
            return redirect(url_for('chefCocinero.listar_recetas'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al modificar receta: {str(e)}', 'danger')
            app.logger.error(f'Error en modificar_receta: {str(e)}', exc_info=True)
            return redirect(url_for('chefCocinero.modificar_receta', id=id))
    
    # GET: Mostrar formulario con datos actuales
    materias_primas = MateriaPrima.query.filter_by(activa=True).order_by(MateriaPrima.nombre).all()
    
    # Calcular porcentaje de ganancia actual
    porcentaje_actual = 0
    if galleta and galleta.costo_galleta > 0:
        porcentaje_actual = ((galleta.precio - galleta.costo_galleta) / galleta.costo_galleta) * 100
    
    # Obtener ingredientes actuales de la receta
    ingredientes_actuales = IngredienteReceta.query.filter_by(receta_id=receta.id).all()
    
    # Calcular peso total actual para determinar peso por galleta
    peso_total_actual = sum(i.cantidad_necesaria for i in ingredientes_actuales)
    peso_galleta_actual = peso_total_actual / receta.cantidad_galletas_producidas if receta.cantidad_galletas_producidas > 0 else 100
    
    return render_template('cocina/modificar_receta.html', 
                         receta=receta,
                         galleta=galleta,
                         materias_primas=materias_primas,
                         ingredientes_actuales=ingredientes_actuales,
                         porcentaje_actual=round(porcentaje_actual, 2),
                         peso_galleta_actual=round(peso_galleta_actual, 2))