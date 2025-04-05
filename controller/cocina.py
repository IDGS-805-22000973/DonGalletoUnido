from datetime import datetime, timedelta
from decimal import Decimal
from flask import Blueprint, flash, redirect, render_template, request, jsonify, make_response, session, url_for
from wtforms import DateField
from models.models import Merma, db, Usuarios, Galleta, Pedido, DetallePedido, Venta, DetalleVenta, Proveedor, PagoProveedor, MateriaPrima, Receta, IngredienteReceta, InventarioGalleta, EstadoGalleta
from flask_wtf.csrf import generate_csrf
from werkzeug.exceptions import BadRequest
from controller.auth import cocina_required
from models.forms import GalletaForm, PedidoForm, MateriasPrimasForm, ActualizarInventarioForm, RecetaForm, IngredientesRecetasForm

chefCocinero = Blueprint('chefCocinero', __name__)

@chefCocinero.route('/produccion')
@cocina_required
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
        return jsonify({"error": "Error interno", "detalle": str(e)}), 500
    
        
    
@chefCocinero.route('/guardar_cantidad', methods=['POST'])
@cocina_required
def guardar_cantidad():
    try:
        # Verificar sesión primero
        if 'user_id' not in session:
            return jsonify({
                "error": "No autenticado",
                "detalle": "Debe iniciar sesión primero",
                "redirect": url_for('auth.login')
            }), 401

        data = request.get_json()
        id_galleta = int(data['idGalleta'])
        hubo_merma = data.get('huboMerma', False)
        cantidad_merma = float(data.get('cantidadMerma', 0))
        motivo_merma = data.get('motivoMerma', '')

        # Obtenemos el usuario_id directamente de la sesión
        usuario_id = session['user_id']

        galleta = Galleta.query.get(id_galleta)
        if not galleta:
            return jsonify({"error": "Galleta no encontrada"}), 404
        
        cantidad_producida = galleta.receta.cantidad_galletas_producidas
        
        # Validaciones
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

        # Manejo de inventario
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
        
        # Registrar merma si aplica
        if hubo_merma and cantidad_merma > 0:
            inventario.stock -= cantidad_merma
            nueva_merma = Merma(
                tipo='Galleta Terminada',
                galleta_id=id_galleta,
                cantidad=cantidad_merma,
                motivo=motivo_merma,
                usuario_id=usuario_id
            )
            db.session.add(nueva_merma)

        # Resetear estado
        estado = EstadoGalleta.query.filter_by(galleta_id=id_galleta).first()
        if estado:
            estado.estatus = "Pendiente"
        
        db.session.commit()
        return jsonify({
            "message": f"Producción de {cantidad_producida} unidades registrada",
            "merma": f"Merma registrada: {cantidad_merma} unidades" if hubo_merma else None,
            "csrf_token": generate_csrf()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        print(f"Error guardando cantidad: {str(e)}")
        return jsonify({"error": "Error interno", "detalle": str(e)}), 500



    
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

@chefCocinero.route("/recetas")
@cocina_required
def recetas():
    create_form = RecetaForm(request.form)
    recetas = Receta.query.all()  # Cambiado de 'receta' a 'recetas' (plural)
    return render_template("cocina/recetas.html", form=create_form, recetas=recetas)


@chefCocinero.route('/agregar_receta', methods=['GET', 'POST'])
@cocina_required
def agregar_receta():
    form = RecetaForm(request.form) if request.method == 'POST' else RecetaForm()
    materias_primas = MateriaPrima.query.all()

    if request.method == 'POST' and form.validate_on_submit():
        try:
            nueva_receta = Receta(
                nombre_receta=request.form.get('nombreReceta'),
                descripcion=request.form.get('descripcion'),
                cantidad_galletas_producidas=int(request.form.get('cantidadGalletaProducida')),
                dias_caducidad=int(request.form.get('diasCaducidad')),
                ingrediente_especial=request.form.get('ingredienteEspecial'),
                tiempo_preparacion=0,
                activa=True
            )
            db.session.add(nueva_receta)
            db.session.flush()  

            cantidades = request.form.to_dict(flat=False)

            for materia in materias_primas:
                key = f"cantidadNecesaria[{materia.id}]"
                cantidad_lista = cantidades.get(key)

                if cantidad_lista and cantidad_lista[0].strip() != '':
                    cantidad = float(cantidad_lista[0])
                    if cantidad > 0:
                        ingrediente = IngredienteReceta(
                            receta_id=nueva_receta.id,
                            materia_prima_id=materia.id,
                            cantidad_necesaria=cantidad,
                            observaciones=""
                        )
                        db.session.add(ingrediente)

            db.session.commit()
            flash("Receta registrada con éxito", "success")
            return redirect(url_for('chefCocinero.getAll_receta'))

        except Exception as e:
            db.session.rollback()
            flash(f"Error al registrar la receta: {str(e)}", "danger")
            print(f"Error al registrar receta: {str(e)}")
    elif request.method == 'POST':
        flash("Por favor corrige los errores del formulario", "danger")

    return render_template("cocina/recetas.html", form=form, materias_primas=materias_primas)


@chefCocinero.route('/getAll_receta', methods=['GET'])
@cocina_required
def getAll_receta():
    recetas = Receta.query.all()

    recetas_lista = [
        {
            "id": receta.id,
            "nombre_receta": receta.nombre_receta,
            "ingrediente_especial": receta.ingrediente_especial,
            "descripcion": receta.descripcion, 
            "cantidad_galletas_producidas": receta.cantidad_galletas_producidas,
            "tiempo_preparacion": receta.tiempo_preparacion,
            "dias_caducidad": receta.dias_caducidad,            
            "activa": receta.activa
        }
        for receta in recetas
    ]

    form = RecetaForm()
    return render_template('cocina/vistaRecetas.html', recetas=recetas_lista, form=form)

@chefCocinero.route('/editar_receta/<int:receta_id>', methods=['POST'])
@cocina_required
def editar_receta(receta_id):
    receta = Receta.query.get_or_404(receta_id)
    
    receta.nombre_receta = request.form['nombre_receta']
    receta.ingrediente_especial = request.form['ingrediente_especial']
    receta.descripcion = request.form['descripcion']
    receta.cantidad_galletas_producidas = int(request.form['cantidad_galletas_producidas'])
    receta.tiempo_preparacion = int(request.form['tiempo_preparacion'])
    receta.dias_caducidad = int(request.form['dias_caducidad'])
    receta.activa = 'activa' in request.form
    
    db.session.commit()
    
    flash("Receta actualizada con éxito", "success")
    return redirect(url_for('chefCocinero.getAll_receta'))


@chefCocinero.route('/eliminar_receta/<int:receta_id>', methods=['POST'])
@cocina_required
def eliminar_receta(receta_id):
    receta = Receta.query.get_or_404(receta_id)
    db.session.delete(receta)
    db.session.commit()
    flash("Receta eliminada correctamente", "danger")
    return redirect(url_for('chefCocinero.getAll_receta'))

@chefCocinero.route("/buscar_recetas", methods=["GET"])
@cocina_required
def buscar_recetas():
    form = RecetaForm() 
    query = request.args.get("query", "").strip().lower()
    recetas = Receta.query.all()

    if query:
        recetas = [r for r in recetas if 
            query in r.nombre_receta.lower() or
            query in r.ingrediente_especial.lower() or
            query in r.descripcion.lower() or
            query in str(r.cantidad_galletas_producidas) or
            query in str(r.tiempo_preparacion) or
            query in str(r.dias_caducidad) or
            (query in "sí" if r.activa else "no")]

    return render_template('cocina/vistaRecetas.html', recetas=recetas, form=form)