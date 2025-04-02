from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.models import db, Usuarios, Galleta, Pedido, DetallePedido, Venta, DetalleVenta
from werkzeug.security import check_password_hash, generate_password_hash
from models.formsLogin import LoginForm, RegistrarClientesForm
from datetime import timedelta
from functools import wraps

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        password = form.password.data
        remember = form.remember_me.data
        
        usuario = Usuarios.query.filter_by(email=email).first()
        
        if not usuario:
            flash('Credenciales incorrectas', 'error')
        elif not check_password_hash(usuario.password, password):
            flash('Credenciales incorrectas', 'error')
        else:
            session['user_id'] = usuario.id
            session['user_rol'] = usuario.rol
            session['user_nombre'] = usuario.nombre
            
            if remember:
                session.permanent = True
                # Configurar duración de la sesión (30 días)
                auth_bp.permanent_session_lifetime = timedelta(days=30)
            
            if usuario.rol == 'Admin':
                return redirect(url_for('admin.menuAdmin'))
            elif usuario.rol == 'Ventas':
                return redirect(url_for('ventas.menuVentas'))
            elif usuario.rol == 'Cocina':
                return redirect(url_for('chefCocinero.inventario'))
            elif usuario.rol == 'Cliente':
                return redirect(url_for('cliente.menuCliente'))
            
        return redirect(url_for('auth.login'))
    
    return render_template('login/login.html', form=form)

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión correctamente', 'success')
    return redirect(url_for('auth.login'))



@auth_bp.route("/registrarClientes", methods=['GET', 'POST'])
def registrarClientes():
    form = RegistrarClientesForm()
    form.rol.data = 'Cliente'  # Valor por defecto
    
    if form.validate_on_submit():
        try:
            # Normalizar email (minúsculas, sin espacios)
            email = form.email.data.lower().strip()
            
            # Verificar si el email ya existe
            if Usuarios.query.filter_by(email=email).first():
                flash('Este email ya está registrado. ¿Quieres iniciar sesión?', 'error')
                return redirect(url_for('auth.login'))
            
            # Crear nuevo usuario
            nuevo_usuario = Usuarios(
                nombre=form.nombre.data.strip(),
                email=email,
                password=generate_password_hash(form.password.data, method='pbkdf2:sha256'),
                telefono=form.telefono.data.strip(),
                direccion=form.direccion.data.strip(),
                rol=form.rol.data,
                fechaRegistro=form.fechaRegistro.data
            )
            
            db.session.add(nuevo_usuario)
            db.session.commit()
            
            # Autenticar al usuario directamente después del registro
            session['user_id'] = nuevo_usuario.id
            session['user_rol'] = nuevo_usuario.rol
            session['user_nombre'] = nuevo_usuario.nombre
            
            flash(f'¡Bienvenido {nuevo_usuario.nombre}! Tu registro fue exitoso.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar: {str(e)}', 'error')
            # Log del error para depuración
            app.logger.error(f'Error en registro: {str(e)}')
    
    return render_template('login/registrarClientes.html', form=form)


# Decorador para Admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_rol' not in session or session['user_rol'] != 'Admin':
            flash("Acceso restringido: Solo para administradores", "danger")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorador para Ventas
def ventas_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_rol' not in session or session['user_rol'] != 'Ventas':
            flash("Acceso restringido: Solo para personal de ventas", "danger")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorador para Cocina
def cocina_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_rol' not in session or session['user_rol'] != 'Cocina':
            flash("Acceso restringido: Solo para personal de cocina", "danger")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorador para Cliente
def cliente_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_rol' not in session or session['user_rol'] != 'Cliente':
            flash("Acceso restringido: Solo para clientes", "danger")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function
