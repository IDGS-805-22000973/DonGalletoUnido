from flask import Flask, render_template, request, redirect, url_for, blueprints
from flask import flash
from flask_wtf.csrf import CSRFProtect
from flask import g
from models.config import DevelopmentConfig
from models.models import db, Usuarios, Galleta, Pedido, DetallePedido, Venta, DetalleVenta
from models.forms import GalletaForm
from werkzeug.security import generate_password_hash
import models.forms
from controller.auth import auth_bp
from controller.admin import admin_bp
from controller.ventas import ventas_bp
from controller.cocina import chefCocinero
from controller.cliente import cliente_bp


app = Flask(__name__)
app.config.from_object(DevelopmentConfig)

# Inicializar extenciones
csrf=CSRFProtect()
csrf.init_app(app)
db.init_app(app)


# Registrar Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(ventas_bp)
app.register_blueprint(chefCocinero)
app.register_blueprint(cliente_bp)

@app.route('/')
def index():
    return render_template('conocenos.html')


@app.route("/conocenos")
def conocenos():
    return render_template("conocenos.html")



if __name__ == "__main__":
    with app.app_context():
        # Crear tablas si no existen
        db.create_all()
        
        # Verificar y crear usuarios de prueba para cada rol
        try:
            # Usuario Admin
            if not Usuarios.query.filter_by(email="admin@example.com").first():
                admin = Usuarios(
                    nombre="Administrador",
                    email="admin@example.com",
                    password=generate_password_hash("admin1234"),
                    rol="Admin",
                )
                db.session.add(admin)
            
            # Usuario Ventas
            if not Usuarios.query.filter_by(email="ventas@example.com").first():
                ventas = Usuarios(
                    nombre="Vendedor",
                    email="ventas@example.com",
                    password=generate_password_hash("ventas1234"),
                    rol="Ventas",
                )
                db.session.add(ventas)
            
            # Usuario Cocina
            if not Usuarios.query.filter_by(email="cocinero@example.com").first():
                cocinero = Usuarios(
                    nombre="Cocinero",
                    email="cocinero@example.com",
                    password=generate_password_hash("cocinero1234"),
                    rol="Cocina",
                )
                db.session.add(cocinero)
            
            # Usuario Cliente
            if not Usuarios.query.filter_by(email="cliente@example.com").first():
                cliente = Usuarios(
                    nombre="Cliente",
                    email="cliente@example.com",
                    password=generate_password_hash("cliente1234"),
                    rol="Cliente",
                )
                db.session.add(cliente)
            
            db.session.commit()
            print("✅ Usuarios de prueba creados exitosamente")
            
        except Exception as e:
            print(f"Error al crear usuarios de prueba: {str(e)}")
            db.session.rollback()
    
    app.run(debug=True, port=5000)