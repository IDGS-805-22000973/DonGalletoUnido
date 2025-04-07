from datetime import datetime, timedelta
from flask import Blueprint, flash, redirect, render_template, request, jsonify, make_response, url_for
from models import models
from models.forms import RecetaForm
from models.forms import GalletaForm, DeleteForm  
from models.models import db, Usuarios, Galleta, Pedido, DetallePedido, Venta, DetalleVenta, Proveedor, PagoProveedor, MateriaPrima, Receta, IngredienteReceta, InventarioGalleta, EstadoGalleta
from flask_wtf.csrf import generate_csrf
from werkzeug.exceptions import BadRequest
from decimal import Decimal
from flask import jsonify
from sqlalchemy.exc import SQLAlchemyError
import os
from werkzeug.utils import secure_filename
from decimal import Decimal


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


@chefCocinero.route("/recetas")
def recetas():
    create_form = RecetaForm(request.form)
    recetas = Receta.query.all()  # Cambiado de 'receta' a 'recetas' (plural)
    return render_template("cocina/recetas.html", form=create_form, recetas=recetas)



import os
from decimal import Decimal
from werkzeug.utils import secure_filename
from flask import flash, redirect, render_template, request, url_for
import uuid

UPLOAD_FOLDER = 'static/uploads/recetas'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@chefCocinero.route('/agregar_receta', methods=['GET', 'POST'])
def agregar_receta():
    form = RecetaForm(request.form) if request.method == 'POST' else RecetaForm()
    materias_primas = MateriaPrima.query.all()

    if request.method == 'POST' and form.validate_on_submit():
        try:
            # --- Manejo de la imagen --- #
            foto_file = request.files.get('foto')
            foto_url = None

            if foto_file and foto_file.filename != '':
                if not allowed_file(foto_file.filename):
                    flash('Formato de imagen no permitido. Usa PNG, JPG, JPEG o GIF.', 'danger')
                    return redirect(url_for('chefCocinero.agregar_receta'))

                ext = foto_file.filename.rsplit('.', 1)[1].lower()
                base_name = secure_filename(foto_file.filename.rsplit('.', 1)[0])
                if not base_name:
                    base_name = f"receta_{uuid.uuid4().hex[:6]}"
                filename = f"{base_name}.{ext}"

                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                filepath = os.path.join(UPLOAD_FOLDER, filename)

                foto_file.save(filepath)

                if not os.path.exists(filepath):
                    raise Exception("Error al guardar la imagen")

                foto_url = f'/static/uploads/recetas/{filename}'
                print(f"[DEBUG] Foto guardada: {foto_url}")  # Para verificar que se asigna correctamente

            # --- Crear la receta --- #
            nueva_receta = Receta(
                nombre_receta=form.nombreReceta.data,
                descripcion=form.descripcion.data,
                cantidad_galletas_producidas=int(form.cantidadGalletaProducida.data),
                dias_caducidad=int(form.diasCaducidad.data),
                tiempo_preparacion=int(form.tiempoPreparacion.data),
                activa=True,
                foto_url=foto_url
            )
            db.session.add(nueva_receta)
            db.session.flush()  # Obtener ID antes de commit

            # --- Manejo de ingredientes --- #
            ingredientes_ids = request.form.getlist('ingrediente_id[]')
            cantidades = request.form.getlist('cantidad[]')
            unidades = request.form.getlist('unidad[]')

            for mp_id, cant, unidad in zip(ingredientes_ids, cantidades, unidades):
                if cant.strip():
                    try:
                        cantidad_decimal = Decimal(cant)
                        if cantidad_decimal <= 0:
                            flash("Las cantidades deben ser mayores a 0", "danger")
                            db.session.rollback()
                            return redirect(url_for('chefCocinero.agregar_receta'))

                        db.session.add(IngredienteReceta(
                            receta_id=nueva_receta.id,
                            materia_prima_id=int(mp_id),
                            cantidad_necesaria=cantidad_decimal,
                            unidad_medida=unidad
                        ))
                    except ValueError:
                        flash("Cantidad inválida detectada", "danger")
                        db.session.rollback()
                        return redirect(url_for('chefCocinero.agregar_receta'))

            # --- Commit final --- #
            db.session.commit()
            flash("¡Receta creada exitosamente!", "success")
            return redirect(url_for('chefCocinero.getAll_receta'))

        except Exception as e:
            db.session.rollback()
            flash(f"Error al guardar: {str(e)}", "danger")
            print(f"ERROR: {str(e)}")

    return render_template("cocina/recetas.html", 
                        form=form, 
                        materias_primas=materias_primas)


