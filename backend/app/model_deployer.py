from __future__ import annotations

import os
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    balanced_accuracy_score,
    f1_score,
    log_loss,
)

from app.config import get_settings
from app.model_service import model_service


settings = get_settings()
_deployment_lock = threading.Lock()


@dataclass(frozen=True)
class PromotionDecision:
    approved: bool
    reasons: list[str]
    candidate_metrics: dict[str, float]
    current_metrics: dict[str, float]


@dataclass(frozen=True)
class DeploymentResult:
    production_path: Path
    backup_path: Path
    deployed_package_version: str


def evaluate_package_on_dataset(
    package: dict[str, Any],
    features: pd.DataFrame,
    target: pd.Series,
) -> dict[str, float]:
    """在同一验证集上评估一个模型包。"""

    model = package.get("model")
    feature_columns = list(package.get("feature_columns", []))

    if model is None:
        raise ValueError("模型包缺少 model。")

    if not feature_columns:
        raise ValueError("模型包缺少 feature_columns。")

    input_frame = features.reindex(columns=feature_columns).copy()
    true_labels = target.astype(str).copy()

    predicted_labels = model.predict(input_frame)
    predicted_probabilities = model.predict_proba(input_frame)
    model_classes = [str(item) for item in model.classes_.tolist()]

    missing_classes = sorted(set(true_labels) - set(model_classes))
    if missing_classes:
        raise ValueError(
            "模型不支持验证集中的类别："
            f"{missing_classes}"
        )

    if not np.all(np.isfinite(predicted_probabilities)):
        raise ValueError("模型验证概率包含无效数值。")

    return {
        "macro_f1": float(
            f1_score(
                true_labels,
                predicted_labels,
                average="macro",
                zero_division=0,
            )
        ),
        "balanced_accuracy": float(
            balanced_accuracy_score(
                true_labels,
                predicted_labels,
            )
        ),
        "log_loss": float(
            log_loss(
                true_labels,
                predicted_probabilities,
                labels=model_classes,
            )
        ),
    }


def evaluate_promotion(
    candidate_package: dict[str, Any],
    current_package: dict[str, Any],
    candidate_metrics: dict[str, float],
    current_metrics: dict[str, float],
) -> PromotionDecision:
    """判断候选模型是否满足自动晋升条件。"""

    reasons: list[str] = []

    candidate_classes = [
        str(item)
        for item in candidate_package.get("class_labels", [])
    ]
    current_classes = [
        str(item)
        for item in current_package.get("class_labels", [])
    ]

    if (
        settings.auto_model_deployment_require_same_classes
        and candidate_classes != current_classes
    ):
        reasons.append(
            "候选模型类别列表与当前正式模型不一致"
        )

    candidate_columns = list(
        candidate_package.get("feature_columns", [])
    )
    current_columns = list(
        current_package.get("feature_columns", [])
    )

    if (
        settings.auto_model_deployment_require_same_feature_columns
        and candidate_columns != current_columns
    ):
        reasons.append(
            "候选模型输入字段与当前正式模型不一致"
        )

    candidate_macro_f1 = float(candidate_metrics["macro_f1"])
    current_macro_f1 = float(current_metrics["macro_f1"])

    if (
        candidate_macro_f1
        < settings.auto_model_deployment_minimum_macro_f1
    ):
        reasons.append(
            "候选模型 Macro-F1 低于绝对最低门槛："
            f"{candidate_macro_f1:.4f} < "
            f"{settings.auto_model_deployment_minimum_macro_f1:.4f}"
        )

    if (
        candidate_macro_f1
        < current_macro_f1
        - settings.auto_model_deployment_macro_f1_tolerance
    ):
        reasons.append(
            "候选模型 Macro-F1 低于当前模型："
            f"{candidate_macro_f1:.4f} < {current_macro_f1:.4f}"
        )

    candidate_balanced_accuracy = float(
        candidate_metrics["balanced_accuracy"]
    )
    current_balanced_accuracy = float(
        current_metrics["balanced_accuracy"]
    )

    if (
        candidate_balanced_accuracy
        < settings.auto_model_deployment_minimum_balanced_accuracy
    ):
        reasons.append(
            "候选模型 Balanced Accuracy 低于绝对最低门槛："
            f"{candidate_balanced_accuracy:.4f} < "
            f"{settings.auto_model_deployment_minimum_balanced_accuracy:.4f}"
        )

    if (
        candidate_balanced_accuracy
        < current_balanced_accuracy
        - settings.auto_model_deployment_balanced_accuracy_tolerance
    ):
        reasons.append(
            "候选模型 Balanced Accuracy 低于当前模型："
            f"{candidate_balanced_accuracy:.4f} < "
            f"{current_balanced_accuracy:.4f}"
        )

    candidate_log_loss = float(candidate_metrics["log_loss"])
    current_log_loss = float(current_metrics["log_loss"])

    if (
        candidate_log_loss
        > current_log_loss
        + settings.auto_model_deployment_log_loss_tolerance
    ):
        reasons.append(
            "候选模型 Log Loss 高于当前模型："
            f"{candidate_log_loss:.4f} > {current_log_loss:.4f}"
        )

    return PromotionDecision(
        approved=not reasons,
        reasons=reasons,
        candidate_metrics=dict(candidate_metrics),
        current_metrics=dict(current_metrics),
    )


