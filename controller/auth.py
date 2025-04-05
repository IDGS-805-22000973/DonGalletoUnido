from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.models import db, Usuarios
from werkzeug.security import check_password_hash, generate_password_hash
from models.formsLogin import LoginForm, RegistrarClientesForm, TwoFactorForm
from datetime import timedelta
from flask_login import login_user, logout_user, current_user, login_required
from functools import wraps
import pyotp
import qrcode
import io
import base64

auth_bp = Blueprint('auth', __name__)

# Configuración de 2FA
TOTP_ISSUER = "Panadería Dulce Tentación"

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        password = form.password.data
        remember = form.remember_me.data
        
        usuario = Usuarios.query.filter_by(email=email).first()
        
        if not usuario or not check_password_hash(usuario.password, password):
            flash('Credenciales incorrectas', 'error')
            return redirect(url_for('auth.login'))
        
        login_user(usuario, remember=remember)
        session['temp_user_id'] = usuario.id  # Solo para 2FA
        
        if usuario.two_factor_enabled:
            return redirect(url_for('auth.verify_2fa'))
        
        flash(f'Bienvenido, {usuario.nombre}!', 'success')
        return redirect_after_login(usuario.rol)
    
    return render_template('login/login.html', form=form)

def redirect_after_login(rol):
    if rol == 'Admin':
        return redirect(url_for('admin.ABCempleados'))
    elif rol == 'Ventas':
        return redirect(url_for('ventas.menuVentas'))
    elif rol == 'Cocina':
        return redirect(url_for('chefCocinero.inventario'))
    elif rol == 'Cliente':
        return redirect(url_for('cliente.menuCliente'))

@auth_bp.route('/verify-2fa', methods=['GET', 'POST'])
def verify_2fa():
    # Verificar que el usuario está en proceso de login
    if 'temp_user_id' not in session:
        return redirect(url_for('auth.login'))
    
    usuario = Usuarios.query.get(session['temp_user_id'])
    if not usuario:
        return redirect(url_for('auth.login'))
    
    form = TwoFactorForm()
    
    if form.validate_on_submit():
        # Verificar el código
        if verify_totp(usuario.two_factor_secret, form.verification_code.data):
            remember = session.get('temp_remember', False)
            return complete_login(usuario, remember)
        else:
            flash('Código de verificación incorrecto', 'error')
    
    return render_template('login/verify_2fa.html', form=form)

def verify_totp(secret, code):
    """Verifica un código TOTP contra el secreto"""
    if not secret or not code:
        return False
    try:
        totp = pyotp.TOTP(secret)
        return totp.verify(code)
    except:
        return False

def complete_login(usuario, remember):
    """Función para completar el login después de 2FA"""
    session.pop('temp_user_id', None)
    session.pop('temp_remember', None)
    
    session['user_id'] = usuario.id
    session['user_rol'] = usuario.rol
    session['user_nombre'] = usuario.nombre
    
    if remember:
        session.permanent = True
        auth_bp.permanent_session_lifetime = timedelta(days=30)
    
    if usuario.rol == 'Admin':
        return redirect(url_for('admin.ABCempleados'))
    elif usuario.rol == 'Ventas':
        return redirect(url_for('ventas.menuVentas'))
    elif usuario.rol == 'Cocina':
        return redirect(url_for('chefCocinero.inventario'))
    elif usuario.rol == 'Cliente':
        return redirect(url_for('cliente.menuCliente'))

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
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
                fechaRegistro=form.fechaRegistro.data,
                two_factor_secret=pyotp.random_base32(),  # Generar secreto para 2FA
                two_factor_enabled=False  # Por defecto desactivado
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



# Decorador para verificar que la autenticación en dos pasos esté activada
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.rol != 'Admin':
            flash("Acceso restringido: Solo para administradores", "danger")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def ventas_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.rol != 'Ventas':
            flash("Acceso restringido: Solo para personal de ventas", "danger")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def cocina_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.rol != 'Cocina':
            flash("Acceso restringido: Solo para personal de cocina", "danger")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def cliente_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.rol != 'Cliente':
            flash("Acceso restringido: Solo para clientes", "danger")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/setup-2fa', methods=['GET', 'POST'])
@login_required
def setup_2fa():
    usuario = Usuarios.query.get(session['user_id'])
    
    if request.method == 'POST':
        # Activar 2FA
        usuario.two_factor_enabled = True
        db.session.commit()
        flash('Autenticación en dos pasos activada correctamente', 'success')
        return redirect(url_for('auth.account_settings'))
    
    # Generar URI de configuración
    if not usuario.two_factor_secret:
        usuario.two_factor_secret = pyotp.random_base32()
        db.session.commit()
    
    totp = pyotp.TOTP(usuario.two_factor_secret)
    provisioning_uri = totp.provisioning_uri(
        name=usuario.email,
        issuer_name=TOTP_ISSUER
    )
    
    # Generar QR code
    img = qrcode.make(provisioning_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_code = base64.b64encode(buf.getvalue()).decode("ascii")
    
    # Mostrar clave manual también
    manual_key = ' '.join([usuario.two_factor_secret[i:i+4] for i in range(0, len(usuario.two_factor_secret), 4)])
    
    return render_template('login/setup_2fa.html', 
                         qr_code=qr_code,
                         manual_key=manual_key,
                         provisioning_uri=provisioning_uri)

@auth_bp.route('/disable-2fa', methods=['POST'])
@login_required
def disable_2fa():
    usuario = Usuarios.query.get(session['user_id'])
    usuario.two_factor_enabled = False
    db.session.commit()
    flash('Autenticación en dos pasos desactivada', 'success')
    return redirect(url_for('auth.account_settings'))

@auth_bp.route('/account/settings')
@login_required
def account_settings():
    usuario = Usuarios.query.get(session['user_id'])
    return render_template('account/settings.html', usuario=usuario)


