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
from werkzeug.utils import secure_filename
import uuid 
import requests
from datetime import datetime
import googlemaps

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("PGSOCKET_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Nesse arquivo principal vamos definir toda as classes da base de dados via SQLAlchemy


gmaps = googlemaps.Client(key='AIzaSyC-V9Fb47uj2paEagjSaMQ3cto9wVEidSQ')


app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)



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
    
    # Plantas são acessadas por meio de posts.
    
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



class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, info={'label': 'Nome do Post'})
    status = db.Column(db.String(50), default='Disponível')
    description = db.Column(db.Text, nullable=True) # Pode ser grande.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    owner_id = db.Column(db.Integer, db.ForeignKey('pessoas.id'), nullable=False)
    
    # db.relationships

    owner = db.relationship('Pessoa', backref=db.backref('posts', lazy='dynamic'))

    plants = db.relationship('Plant', back_populates='post', cascade='all, delete-orphan')

    offers_made = db.relationship('Offer', 
                                  foreign_keys='Offer.offered_post_id', 
                                  back_populates='offered_post', 
                                  cascade='all, delete-orphan')

    offers_received = db.relationship('Offer', 
                                      foreign_keys='Offer.target_post_id', 
                                      back_populates='target_post', 
                                      cascade='all, delete-orphan')

# Planta não tem relação direta com o seu dono. Uma planta pertence a um post, e um post pertence a uma pessoa.
class Plant(db.Model):
    __tablename__ = "plants"
    
    id = db.Column(db.Integer, primary_key=True)
    common_name = db.Column(db.String, nullable=False)              # nome_popular
    species_name = db.Column(db.String, nullable=True)              # nome_especie
    family = db.Column(db.String, nullable=True)                    # família
    genus = db.Column(db.String, nullable=True)                     # genero
    size = db.Column(db.String, nullable=False)                     # tamanho
    photo_url = db.Column(db.String, nullable=True)                 # foto_url
    created_at = db.Column(db.DateTime, server_default=func.now())  # data_criacao
    
    # Estrangeira
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    
    post = db.relationship('Post', back_populates='plants')

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

    user = current_user

    def get_status_info(status):

        status_map = {
            'Disponível': ('Disponível', 'status-disponivel'),
            'Em negociação': ('Em negociação', 'status-em-negociacao'),
            'Em andamento': ('Em andamento', 'status-em-andamento'),
            'Aguardando Entrega': ('Aguardando Entrega', 'status-aguardando-entrega'),
            'Concluída': ('Concluída', 'status-concluida'),
            'Cancelada': ('Cancelada', 'status-cancelada'),
            'Trocado': ('Trocado', 'status-concluida'), # Reserva
        }
        return status_map.get(status, (status, 'status-trocado'))


    # =======================================
    # Query posts 
    user_posts_objects = Post.query.filter_by(owner_id=user.id).order_by(Post.created_at.desc()).all()

    posts_data = []
    for post in user_posts_objects:
        primeira_planta = post.plants[0] if post.plants else None
        photo_url = primeira_planta.photo_url if primeira_planta else None
        
        status_text, status_class = get_status_info(post.status)

        posts_data.append({
            'id': f'p{post.id}',
            'title': post.name,
            'description': post.description or "",
            'details': f'Criado em: {post.created_at.strftime("%d/%m/%Y")}',
            'statusText': status_text,
            'statusClass': status_class,
            'photo_url': photo_url
        })



    # =======================================
    # Query ofertas
    user_offers_objects = db.session.query(Offer).join(
        Post, Offer.offered_post_id == Post.id
    ).filter(
        Post.owner_id == user.id
    ).order_by(Offer.created_at.desc()).all()

    offers_received_objects = db.session.query(Offer).join(
        Post, Offer.target_post_id == Post.id
    ).filter(
        Post.owner_id == user.id
    ).order_by(Offer.created_at.desc()).all()

    user_offers_objects = user_offers_objects + offers_received_objects

    offers_data = []
    for offer in user_offers_objects:
        target_post = offer.target_post
        primeira_planta_alvo = target_post.plants[0] if target_post.plants else None
        photo_url_alvo = primeira_planta_alvo.photo_url if primeira_planta_alvo else None
        status_text, status_class = get_status_info(offer.status)
        
        offers_data.append({
            'id': f'o{offer.id}',  
            'title': target_post.name,
            'description': target_post.description or "", 
            'photo_url': photo_url_alvo, 
            'details': f'Oferta por "{offer.offered_post.name}"',
            'statusText': status_text,
            'statusClass': status_class,
        })

    return render_template('pages/user_profile.html', posts=posts_data, offers=offers_data, current_user=current_user)

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
        
        pagination = Post.query.filter_by(status='Disponível').filter(Post.owner_id != current_user.id).order_by(Post.created_at.desc()).paginate(
            page=1, per_page=POSTS_PER_PAGE, error_out=False
        )
        
        initial_posts = [serialize_post(post) for post in pagination.items]
        user_posts_for_offer = Post.query.filter_by(owner_id=current_user.id, status='Disponível').all()
        serialized_user_posts = []
        for post in user_posts_for_offer:

            primeira_planta = post.plants[0] if post.plants else None
            photo_url = primeira_planta.photo_url if primeira_planta else None


            serialized_user_posts.append({
                'id': post.id,     
                'title': post.name,    
                'photo_url': photo_url  
            })
        
        page_data = {
            "initial_posts": initial_posts,
            "has_next_page": pagination.has_next,
            "user_posts_for_offer": serialized_user_posts 
        }

        return render_template('pages/feed_user.html', page_data=page_data, current_user=current_user)

            
    elif isinstance(current_user, Entregador):
        return render_template("pages/feed_delivery.html")
        
    else:
        logout_user() # Desloga o usuário por segurança
        return redirect(url_for('login_page'))




