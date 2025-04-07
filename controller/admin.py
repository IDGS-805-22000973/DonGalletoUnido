from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.models import db, Usuarios, Galleta, Pedido, DetallePedido, Venta, DetalleVenta, Proveedor, Merma, MateriaPrima
from werkzeug.security import check_password_hash, generate_password_hash
from models.formsAdmin import RegistrarEmpleadosForm, ModificarEmpleadosForm
from controller.auth import admin_required
from models.forms import ProveedorForm, mostrarMermasForm
from models import forms  # Asegúrate de que forms.py tenga ProveedorForm


admin_bp = Blueprint('admin', __name__)


@admin_bp.route("/menuAdmin", methods=['GET', 'POST'])
@admin_required
def menuAdmin():
    return render_template("admin/menuAdmin.html")

@admin_bp.route("/ABCempleados", methods=["GET", "POST"])
@admin_required
def ABCempleados():
    # Filtrar usuarios excluyendo los que tienen rol 'Administrador'
    usuarios = Usuarios.query.filter(Usuarios.rol != 'Admin').all()
    return render_template("admin/ABCempleados.html", usuarios=usuarios)

@admin_bp.route("/AgregarEmpleado", methods=["GET", "POST"])
@admin_required
def agregarEmpleado():
    form = RegistrarEmpleadosForm(request.form)

    if form.validate_on_submit():
        try:
            # Verificar si el email ya existe
            if Usuarios.query.filter_by(email=form.email.data).first():
                flash('Este email ya está registrado', 'error')
                return redirect(url_for('admin.agregarEmpleado'))
            
            # Crear nuevo usuario
            nuevo_empleado = Usuarios(
                nombre=form.nombre.data.strip(),
                email=form.email.data,  # Corregido aquí
                password=generate_password_hash(form.password.data, method='pbkdf2:sha256'),
                telefono=form.telefono.data.strip(),
                direccion=form.direccion.data.strip(),
                rol=form.rol.data,
                fechaRegistro=form.fechaRegistro.data
            )
            
            db.session.add(nuevo_empleado)
            db.session.commit()
            
            flash('Empleado registrado exitosamente!', 'success')
            return redirect(url_for('admin.menuAdmin'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar: {str(e)}', 'error')
    
    return render_template('admin/AgregarEmpleado.html', form=form)


@admin_bp.route('/modificar', methods=['GET', 'POST'])
@admin_required
def modificar():
    form = ModificarEmpleadosForm(request.form)

    if request.method == 'GET':
        id = request.args.get('id')
        empleado = Usuarios.query.filter_by(id=id).first()
        
        if not empleado:
            flash('Empleado no encontrado', 'error')
            return redirect(url_for('admin.ABCempleados'))
        
        form.id.data = id
        form.nombre.data = empleado.nombre.strip() if empleado.nombre else ''
        form.email.data = empleado.email
        form.telefono.data = empleado.telefono.strip() if empleado.telefono else ''
        form.direccion.data = empleado.direccion.strip() if empleado.direccion else ''
        form.rol.data = empleado.rol
        form.fechaRegistro.data = empleado.fechaRegistro
        form.password.data = ''  # Campo vacío por seguridad

    if request.method == 'POST' and form.validate():
        id = form.id.data
        empleado = Usuarios.query.filter_by(id=id).first()
        
        if not empleado:
            flash('Empleado no encontrado', 'error')
            return redirect(url_for('admin.ABCempleados'))
        
        # Verificar si el email ya existe (excepto para este usuario)
        if Usuarios.query.filter(Usuarios.email == form.email.data, Usuarios.id != id).first():
            flash('Este email ya está registrado por otro usuario', 'error')
            return redirect(url_for('admin.modificar', id=id))
        
        # Actualizar datos
        empleado.nombre = form.nombre.data.strip()
        empleado.email = form.email.data
        empleado.telefono = form.telefono.data.strip()
        empleado.direccion = form.direccion.data.strip()
        empleado.rol = form.rol.data
        empleado.fechaRegistro = form.fechaRegistro.data
        
        # Solo actualizar contraseña si se proporcionó
        if form.password.data:
            empleado.password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        
        try:
            db.session.commit()
            flash('Empleado modificado correctamente', 'success')
            return redirect(url_for('admin.ABCempleados'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al modificar empleado: {str(e)}', 'error')
    
    return render_template('admin/modificarEmpleado.html', form=form)


@admin_bp.route("/eliminar/<int:id>", methods=["POST"])
@admin_required
def eliminar(id):
    empleado = Usuarios.query.get_or_404(id)
    try:
        db.session.delete(empleado)
        db.session.commit()
        flash('Empleado eliminado correctamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar empleado: {str(e)}', 'error')
    return redirect(url_for('admin.ABCempleados'))


@admin_bp.route('/proveedores', methods=['GET', 'POST'])
@admin_required
def proveedores():
    form = forms.ProveedorForm(request.form)
    proveedores = Proveedor.query.all()  # Obtener todos los proveedores

    if request.method == 'POST' and form.validate():
        if form.id.data:  # Si hay un ID, actualizamos el proveedor
            proveedor = Proveedor.query.get(form.id.data)
            if proveedor:
                proveedor.nombre_proveedor = form.nombre_proveedor.data
                proveedor.telefono = form.telefono.data
                proveedor.email = form.email.data
                proveedor.direccion = form.direccion.data
                flash("Proveedor actualizado correctamente", "success")
        else:  # Si no hay ID, creamos un nuevo proveedor
            nuevo_proveedor = Proveedor(
                nombre_proveedor=form.nombre_proveedor.data,
                telefono=form.telefono.data,
                email=form.email.data,
                direccion=form.direccion.data
            )
            db.session.add(nuevo_proveedor)
            flash("Proveedor agregado correctamente", "success")

        db.session.commit()
        return redirect(url_for('admin.proveedores'))

    return render_template("admin/proveedores.html", form=form, proveedores=proveedores)
# Función para eliminar proveedor
@admin_bp.route('/proveedores/eliminar/<int:id>')
def eliminar_proveedor(id):
    proveedor = Proveedor.query.get(id)
    if proveedor:
        db.session.delete(proveedor)
        db.session.commit()
        flash("Proveedor eliminado correctamente", "success")

    return redirect(url_for('admin.proveedores'))

#Control de mermas 
@admin_bp.route("/mostrarMermas", methods=['GET', 'POST'])
@admin_required
def mostrarMermas():
    form = mostrarMermasForm(request.form)
    
    # Consulta para obtener todas las mermas con sus relaciones
    mermas = db.session.query(
        Merma,
        MateriaPrima.nombre.label('nombre_materia_prima'),
        Galleta.nombre.label('nombre_galleta'),
        Usuarios.nombre.label('nombre_usuario')
    ).outerjoin(MateriaPrima, Merma.materia_prima_id == MateriaPrima.id)\
    .outerjoin(Galleta, Merma.galleta_id == Galleta.id)\
    .join(Usuarios, Merma.usuario_id == Usuarios.id)\
    .order_by(Merma.fecha_registro.desc()).all()
    return render_template("admin/mostrarMermas.html", form=form, mermas=mermas)

