import sys
sys.path.insert(0, ".")
from app.database import SessionLocal, engine
from app.database import Base
from app.models import Usuario
from app.services.auth import hash_senha

Base.metadata.create_all(bind=engine)
db = SessionLocal()

if not db.query(Usuario).filter(Usuario.email == "marcos@frigorifico.com").first():
    db.add(Usuario(nome="Marcos Ribeiro", email="marcos@frigorifico.com", senha_hash=hash_senha("senha123")))
    db.commit()
    print("Usuário criado: marcos@frigorifico.com / senha123")
else:
    print("Usuário já existe.")
db.close()
