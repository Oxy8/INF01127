from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from geoalchemy2 import Geography
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.sql import func
from sqlalchemy.orm import joinedload
from sqlalchemy import text
from sqlalchemy import select, func, desc
from flask_login import LoginManager, login_required, UserMixin, login_user, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import requests
from datetime import datetime
import googlemaps

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("PGSOCKET_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Nesse arquivo principal vamos definir toda as classes da base de dados via SQLAlchemy


gmaps = googlemaps.Client(key='AIzaSyC-V9Fb47uj2paEagjSaMQ3cto9wVEidSQ')

'''
# Geocoding an address
endereco_usuario = "Rua Cabral, 150, Rio Branco, Porto Alegre, RS"
geocode_result = gmaps.geocode(endereco_usuario)

print(geocode_result)
'''


#=======================================================
# Dados
#=======================================================

class Localizacao(db.Model):
    __tablename__ = 'localizacoes'

    id = db.Column(db.Integer, primary_key=True)
    
    # Campos do endereço
    rua = db.Column(db.String(255))
    numero = db.Column(db.String(20))
    complemento = db.Column(db.String(100))
    bairro = db.Column(db.String(100))
    cidade = db.Column(db.String(100))
    uf = db.Column(db.String(2))
    cep = db.Column(db.String(10))

    # As coordenadas geográficas
    coordenadas = db.Column(Geography(geometry_type='POINT', srid=4326), nullable=True)

    # Relacionamento de volta para a Pessoa (um-para-um)
    pessoa = db.relationship('Pessoa', back_populates='localizacao')




class Pessoa(db.Model, UserMixin):
    __tablename__ = 'pessoas'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=True) 
    celular = db.Column(db.String(20), nullable=True)
    foto_url = db.Column(db.String, nullable=True)
    localizacao_id = db.Column(db.Integer, db.ForeignKey('localizacoes.id'), nullable=True) # objeto localizacao

    # Nivel de permissão do administrador
    nivel_permissao = db.Column(db.String(50), nullable=True) 


    localizacao = db.relationship('Localizacao', back_populates='pessoa', uselist=False, cascade='all, delete-orphan', single_parent=True)
    plants = db.relationship('Plant', back_populates='owner', cascade='all, delete-orphan') 

    # Discriminação do SQLAlchemy
    type = db.Column(db.String(50), nullable=False)

    __mapper_args__ = {
        'polymorphic_on': type, # Usa a coluna 'type' como discriminador
        'polymorphic_identity': 'pessoa' 
    }


# CLASSES FILHAS

class Usuario(Pessoa):
    __mapper_args__ = {
        'polymorphic_identity': 'normal_user'
    }

class Admin(Pessoa):
    __mapper_args__ = {
        'polymorphic_identity': 'admin'
    }

class Entregador(Pessoa):
    __mapper_args__ = {
        'polymorphic_identity': 'delivery_user' 
    }



class Plant(db.Model):
    __tablename__ = "plants"
    
    id = db.Column(db.Integer, primary_key=True)
    common_name = db.Column(db.String, nullable=False)              # nome_popular
    species_name = db.Column(db.String, nullable=True)              # nome_especie
    family = db.Column(db.String, nullable=True)                    # família
    genus = db.Column(db.String, nullable=True)                     # genero
    size = db.Column(db.String, nullable=False)                     # tamanho
    location = db.Column(db.String, nullable=False)                 # localizacao
    trade_status = db.Column(db.String, nullable=False)             # status_troca
    photo_url = db.Column(db.String, nullable=True)                 # foto_url
    created_at = db.Column(db.DateTime, server_default=func.now())  # data_criacao
    normal_user_id = db.Column(db.Integer, db.ForeignKey("pessoas.id", ondelete="CASCADE"), nullable=False)

    # Relationship deleta objetos na camada do python.
    # Deletar apenas em nível de banco de dados pode gerar
    # objetos fantasmas que não possuem ligação com base de dados
    owner = db.relationship("Pessoa", back_populates="plants")

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

