from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.models import db, Proveedor
from models import forms

proveedores_bp = Blueprint('proveedores', __name__)

@proveedores_bp.route('/proveedores', methods=['GET', 'POST'])
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
        return redirect(url_for('proveedores.proveedores'))

    return render_template("proveedores.html", form=form, proveedores=proveedores)

@proveedores_bp.route('/proveedores/eliminar/<int:id>')
def eliminar_proveedor(id):
    proveedor = Proveedor.query.get(id)
    if proveedor:
        db.session.delete(proveedor)
        db.session.commit()
        flash("Proveedor eliminado correctamente", "success")

    return redirect(url_for('proveedores.proveedores'))