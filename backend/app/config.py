from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "医院病人诊断辅助预测系统"
    app_version: str = "0.1.0"

    db_user: str
    db_password: str
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str

    frontend_origin: str = "http://localhost:5173"
    review_data_root: Path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "review"
    )

    # 自动训练是否启用
    auto_training_enabled: bool = True

    # 每新增多少条未参与训练的医生标注后触发训练
    auto_training_annotation_threshold: int = 1

    # 至少需要多少条有效标注数据才允许训练
    auto_training_minimum_sample_count: int = 5

    # 每个诊断类别至少需要多少条样本
    auto_training_minimum_samples_per_class: int = 1

    # 新模型的 Macro-F1 允许比当前模型低多少
    # 第一版建议不允许降低
    auto_training_macro_f1_tolerance: float = 0.0

    # 项目目录
    backend_dir: Path = Path(__file__).resolve().parent.parent
    project_root: Path = backend_dir.parent

    # 正式模型路径
    model_path: Path = (
        backend_dir
        / "models"
        / "diagnosis_classifier.joblib"
    )

    # 自动训练产生的模型版本目录
    model_versions_dir: Path = (
        backend_dir
        / "models"
        / "versions"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