def _safe_name(value: object) -> str:
    text = str(value or "unknown")
    return "".join(
        character
        if character.isalnum() or character in {"-", "_", "."}
        else "-"
        for character in text
    )[:80]


def _prune_backups() -> None:
    keep_count = max(1, int(settings.auto_model_backup_count))
    backups = sorted(
        settings.model_backups_dir.glob("*.joblib"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )

    for old_backup in backups[keep_count:]:
        try:
            old_backup.unlink()
        except OSError:
            pass


def rollback_to_backup(
    backup_path: Path,
    sample_feature_values: dict[str, Any],
) -> None:
    """将正式模型恢复为指定备份，并热加载。"""

    if not backup_path.exists():
        raise FileNotFoundError(
            f"回滚备份不存在：{backup_path}"
        )

    production_path = settings.model_path
    production_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_restore_path = production_path.with_suffix(
        ".rollback.joblib"
    )

    if temporary_restore_path.exists():
        temporary_restore_path.unlink()

    shutil.copy2(backup_path, temporary_restore_path)
    os.replace(temporary_restore_path, production_path)

    model_service.reload()
    model_service.predict(sample_feature_values)


def deploy_candidate(
    candidate_path: Path,
    sample_feature_values: dict[str, Any],
) -> DeploymentResult:
    """
    原子替换正式模型、热加载并执行健康预测。

    任一步失败都会恢复旧模型。
    """

    with _deployment_lock:
        candidate_package = model_service.validate_model_file(
            candidate_path,
            sample_feature_values,
        )

        production_path = settings.model_path
        if not production_path.exists():
            raise FileNotFoundError(
                f"当前正式模型不存在：{production_path}"
            )

        settings.model_backups_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        production_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        current_package = model_service.package or {}
        current_version = _safe_name(
            current_package.get("package_version", "unknown")
        )
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = (
            settings.model_backups_dir
            / f"production-{timestamp}-{current_version}.joblib"
        )

        shutil.copy2(production_path, backup_path)

        temporary_deploy_path = production_path.with_suffix(
            ".deploying.joblib"
        )

        if temporary_deploy_path.exists():
            temporary_deploy_path.unlink()

        try:
            shutil.copy2(candidate_path, temporary_deploy_path)
            os.replace(temporary_deploy_path, production_path)

            model_service.reload()
            model_service.predict(sample_feature_values)

            loaded_package = model_service.package or {}
            loaded_version = str(
                loaded_package.get("package_version", "unknown")
            )
            candidate_version = str(
                candidate_package.get("package_version", "unknown")
            )

            if loaded_version != candidate_version:
                raise RuntimeError(
                    "热加载后的模型版本与候选模型不一致。"
                )

            _prune_backups()

            return DeploymentResult(
                production_path=production_path,
                backup_path=backup_path,
                deployed_package_version=candidate_version,
            )

        except Exception as deployment_error:
            try:
                rollback_to_backup(
                    backup_path,
                    sample_feature_values,
                )
            except Exception as rollback_error:
                raise RuntimeError(
                    "候选模型部署失败，并且自动回滚也失败："
                    f"部署错误={deployment_error!r}；"
                    f"回滚错误={rollback_error!r}"
                ) from rollback_error

            raise RuntimeError(
                "候选模型部署失败，已自动恢复旧模型："
                f"{deployment_error}"
            ) from deployment_error
