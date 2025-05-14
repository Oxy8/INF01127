from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import os

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("PGSOCKET_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# User Model
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, unique=True, nullable=False)
    celular = db.Column(db.String, nullable=False)
    localizacao = db.Column(db.String, nullable=False)
    foto_url = db.Column(db.String, nullable=True)

# Admin Model (inherits User)
class Admin(db.Model):
    __tablename__ = "admins"
    id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    nivel_permissao = db.Column(db.String, nullable=False)

# Plant Model
class Plant(db.Model):
    __tablename__ = "plants"
    id = db.Column(db.Integer, primary_key=True)
    nome_especie = db.Column(db.String, nullable=False)
    familia = db.Column(db.String, nullable=False)
    genero = db.Column(db.String, nullable=False)
    tamanho = db.Column(db.String, nullable=False)  # pequeno, médio, grande
    localizacao = db.Column(db.String, nullable=False)  # pode ser coordenadas
    status_troca = db.Column(db.String, nullable=False)  # disponível, em negociação, trocada
    usuario_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    data_cadastro = db.Column(db.DateTime, nullable=False)
    foto_url = db.Column(db.String, nullable=True)

# Search Plants (Basic Implementation)
@app.route("/search_plants", methods=["GET"])
def search_plants():
    especie = request.args.get("especie")
    familia = request.args.get("familia")
    genero = request.args.get("genero")
    raio = request.args.get("raio")

    query = Plant.query
    if especie:
        query = query.filter(Plant.nome_especie.ilike(f"%{especie}%"))
    if familia:
        query = query.filter(Plant.familia.ilike(f"%{familia}%"))
    if genero:
        query = query.filter(Plant.genero.ilike(f"%{genero}%"))
    # Placeholder for radius filtering - requires geospatial support
    # if raio:
    #     query = query.filter_by_radius(User.localizacao, raio)

    plants = query.all()
    return jsonify([{
        "id": plant.id,
        "nome_especie": plant.nome_especie,
        "familia": plant.familia,
        "genero": plant.genero,
        "tamanho": plant.tamanho,
        "localizacao": plant.localizacao,
        "status_troca": plant.status_troca,
        "data_cadastro": plant.data_cadastro.strftime("%Y-%m-%d %H:%M:%S"),
        "foto_url": plant.foto_url
    } for plant in plants])

# Basic Routes
@app.route("/users", methods=["GET"])
def get_users():
    users = User.query.all()
    return jsonify([{"id": user.id, "name": user.name} for user in users])

@app.route("/add_user", methods=["POST"])
def add_user():
    new_name = request.json.get("name")
    new_email = request.json.get("email")
    new_celular = request.json.get("celular")
    new_localizacao = request.json.get("localizacao")
    if new_name and new_email:
        new_user = User(name=new_name, email=new_email, celular=new_celular, localizacao=new_localizacao)
        db.session.add(new_user)
        db.session.commit()
    return jsonify({"status": "success"})

@app.route("/remove_user", methods=["POST"])
def remove_user():
    remove_id = request.json.get("remove_id")
    if remove_id:
        user_to_remove = User.query.get(remove_id)
        if user_to_remove:
            db.session.delete(user_to_remove)
            db.session.commit()
    return jsonify({"status": "success"})

@app.route("/", methods=["GET"])
def home():
    return render_template("home.html")


'''
# Dropa 1 tabela (para modificar ela)
with app.app_context():
    db.session.execute(text("DROP TABLE IF EXISTS users CASCADE"))
    db.session.commit()

with app.app_context():
    db.create_all()
'''



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