class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, info={'label': 'Nome do Post'})
    status = db.Column(db.String(50), default='Disponível')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    owner_id = db.Column(db.Integer, db.ForeignKey('pessoas.id'), nullable=False)
    owner = db.relationship('Pessoa', backref=db.backref('posts', lazy='dynamic'))

    # Relações para a tabela de ofertas
    # 'offers_made' são as ofertas onde este post é o item OFERECIDO
    offers_made = db.relationship('Offer', 
                                  foreign_keys='Offer.offered_post_id', 
                                  back_populates='offered_post', 
                                  cascade='all, delete-orphan')

    # 'offers_received' são as ofertas onde este post é o item ALVO
    offers_received = db.relationship('Offer', 
                                      foreign_keys='Offer.target_post_id', 
                                      back_populates='target_post', 
                                      cascade='all, delete-orphan')

class Offer(db.Model):
    __tablename__ = 'offers'
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(50), default='Enviada') # Enviada, Aceita, Recusada
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # O Post que está sendo oferecido
    offered_post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    # O Post que se deseja em troca
    target_post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)

    # Relações para acessar os objetos Post
    offered_post = db.relationship('Post', foreign_keys=[offered_post_id], back_populates='offers_made')
    target_post = db.relationship('Post', foreign_keys=[target_post_id], back_populates='offers_received')
    
    # Proxies para facilitar o acesso aos donos
    offerer = association_proxy('offered_post', 'owner')
    target_owner = association_proxy('target_post', 'owner')

#=======================================================
# Login
#=======================================================

# Preparativos
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page' # Redireciona para a rota de login se o usuário não estiver logado

app.secret_key = 'chave-super-secretinha'

login_manager.login_view = 'login_page' # Redireciona para login_page caso não passe na guarda de @login_required


@login_manager.user_loader
def load_user(user_id):
    # Faz join com localizações antes de retornar.
    return db.session.query(Pessoa).options(
        joinedload(Pessoa.localizacao)
    ).get(int(user_id))


@app.route('/perform_login', methods=['POST'])
def perform_login():
    """Processa a tentativa de login do usuário."""
    
    data = request.get_json()
    if not data:
        return jsonify({"message": "Requisição inválida. Nenhum dado enviado."}), 400

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"message": "Email e senha são obrigatórios."}), 400

    
    pessoa = Pessoa.query.filter_by(email=email).first()


    if pessoa and check_password_hash(pessoa.password_hash, password):
        
        print(f"Usuário encontrado e senha correta: {pessoa.name}")
        login_user(pessoa) # management do flask-login
        
        return jsonify({
            "message": "Login realizado com sucesso!",
            "redirect_url": "/feed"  # URL para onde o frontend deve redirecionar
        }), 200
    else:
    
        return jsonify({"message": "Email ou senha inválidos."}), 401 # 401 Unauthorized


@app.route('/api/logout', methods=['POST'])
@login_required 
def logout():
    logout_user() 
    return jsonify({"status": "success", "message": "Você foi desconectado com sucesso."}), 200

#=======================================================
# Add, Remove, Get Users
#=======================================================


# precisa adicionar login required aqui, permitindo apenas admins com alto nível de permissão
# senão, implicaria em vazamento fácil das hashes das senhas.
@app.route("/api/users", methods=["GET"])
def get_users():
    users = User.query.all()
    return jsonify([{"id": user.id, "name": user.name} for user in users])

def processar_endereco_e_geocodificar(endereco_data: dict) -> Localizacao or None:
    if not endereco_data or not any(endereco_data.values()):
        return None

    rua = endereco_data.get("rua")
    numero = endereco_data.get("numero")
    bairro = endereco_data.get("bairro")
    cidade = endereco_data.get("cidade")
    uf = endereco_data.get("uf")
    cep = endereco_data.get("cep")
    complemento = endereco_data.get("complemento")
    
    partes_endereco = [rua, numero, bairro, cidade, uf]
    endereco_completo_str = ", ".join(filter(None, partes_endereco))

    if not endereco_completo_str:
        return None

    nova_localizacao = Localizacao(
        rua=rua,
        numero=numero,
        bairro=bairro,
        cidade=cidade,
        uf=uf,
        cep=cep,
        complemento=complemento,
    )

    try:
        geocode_result = gmaps.geocode(endereco_completo_str)
        if geocode_result:
            geometry = geocode_result[0]['geometry']['location']
            latitude = geometry['lat']
            longitude = geometry['lng']
            location_point = f'POINT({longitude} {latitude})'

            nova_localizacao.coordenadas = location_point
    except Exception as e:
        print(f"AVISO DE GEOCODIFICAÇÃO: Não foi possível obter coordenadas para '{endereco_completo_str}'. Erro: {e}")

    return nova_localizacao