@chefCocinero.route('/getAll_receta', methods=['GET'])
def getAll_receta():
    recetas = Receta.query.all()
    recetas_lista = [
        {
            "id": receta.id,
            "nombre_receta": receta.nombre_receta,
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
def editar_receta(receta_id):
    receta = Receta.query.get_or_404(receta_id)
    
    receta.nombre_receta = request.form['nombre_receta']
    receta.descripcion = request.form['descripcion']
    receta.cantidad_galletas_producidas = int(request.form['cantidad_galletas_producidas'])
    receta.tiempo_preparacion = int(request.form['tiempo_preparacion'])
    receta.dias_caducidad = int(request.form['dias_caducidad'])
    receta.activa = 'activa' in request.form
    
    db.session.commit()
    
    flash("Receta actualizada con éxito", "success")
    return redirect(url_for('chefCocinero.getAll_receta'))


@chefCocinero.route('/eliminar_receta/<int:receta_id>', methods=['POST'])
def eliminar_receta(receta_id):
    receta = Receta.query.get(receta_id)

    if receta:
        try:
            print(f"Eliminando receta ID {receta_id}...")

            # Usamos no_autoflush para evitar el flush automático de la sesión
            with db.session.no_autoflush:
                # Eliminar dependencias de las galletas primero
                for galleta in receta.galletas:
                    print(f"Eliminando galleta ID {galleta.id} asociada a la receta...")

                    # Eliminar dependencias asociadas a la galleta
                    for inventario in galleta.inventario:
                        db.session.delete(inventario)
                    for detalle_pedido in galleta.detalles_pedido:
                        db.session.delete(detalle_pedido)
                    for detalle_venta in galleta.detalles_venta:
                        db.session.delete(detalle_venta)
                    for solicitud in galleta.solicitudes:
                        db.session.delete(solicitud)

                    # Finalmente eliminar la galleta
                    db.session.delete(galleta)

                # Eliminar ingredientes de la receta
                for ingrediente in receta.ingredientes:
                    db.session.delete(ingrediente)

                # Eliminar la receta
                db.session.delete(receta)

                # Hacer commit de todos los cambios en la sesión
                db.session.commit()

            print("Receta eliminada correctamente.")
            return redirect(url_for('chefCocinero.getAll_receta'))

        except Exception as e:
            db.session.rollback()
            print(f"Error eliminando receta: {e}")
            return f"Error eliminando receta: {e}", 500

    return "Receta no encontrada", 404



@chefCocinero.route("/buscar_recetas", methods=["GET"])
def buscar_recetas():
    form = RecetaForm() 
    query = request.args.get("query", "").strip().lower()
    recetas = Receta.query.all()
    if query:
        recetas = [r for r in recetas if 
            query in r.nombre_receta.lower() or
            query in r.descripcion.lower() or
            query in str(r.cantidad_galletas_producidas) or
            query in str(r.tiempo_preparacion) or
            query in str(r.dias_caducidad) or
            (query in "sí" if r.activa else "no")]

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render_template("cocina/buscarReceta.html", recetas=recetas)
    
    return render_template("cocina/buscarReceta.html", recetas=recetas, form=form)



def calcular_costo_galleta(receta_id):
    ingredientes = IngredienteReceta.query.filter_by(receta_id=receta_id).all()
    total_costo = Decimal('0.00')  # Asegúrate de que total_costo sea un Decimal

    for ingrediente in ingredientes:
        materia = MateriaPrima.query.get(ingrediente.materia_prima_id)
        if materia:
            costo_unitario = Decimal(str(materia.precio_compra))  # Convertir a Decimal
            cantidad = Decimal(str(ingrediente.cantidad_necesaria))  # Convertir a Decimal
            total_costo += costo_unitario * cantidad

    return round(total_costo, 2)


@chefCocinero.route('/crear_galleta', methods=['GET', 'POST'])
def crear_galleta():
    form = GalletaForm()
    recetas = Receta.query.all()

    # Rellenar el SelectField con las recetas
    form.receta_id.choices = [(receta.id, receta.nombre_receta) for receta in recetas]

    if form.validate_on_submit():
        nombre = form.nombre.data
        receta_id = form.receta_id.data  # Ahora se obtiene del formulario
        descripcion = form.descripcion.data  # Ahora se obtiene del formulario

        # Calcular el costo
        costo_galleta = calcular_costo_galleta(receta_id)
        precio_venta = round(costo_galleta * Decimal("1.30"), 2)

        nueva_galleta = Galleta(
            nombre=nombre,
            receta_id=receta_id,
            descripcion=descripcion,
            precio=precio_venta,
            costo_galleta=costo_galleta
        )
        db.session.add(nueva_galleta)
        db.session.commit()

        flash(f"Galleta '{nombre}' creada con éxito. Costo: ${costo_galleta}, Precio de venta: ${precio_venta}", 'success')
        return redirect(url_for('chefCocinero.crear_galleta'))

    return render_template('cocina/crearGalleta.html', form=form, recetas=recetas)

@chefCocinero.route('/obtener_galletas', methods=['GET'])
def obtener_galletas():
    # Obtener todas las galletas de la base de datos
    galletas = Galleta.query.all()

    # Formatear las galletas para enviarlas como JSON
    galletas_data = []
    for galleta in galletas:
        galletas_data.append({
            'id': galleta.id,
            'nombre': galleta.nombre,
            'receta': galleta.receta.nombre_receta if galleta.receta else '',
            'descripcion': galleta.descripcion
        })

    # Retornar las galletas como JSON
    return jsonify(galletas_data)


@chefCocinero.route('/eliminar_galleta/<int:id>', methods=['POST'])
def eliminar_galleta(id):
    print(f"Intentando eliminar galleta con id: {id}")
    galleta = Galleta.query.get(id)

    if galleta:
        try:
            # Eliminar dependencias de las relaciones
            # Eliminamos todos los registros en las tablas relacionadas
            for inventario in galleta.inventario:
                db.session.delete(inventario)
            for detalle_pedido in galleta.detalles_pedido:
                db.session.delete(detalle_pedido)
            for detalle_venta in galleta.detalles_venta:
                db.session.delete(detalle_venta)
            for solicitud in galleta.solicitudes:
                db.session.delete(solicitud)
            
            # Luego eliminar la galleta
            db.session.delete(galleta)
            db.session.commit()

            print("Galleta eliminada correctamente.")
            return jsonify({'mensaje': 'Galleta eliminada correctamente'}), 200
        except Exception as e:
            db.session.rollback()
            print(f"Error eliminando galleta: {e}")
            return jsonify({'error': str(e)}), 500
    print("Galleta no encontrada.")
    return jsonify({'error': 'Galleta no encontrada'}), 404
