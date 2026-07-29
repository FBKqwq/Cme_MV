from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "医院病人诊断辅助预测系统"
    app_version: str = "0.1.0"

    frontend_origin: str = "http://localhost:5173"
    runtime_data_root: Path = Path("data/runtime")
    review_data_root: Path = Path("data/review")

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
    model_path: Path = Path("backend/models/diagnosis_classifier.joblib")

    # 自动训练产生的模型版本目录
    model_versions_dir: Path = Path("data/runtime/models/versions")

    @field_validator(
        "runtime_data_root",
        "review_data_root",
        "model_path",
        "model_versions_dir",
    )
    @classmethod
    def require_relative_path(cls, value: Path) -> Path:
        if value.is_absolute():
            raise ValueError("数据与模型配置必须使用项目相对路径")
        return value

    def resolve_project_path(self, value: Path) -> Path:
        return self.project_root / value

    @property
    def runtime_data_path(self) -> Path:
        return self.resolve_project_path(self.runtime_data_root)

    @property
    def review_data_path(self) -> Path:
        return self.resolve_project_path(self.review_data_root)

    @property
    def model_file_path(self) -> Path:
        return self.resolve_project_path(self.model_path)

    @property
    def model_versions_path(self) -> Path:
        return self.resolve_project_path(self.model_versions_dir)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
