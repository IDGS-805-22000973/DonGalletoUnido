from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.models import db, Usuarios, Galleta, Pedido, DetallePedido, Venta, DetalleVenta
from werkzeug.security import check_password_hash, generate_password_hash
from models.formsAdmin import RegistrarEmpleadosForm, ModificarEmpleadosForm
from controller.auth import admin_required

admin_bp = Blueprint('admin', __name__)


@admin_bp.route("/menuAdmin", methods=['GET', 'POST'])
@admin_required
def menuAdmin():
    return render_template("admin/menuAdmin.html")

@admin_bp.route("/ABCempleados", methods=["GET", "POST"])
@admin_required
def ABCempleados():
    usuarios = Usuarios.query.all()
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


