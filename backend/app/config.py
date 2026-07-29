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

    # ------------------------------
    # 自动训练
    # ------------------------------
    auto_training_enabled: bool = True

    # 每新增多少条未参与训练的医生标注后触发训练。
    auto_training_annotation_threshold: int = 20

    # 至少需要多少条有效标注数据才允许训练。
    auto_training_minimum_sample_count: int = 20

    # 每个诊断类别至少需要多少条样本。
    # 自动训练当前使用分层测试集和至少 2 折交叉验证，
    # 因此程序内部还会强制每类至少 3 条。
    auto_training_minimum_samples_per_class: int = 5

    # 保留旧配置名，兼容已有 .env。
    auto_training_macro_f1_tolerance: float = 0.0

    # ------------------------------
    # 自动模型部署
    # ------------------------------
    # 默认关闭。确认测试通过后，在 .env 中显式设置为 true。
    auto_model_deployment_enabled: bool = False

    # 候选模型允许比当前正式模型低多少。
    # 0 表示不允许降低。
    auto_model_deployment_macro_f1_tolerance: float = 0.0
    auto_model_deployment_balanced_accuracy_tolerance: float = 0.0

    # Log Loss 越小越好；该值表示候选模型最多允许高出多少。
    auto_model_deployment_log_loss_tolerance: float = 0.0

    # 绝对最低指标门槛。
    auto_model_deployment_minimum_macro_f1: float = 0.0
    auto_model_deployment_minimum_balanced_accuracy: float = 0.0

    # 自动部署时要求类别和输入字段与当前模型完全一致。
    auto_model_deployment_require_same_classes: bool = True
    auto_model_deployment_require_same_feature_columns: bool = True

    # 保留最近多少个正式模型备份。
    auto_model_backup_count: int = 5

    # ------------------------------
    # 项目路径
    # ------------------------------
    backend_dir: Path = Path(__file__).resolve().parent.parent
    project_root: Path = backend_dir.parent

    model_path: Path = (
        backend_dir
        / "models"
        / "diagnosis_classifier.joblib"
    )

    model_versions_dir: Path = (
        backend_dir
        / "models"
        / "versions"
    )

    model_backups_dir: Path = (
        backend_dir
        / "models"
        / "backups"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
