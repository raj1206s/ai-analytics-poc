from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://analytics:analytics@localhost:5432/loan_analytics"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_model_fallbacks: str = (
        "gemini-3.6-flash,gemini-3.1-flash-lite,gemini-3-flash-preview,gemini-flash-lite-latest"
    )
    cors_origins: str = "http://localhost:3000"
    sql_timeout_ms: int = 10000
    sql_row_limit: int = 500

    @property
    def gemini_models(self) -> list[str]:
        models = [self.gemini_model.strip()]
        for model in self.gemini_model_fallbacks.split(","):
            model = model.strip()
            if model and model not in models:
                models.append(model)
        return models

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
