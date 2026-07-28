from __future__ import annotations

import math
import threading
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from app.config import get_settings


settings = get_settings()

MODEL_PATH = settings.model_path


def make_json_safe(value: Any) -> Any:
    """
    将 NumPy 类型和 NaN 转换成可以安全返回给前端的值。
    """

    if isinstance(value, np.generic):
        value = value.item()

    if isinstance(value, float):
        if not math.isfinite(value):
            return None

        return value

    if isinstance(value, dict):
        return {
            str(key): make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            make_json_safe(item)
            for item in value
        ]

    return value


class DiagnosisModelService:
    def __init__(self, model_path: Path) -> None:
        self.model_path = model_path

        self.package: dict[str, Any] | None = None
        self.model: Any | None = None

        self.feature_columns: list[str] = []
        self.class_labels: list[str] = []
        self.feature_schema: list[dict[str, Any]] = []

        # 防止预测和模型替换同时发生
        self._lock = threading.RLock()

    @property
    def loaded(self) -> bool:
        return (
            self.package is not None
            and self.model is not None
        )

    def _read_and_validate_package(
        self,
        model_path: Path,
    ) -> dict[str, Any]:
        if not model_path.exists():
            raise FileNotFoundError(
                f"没有找到模型文件：{model_path}"
            )

        if model_path.stat().st_size <= 0:
            raise RuntimeError(
                f"模型文件为空：{model_path}"
            )

        package = joblib.load(model_path)

        if not isinstance(package, dict):
            raise TypeError(
                "模型文件不是有效的模型包字典。"
            )

        required_keys = {
            "model",
            "feature_columns",
            "class_labels",
        }

        missing_keys = (
            required_keys - set(package)
        )

        if missing_keys:
            raise KeyError(
                "模型包缺少必要内容："
                f"{sorted(missing_keys)}"
            )

        model = package["model"]

        if not hasattr(model, "predict"):
            raise TypeError(
                "模型不支持 predict。"
            )

        if not hasattr(
            model,
            "predict_proba",
        ):
            raise TypeError(
                "模型不支持 predict_proba。"
            )

        feature_columns = list(
            package["feature_columns"]
        )

        class_labels = list(
            package["class_labels"]
        )

        if not feature_columns:
            raise ValueError(
                "模型输入字段列表为空。"
            )

        if not class_labels:
            raise ValueError(
                "模型类别列表为空。"
            )

        return package

    def _apply_package(
        self,
        package: dict[str, Any],
    ) -> None:
        self.package = package
        self.model = package["model"]

        self.feature_columns = list(
            package["feature_columns"]
        )

        self.class_labels = list(
            package["class_labels"]
        )

        self.feature_schema = list(
            package.get(
                "feature_schema",
                [],
            )
        )

    def load(self) -> None:
        """
        从正式模型文件加载模型。
        """

        package = self._read_and_validate_package(
            self.model_path
        )

        with self._lock:
            self._apply_package(package)

    def reload(self) -> None:
        """
        热加载正式模型文件，不需要重启 FastAPI。
        """

        package = self._read_and_validate_package(
            self.model_path
        )

        with self._lock:
            self._apply_package(package)

    def load_from_path(
        self,
        model_path: Path,
    ) -> None:
        """
        从指定模型文件加载，主要用于候选模型验证。
        """

        package = self._read_and_validate_package(
            model_path
        )

        with self._lock:
            self._apply_package(package)

    def validate_model_file(
        self,
        model_path: Path,
        sample_feature_values: dict[str, Any],
    ) -> dict[str, Any]:
        """
        验证模型包，并实际执行一次预测。
        不改变当前正在使用的模型。
        """

        package = self._read_and_validate_package(
            model_path
        )

        model = package["model"]

        feature_columns = list(
            package["feature_columns"]
        )

        row: dict[str, Any] = {}

        for column in feature_columns:
            value = sample_feature_values.get(column)

            if value in ("", None):
                row[column] = np.nan
            else:
                row[column] = value

        input_frame = pd.DataFrame(
            [row],
            columns=feature_columns,
        )

        predictions = model.predict(input_frame)
        probabilities = model.predict_proba(
            input_frame
        )

        if len(predictions) != 1:
            raise RuntimeError(
                "候选模型预测结果数量异常。"
            )

        if probabilities.shape[0] != 1:
            raise RuntimeError(
                "候选模型概率结果数量异常。"
            )

        if not np.all(
            np.isfinite(probabilities)
        ):
            raise RuntimeError(
                "候选模型概率包含无效数值。"
            )

        probability_sum = float(
            probabilities[0].sum()
        )

        if not np.isclose(
            probability_sum,
            1.0,
            atol=1e-5,
        ):
            raise RuntimeError(
                "候选模型概率之和不等于 1。"
            )

        return package

    def ensure_loaded(self) -> None:
        if not self.loaded:
            self.load()

    def get_info(self) -> dict[str, Any]:
        self.ensure_loaded()

        with self._lock:
            assert self.package is not None
            assert self.model is not None

            information = {
                "loaded": True,
                "model_file": self.model_path.name,
                "model_file_size": (
                    self.model_path.stat().st_size
                ),
                "package_version": self.package.get(
                    "package_version"
                ),
                "best_model_name": self.package.get(
                    "best_model_name"
                ),
                "created_at": self.package.get(
                    "created_at"
                ),
                "feature_count": len(
                    self.feature_columns
                ),
                "feature_columns": list(
                    self.feature_columns
                ),
                "feature_schema": list(
                    self.feature_schema
                ),
                "class_labels": list(
                    self.class_labels
                ),
                "test_metrics": self.package.get(
                    "test_metrics",
                    {},
                ),
                "prediction_time_assumption": (
                    self.package.get(
                        "prediction_time_assumption"
                    )
                ),
                "sklearn_version": (
                    self.package.get(
                        "sklearn_version"
                    )
                ),
                "sample_count": self.package.get(
                    "sample_count"
                ),
                "training_source": self.package.get(
                    "training_source"
                ),
            }

        return make_json_safe(information)

    def create_input_frame(
        self,
        feature_values: dict[str, Any],
    ) -> pd.DataFrame:
        """
        按训练时的字段顺序创建一行模型输入。
        """

        self.ensure_loaded()

        with self._lock:
            feature_columns = list(
                self.feature_columns
            )

        row: dict[str, Any] = {}

        for column in feature_columns:
            value = feature_values.get(column)

            if value in ("", None):
                row[column] = np.nan
            else:
                row[column] = value

        return pd.DataFrame(
            [row],
            columns=feature_columns,
        )

    def predict(
        self,
        feature_values: dict[str, Any],
    ) -> dict[str, Any]:
        self.ensure_loaded()

        input_frame = self.create_input_frame(
            feature_values
        )

        with self._lock:
            assert self.model is not None

            predicted_values = self.model.predict(
                input_frame
            )

            probability_values = (
                self.model.predict_proba(
                    input_frame
                )
            )

            model_classes = [
                str(item)
                for item in self.model.classes_
            ]

            class_labels = list(
                self.class_labels
            )

        predicted_label = str(
            predicted_values[0]
        )

        probabilities = {
            class_name: float(
                probability_values[0][index]
            )
            for index, class_name
            in enumerate(model_classes)
        }

        for class_label in class_labels:
            probabilities.setdefault(
                class_label,
                0.0,
            )

        return {
            "predicted_label": predicted_label,
            "probabilities": probabilities,
        }


model_service = DiagnosisModelService(
    MODEL_PATH
)