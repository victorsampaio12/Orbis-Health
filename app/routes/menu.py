from flask import Blueprint, render_template

menu_bp = Blueprint('menu_bp', __name__)

@menu_bp.route('/menu-socorrista')
def menu_socorrista():
    return render_template('menusocorrista.html')
