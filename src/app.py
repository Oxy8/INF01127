from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import os
from datetime import datetime

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("PGSOCKET_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

#=======================================================
# Dados
#=======================================================
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
    nome_popular = db.Column(db.String, nullable=False)
    nome_especie = db.Column(db.String, nullable=True)
    familia = db.Column(db.String, nullable=True)
    genero = db.Column(db.String, nullable=True)
    tamanho = db.Column(db.String, nullable=False)  # pequeno, médio, grande
    localizacao = db.Column(db.String, nullable=False)
    status_troca = db.Column(db.String, nullable=False)  # disponível, em negociação, trocada
    # ondelete="CASCADE" requer que ao deletar um usuário seja forçada uma atualização da lista de plantas (reatividade não vai tão longe)
    usuario_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False) 
    data_cadastro = db.Column(db.DateTime, nullable=False)
    foto_url = db.Column(db.String, nullable=True)
    '''
    __table_args__ = (
        CheckConstraint(
            "LOWER(tamanho) IN ('pequeno', 'médio', 'grande')", name='tamanho_check'
        ),
        CheckConstraint(
            "LOWER(status_troca) IN ('disponível', 'em negociação', 'trocada')", name='status_troca_check'
        ),
    )
    '''

#=======================================================
# Add, Remove, Get Users
#=======================================================

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
    

#=======================================================
# Add, Remove, Get Plants
#=======================================================

@app.route("/plants", methods=["GET"])
def get_plants():
    plants = Plant.query.all()
    return jsonify([
        {
            "id": plant.id,
            "nome_popular": plant.nome_popular,
            "nome_especie": plant.nome_especie,
            "familia": plant.familia,
            "genero": plant.genero,
            "tamanho": plant.tamanho,
            "localizacao": plant.localizacao,
            "status_troca": plant.status_troca,
            "data_cadastro": plant.data_cadastro.strftime("%Y-%m-%d %H:%M:%S"),
            "foto_url": plant.foto_url,
            "usuario_id": plant.usuario_id
        }
        for plant in plants
    ])


@app.route("/add_plant", methods=["POST"])
def add_plant():
    nome_popular = request.json.get("nome_popular")
    nome_especie = request.json.get("nome_especie")
    familia = request.json.get("familia")
    genero = request.json.get("genero")
    tamanho = request.json.get("tamanho")
    localizacao = request.json.get("localizacao")
    status_troca = request.json.get("status_troca")
    usuario_id = request.json.get("usuario_id")
    data_cadastro = datetime.now() # Coloca data automaticamente
    foto_url = request.json.get("foto_url")

    if nome_popular and tamanho and localizacao and status_troca and usuario_id and data_cadastro:
        new_plant = Plant(
            nome_popular=nome_popular,
            nome_especie=nome_especie,
            familia=familia,
            genero=genero,
            tamanho=tamanho,
            localizacao=localizacao,
            status_troca=status_troca,
            usuario_id=usuario_id,
            data_cadastro=data_cadastro,
            foto_url=foto_url
        )
        db.session.add(new_plant)
        db.session.commit()

    return jsonify({"status": "success"})


@app.route("/remove_plant", methods=["POST"])
def remove_plant():
    remove_id = request.json.get("remove_id")
    
    if remove_id:
        plant_to_remove = Plant.query.get(remove_id)
        if plant_to_remove:
            db.session.delete(plant_to_remove)
            db.session.commit()

    return jsonify({"status": "success"})



#=======================================================
# SEARCH
#=======================================================
@app.route("/search_plants", methods=["GET"])
def search_plants():
    query = request.args.get("query")
    print(f"Received query: {query}")

    similarity_threshold = 0.3  # Adjust as needed

    if not query:
        return jsonify([])

    query = f"%{query}%"

    plants = Plant.query.filter(
        db.or_(
            Plant.nome_popular.ilike(query),
            Plant.nome_especie.ilike(query),
            Plant.genero.ilike(query),
            Plant.familia.ilike(query)
        )
    ).all()

    print("Found Plants:")
    for plant in plants:
        print(f"ID: {plant.id}, Nome Popular: {plant.nome_popular}, Especie: {plant.nome_especie}, Familia: {plant.familia}, Genero: {plant.genero}")

    return jsonify([
        {
            "id": plant.id,
            "nome_popular": plant.nome_popular,
            "nome_especie": plant.nome_especie,
            "familia": plant.familia,
            "genero": plant.genero,
            "tamanho": plant.tamanho,
            "localizacao": plant.localizacao,
            "status_troca": plant.status_troca,
            "data_cadastro": plant.data_cadastro.strftime("%Y-%m-%d %H:%M:%S"),
            "foto_url": plant.foto_url,
            "usuario_id": plant.usuario_id

        }
        for plant in plants
    ])



#=======================================================
# Render
#=======================================================
@app.route("/", methods=["GET"])
def home():
    return render_template("home.html")


'''
# Dropa 1 tabela (para modificar atributos ela)
with app.app_context():
    db.session.execute(text("DROP TABLE IF EXISTS plants CASCADE"))
    db.session.commit()

# Cria as tabelas novamente (não vai mexer nas que já)
with app.app_context():
    db.create_all()
'''



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)