@app.route("/api/add_user", methods=["POST"])
def add_user():
    # verificação
    data = request.get_json()
    if not data:
        return jsonify({"message": "Requisição inválida. Nenhum dado JSON recebido."}), 400

    name = data.get("name")
    email = data.get("email")
    celular = data.get("celular")
    password = data.get("password")

    if not all([name, email, password]):
        return jsonify({"message": "Nome, email e senha são obrigatórios."}), 400

    if Pessoa.query.filter_by(email=email).first():
        return jsonify({"message": "Este email já está em uso."}), 409

    # DELEGA toda a lógica de endereço e geocodificação para a função auxiliar.
    endereco_data = data.get("endereco", {})
    nova_localizacao = processar_endereco_e_geocodificar(endereco_data)

    # Criação do usuário
    hashed_password = generate_password_hash(
        password,
        method='pbkdf2:sha256',
        salt_length=8
    )
    new_user = Usuario(
        name=name,
        email=email,
        celular=celular,
        password_hash=hashed_password,
    )

    # Associação (se a localização foi criada com sucesso)
    if nova_localizacao:
        new_user.localizacao = nova_localizacao

    # Persistência no banco de dados
    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"status": "success", "message": "Usuário criado com sucesso!"}), 201
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao salvar no banco: {e}")
        return jsonify({"message": "Ocorreu um erro interno ao criar o usuário."}), 500

# "@login_required" just sets the need for the user to be logged, any conditionals on
# whether the current user can/cannot use a given functionality must be done manually.



@app.route("/remove_user", methods=["POST"])
@login_required
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
@app.route("/api/search_plants", methods=["GET"])
def search_plants():
    query = request.args.get("query")
    print(f"Received query: {query}")

    similarity_threshold = 0.5

    target = "teste"



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

    stmt = (
        select(
            Item,
            func.similarity(Item.name, search_term).label("sim")
        )
        .where(func.similarity(Item.name, search_term) > 0.2)
        .order_by(Item.name.op('<->')(search_term))
        .limit(10)
    )

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

'''
arquivos .py segmentados de acordo com funcionalidade.
(trocar, fazer login, feed...)

templates do alpine segmentados de acordo com componentes das páginas
(footer, header, display_plantas...)
'''

#=======================================================
# Render
#=======================================================
@app.route("/", methods=["GET"])
def home():
    return redirect(url_for('login_page')) 