@app.route("/criar-post")
@login_required
def create_post_page():
    
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


@app.route('/api/create_post', methods=['POST'])
@login_required
def create_post():

    if 'common_name' not in request.form or 'size' not in request.form:
        return jsonify({'message': 'Nome popular e tamanho são obrigatórios.'}), 400

    new_post = Post(
        name = request.form.get('common_name'),
        owner_id=current_user.id,
        description=request.form.get('description')
        # Demais campos são de preenchimento automático
        # name é a exceção.
    )
    
    photo_url = None
    if 'photo' in request.files:
        file = request.files['photo']

        if file.filename != '':
            filename = secure_filename(file.filename)
            unique_filename = str(uuid.uuid4()) + "_" + filename
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(save_path)
            photo_url = url_for('static', filename=f'uploads/{unique_filename}', _external=True)


    new_plant = Plant(
        common_name=request.form.get('common_name'),
        size=request.form.get('size'),
        species_name=request.form.get('species_name'), # .get() retorna None se não existir
        family=request.form.get('family'),
        genus=request.form.get('genus'),
        photo_url=photo_url,  
        post=new_post         
    )

    try:
        db.session.add(new_post)
        # new_plant será salva por cascata por causa da relação
        db.session.commit()
        return jsonify({'message': 'Post criado com sucesso!'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Erro interno ao criar o post.'}), 500

def serialize_post(post):
    """
    Converte um objeto Post do SQLAlchemy em um dicionário seguro para JSON,
    respeitando a estrutura dos modelos de dados.
    """
    # 1. Obter a foto da primeira planta do post (lógica já estava correta)
    primeira_planta = post.plants[0] if post.plants else None
    photo_url = primeira_planta.photo_url if primeira_planta else None
    
    # 2. Construir os detalhes do usuário (PARTE CORRIGIDA)
    user_details = "Usuário desconhecido"
    # Verifica se o post tem um dono (owner) associado
    if post.owner:
        # Ponto de partida: o nome do dono sempre existe
        user_details = f"Por: {post.owner.name}"
        
        # Agora, verifica com segurança se o dono tem uma localização
        if post.owner.localizacao:
            cidade = post.owner.localizacao.cidade
            uf = post.owner.localizacao.uf
            
            # Adiciona a localização aos detalhes se ambos os campos existirem
            if cidade and uf:
                user_details += f" - {cidade}, {uf}"

    # 3. Montar o dicionário final com a estrutura que o frontend espera
    return {
        'id': f'p{post.id}',
        'title': post.name,
        'description': post.description or "",
        'user_details': user_details,  # Usando os detalhes corrigidos
        'statusText': 'Disponível',      # Para o feed, o status é sempre este
        'statusClass': 'status-disponivel',
        'photo_url': photo_url
    }




POSTS_PER_PAGE = 12 

@app.route('/api/load-posts')
def load_posts():
    # Pegamos o número da página da URL (ex: /api/load-posts?page=2)
    page = request.args.get('page', 1, type=int)

    pagination = Post.query.filter_by(status='Disponível').filter(Post.owner_id != current_user.id).order_by(Post.created_at.desc()).paginate(
        page=page, per_page=POSTS_PER_PAGE, error_out=False
    )
    
    posts_data = [serialize_post(post) for post in pagination.items]
    
    return jsonify({
        'posts': posts_data,
        'has_next': pagination.has_next
    })

@app.route('/api/create-offer', methods=['POST'])
@login_required
def create_offer():
    data = request.get_json()
    if not data or 'target_post_id' not in data or 'offered_post_id' not in data:
        return jsonify({'error': 'Dados inválidos.'}), 400

    target_post_id = data.get('target_post_id')
    offered_post_id = data.get('offered_post_id')

    target_post = Post.query.get(target_post_id)
    offered_post = Post.query.get(offered_post_id)

    if not target_post or not offered_post:
        return jsonify({'error': 'Post não encontrado.'}), 404

    if offered_post.owner_id != current_user.id:
        return jsonify({'error': 'Não autorizado. O post oferecido não é seu.'}), 403

    if target_post.owner_id == current_user.id:
        return jsonify({'error': 'Você não pode fazer uma oferta em seu próprio post.'}), 400

    if offered_post.status != 'Disponível':
        return jsonify({'error': 'Seu item oferecido não está mais disponível para troca.'}), 400

    existing_offer = Offer.query.filter_by(offered_post_id=offered_post_id, target_post_id=target_post_id).first()
    if existing_offer:
        return jsonify({'error': 'Você já fez uma oferta para este item com este mesmo post.'}), 409

    try:
        new_offer = Offer(
            offered_post_id=offered_post_id,
            target_post_id=target_post_id,
            status='Em negociação' # Ou use o default do seu modelo
        )

        offered_post.status = 'Em negociação'
        target_post.status = 'Em negociação'
        
        db.session.add(new_offer)
        db.session.commit()
        
        return jsonify({'message': 'Oferta enviada com sucesso!'}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Ocorreu um erro ao processar a oferta.'}), 500


@app.route('/api/delete_post', methods=['POST'])
@login_required
def delete_post():
    data = request.get_json()
    post_id_str = data.get('post_id')
    post_id = int(post_id_str.replace('p', ''))
    post = Post.query.get(post_id)

    if post.owner_id != current_user.id:
        return jsonify({'message': 'Acesso negado.'}), 403 # Forbidden

    try:
        db.session.delete(post)
        db.session.commit()
        return jsonify({'message': 'Post excluído com sucesso.'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Erro ao excluir o post.'}), 500


@app.route('/api/cancel_offer', methods=['POST'])
@login_required
def cancel_offer():
    data = request.get_json()
    offer_id_str = data.get('offer_id') 
    offer_id = int(offer_id_str.replace('o', ''))   
    offer = Offer.query.get(offer_id)

    offerer_id = offer.offerer.id
    recipient_id = offer.target_post.owner_id
    if current_user.id not in [offerer_id, recipient_id]:
        return jsonify({'message': 'Acesso negado. Você não faz parte desta negociação.'}), 403

    post_oferecido = offer.offered_post
    post_alvo = offer.target_post

    if post_oferecido:
        post_oferecido.status = 'Disponível'
    
    if post_alvo:
        post_alvo.status = 'Disponível'

    try:
        db.session.delete(offer)
        db.session.commit()
        return jsonify({'message': 'Oferta cancelada com sucesso.'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Erro ao cancelar a oferta.'}), 500


# Em app.py

@app.route('/api/confirm_trade', methods=['POST'])
@login_required
def confirm_trade():
    data = request.get_json()
    offer_id_str = data.get('offer_id')

    if not offer_id_str:
        return jsonify({'message': 'ID da oferta ausente.'}), 400

    offer_id = int(offer_id_str.replace('o', ''))
    offer_to_confirm = Offer.query.get(offer_id)

    if not offer_to_confirm:
        return jsonify({'message': 'Oferta não encontrada.'}), 404

    # Verificação de segurança: Apenas o destinatário da oferta pode confirmar.
    if offer_to_confirm.target_post.owner_id != current_user.id:
        return jsonify({'message': 'Acesso negado. Apenas o destinatário pode confirmar a troca.'}), 403

    # Posts envolvidos na troca principal
    offered_post = offer_to_confirm.offered_post
    target_post = offer_to_confirm.target_post

    try:
        offer_to_confirm.status = 'Aceita'
        offered_post.status = 'Trocado'
        target_post.status = 'Trocado'


        conflicting_offers = Offer.query.filter(
            Offer.id != offer_to_confirm.id, # Exclui a oferta que estamos aceitando
            or_(
                Offer.offered_post_id == offered_post.id,
                Offer.offered_post_id == target_post.id,
                Offer.target_post_id == offered_post.id,
                Offer.target_post_id == target_post.id
            )
        ).all()

        for conflict in conflicting_offers:
            if conflict.offered_post.status != 'Trocado':
                conflict.offered_post.status = 'Disponível'
            if conflict.target_post.status != 'Trocado':
                conflict.target_post.status = 'Disponível'
            
            db.session.delete(conflict)

        db.session.commit()
        return jsonify({'message': 'Troca confirmada com sucesso!'}), 200

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Erro ao confirmar a troca {offer_id}: {e}")
        return jsonify({'message': 'Erro interno ao confirmar a troca.'}), 500


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