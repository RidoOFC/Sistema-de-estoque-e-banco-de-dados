from flask import Flask, render_template, Blueprint
from db import init_db
from routes import main

app = Flask(__name__)

# Regista as rotas vindas do ficheiro routes.py
app.register_blueprint(main)
app.secret_key = 'sua_chave_secreta_super_segura'


@app.route('/')
def home():
  return render_template('Index.html',
        total_produtos=0,
        total_estoque_baixo=0,
        valor_total=0.0
    )  # 'I' maiúsculo como está na pasta


if __name__ == '__main__':
  init_db()
  app.run(debug=True)