@app.route('/perfil')
@login_required
def profile_page():
    """
    Busca os dados do usuário, seus posts e as ofertas que ele FEZ,
    usando a nova modelagem de Oferta como uma relação Post-Post.
    """
    user = current_user

    # 1. Buscar os posts do usuário (sem alteração aqui)
    user_posts_objects = user.posts.order_by(Post.created_at.desc()).all()

    # 2. Buscar as ofertas feitas pelo usuário
    # A lógica agora é: encontre todas as ofertas cujo `offered_post` pertence ao usuário.
    user_offers_objects = db.session.query(Offer).join(
        Post, Offer.offered_post_id == Post.id
    ).filter(
        Post.owner_id == user.id
    ).order_by(Offer.created_at.desc()).all()

    # 3. Transformar os objetos em dicionários para o frontend
    def get_status_info(status):
        status_map = {
            'Disponível': ('Disponível', 'status-disponivel'),
            'Trocado': ('Trocado', 'status-trocado'),
            'Enviada': ('Oferta Enviada', 'status-ofertado'),
            'Aceita': ('Troca Concluída', 'status-trocado'),
            'Recusada': ('Recusada', 'status-trocado'), # Pode ter uma cor diferente
        }
        return status_map.get(status, (status, 'status-trocado'))

    # Formatando posts (sem alteração)
    posts_data = []
    for post in user_posts_objects:
        status_text, status_class = get_status_info(post.status)
        posts_data.append({
            'id': f'p{post.id}',
            'title': post.name,
            'details': f'Criado em: {post.created_at.strftime("%d/%m/%Y")}',
            'statusText': status_text,
            'statusClass': status_class
        })

    # Formatando ofertas (NOVO FORMATO)
    offers_data = []
    for offer in user_offers_objects:
        status_text, status_class = get_status_info(offer.status)
        offers_data.append({
            'id': f'o{offer.id}',
            # O post que você quer
            'target_post_name': offer.target_post.name,
            'target_post_owner': offer.target_post.owner.name,
            # O post que você usou na troca
            'my_post_offered_name': offer.offered_post.name,
            'statusText': status_text,
            'statusClass': status_class,
        })

    return render_template('pages/user_profile.html', posts=posts_data, offers=offers_data)

@app.route("/register")
def register_page():
    return render_template("pages/register.html")

@app.route("/login")
def login_page():
    return render_template("pages/login.html")

@app.route("/feed")
@login_required
def feed_page():
    
    if isinstance(current_user, Admin):
        return render_template("pages/feed_admin.html")

    elif isinstance(current_user, Usuario):
        return render_template("pages/feed_user.html")
        
    elif isinstance(current_user, Entregador):
        return render_template("pages/feed_delivery.html")
        
    else:
        logout_user() # Desloga o usuário por segurança
        return redirect(url_for('login_page'))


@app.route("/criar-post")
@login_required
def create_post():
    
    if isinstance(current_user, Usuario):
        return render_template("pages/criar_post.html")
    
    else:
        logout_user() # Desloga o usuário por segurança
        return redirect(url_for('login_page'))

@app.route("/minhas-trocas")
@login_required
def trades():
    return redirect(url_for('profile_page')) 
    



@app.route('/api/update_profile', methods=['POST'])
@login_required
def update_profile():
    data = request.get_json()
    if not data:
        return jsonify({"message": "Requisição inválida"}), 400
    
    try:
        current_user.name = data['personal']['name']
        current_user.email = data['personal']['email']
        current_user.celular = data['personal']['celular']
        
        endereco_data = data.get('address', {})
        nova_localizacao = processar_endereco_e_geocodificar(endereco_data) 

        if current_user.localizacao:
            loc = current_user.localizacao
            loc.rua = nova_localizacao.rua
            loc.numero = nova_localizacao.numero
            loc.complemento = nova_localizacao.complemento
            loc.bairro = nova_localizacao.bairro
            loc.cidade = nova_localizacao.cidade
            loc.uf = nova_localizacao.uf
            loc.cep = nova_localizacao.cep
            loc.coordenadas = nova_localizacao.coordenadas
        else:
            current_user.localizacao = nova_localizacao
        
        db.session.commit()
        return jsonify({"status": "success", "message": "Perfil atualizado com sucesso!"}), 200
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Erro ao atualizar perfil: {str(e)}")
        return jsonify({"message": "Erro interno ao atualizar perfil"}), 500




'''
# Dropa 1 tabela (para modificar atributos dela)
with app.app_context():
    db.session.execute(text("DROP TABLE IF EXISTS plants CASCADE"))
    db.session.commit()
'''
'''o
# Cria as tabelas novamente (não vai mexer nas que já existem)
with app.app_context():
    db.create_all()
'''

## AAAAAAAAAAAAAAAA
## AAAAAAAAAAAAAAAA
'''
# DROPA TODAS AS TABELA, CUIDADO!!!
with app.app_context():
    db.drop_all()
'''
## AAAAAAAAAAAAAAAA
## AAAAAAAAAAAAAAAA



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)