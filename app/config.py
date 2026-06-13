from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql://proteinaja:trocar_em_producao@postgres:5432/proteinaja_db"
    evolution_api_url: str = "http://evolution-api:8080"
    evolution_api_key: str = "trocar_em_producao"
    evolution_instance_name: str = "frigorifico_sao_lucas"
    groq_api_key: str = "gsk_xxxxx"
    jwt_secret: str = "secret_muito_longo_para_producao"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24
    frigorifico_nome: str = "Frigorífico São Lucas"
    frigorifico_cidade: str = "Goiás"

    class Config:
        env_file = ".env"

settings = Settings()
