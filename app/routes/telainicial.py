from flask import Blueprint, render_template

telainicial_bp = Blueprint('telainicial', __name__)

@telainicial_bp.route('/')
def telainicial():
    return render_template('telainicial.html')
