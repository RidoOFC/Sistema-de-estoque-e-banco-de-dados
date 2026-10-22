from flask import Flask, render_template, Blueprint
from db import init_db
from routes import main
import os
from dotenv import load_dotenv

load_dotenv()


app=Flask(__name__)
app.secret_key = 'minha_chave_super_secreta_para_o_flask_123'


# Regista as rotas vindas do ficheiro routes.py
app.register_blueprint(main)


@app.route('/') 
def home():
  return render_template('index.html',
        total_produtos=0,
        total_estoque_baixo=0,
        valor_total=0.0
    )  # 'I' maiúsculo como está na pasta


if __name__ == '__main__':
  init_db()
  app.run(debug=True)