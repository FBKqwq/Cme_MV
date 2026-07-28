from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, f1_score, log_loss
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import engine
from app.model_service import model_service
from app.models import Annotation, ModelVersion, TrainingJob
from app.training_dataset_service import build_training_dataset


settings = get_settings()

RANDOM_STATE = 42
TEST_SIZE = 0.20


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _make_one_hot_encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(
            handle_unknown="ignore",
            sparse_output=False,
        )
    except TypeError:
        return OneHotEncoder(
            handle_unknown="ignore",
            sparse=False,
        )


def _build_preprocessor(
    features: pd.DataFrame,
) -> tuple[ColumnTransformer, list[str], list[str]]:
    numeric_features = (
        features.select_dtypes(include=[np.number]).columns.tolist()
    )
    categorical_features = (
        features.select_dtypes(exclude=[np.number]).columns.tolist()
    )

    transformers: list[tuple[str, Pipeline, list[str]]] = []

    if numeric_features:
        numeric_pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]
        )
        transformers.append(("numeric", numeric_pipeline, numeric_features))

    if categorical_features:
        categorical_pipeline = Pipeline(
            steps=[
                (
                    "imputer",
                    SimpleImputer(strategy="most_frequent"),
                ),
                ("encoder", _make_one_hot_encoder()),
            ]
        )
        transformers.append(
            ("categorical", categorical_pipeline, categorical_features)
        )

    if not transformers:
        raise ValueError("训练数据中没有可用特征。")

    return (
        ColumnTransformer(transformers=transformers, remainder="drop"),
        numeric_features,
        categorical_features,
    )


def _model_grids() -> dict[str, tuple[object, dict[str, list[object]]]]:
    return {
        "逻辑回归": (
            LogisticRegression(
                max_iter=3000,
                class_weight="balanced",
                random_state=RANDOM_STATE,
            ),
            {"model__C": [0.1, 1.0, 10.0]},
        ),
        "随机森林": (
            RandomForestClassifier(
                n_estimators=300,
                class_weight="balanced_subsample",
                random_state=RANDOM_STATE,
                n_jobs=1,
            ),
            {
                "model__max_depth": [None, 10],
                "model__min_samples_leaf": [1, 2, 4],
                "model__max_features": ["sqrt", 0.5],
            },
        ),
        "极端随机树": (
            ExtraTreesClassifier(
                n_estimators=300,
                class_weight="balanced",
                random_state=RANDOM_STATE,
                n_jobs=1,
            ),
            {
                "model__max_depth": [None, 10],
                "model__min_samples_leaf": [1, 2, 4],
                "model__max_features": ["sqrt", 0.5],
            },
        ),
    }


def _create_feature_schema(
    features: pd.DataFrame,
    numeric_features: list[str],
    categorical_features: list[str],
) -> list[dict[str, Any]]:
    schema: list[dict[str, Any]] = []

    for column in features.columns:
        if column in numeric_features:
            values = pd.to_numeric(features[column], errors="coerce").dropna()
            schema.append(
                {
                    "name": column,
                    "type": "numeric",
                    "required": False,
                    "min": float(values.min()) if not values.empty else None,
                    "max": float(values.max()) if not values.empty else None,
                    "median": (
                        float(values.median()) if not values.empty else None
                    ),
                }
            )
        elif column in categorical_features:
            schema.append(
                {
                    "name": column,
                    "type": "categorical",
                    "required": False,
                    "allowed_values": sorted(
                        features[column]
                        .dropna()
                        .astype(str)
                        .unique()
                        .tolist()
                    ),
                }
            )

    return schema


def _validate_dataset(
    features: pd.DataFrame,
    target: pd.Series,
    class_labels: list[str],
) -> None:
    sample_count = len(target)

    if sample_count < settings.auto_training_minimum_sample_count:
        raise ValueError(
            "有效标注数量不足："
            f"当前 {sample_count} 条，"
            "至少需要 "
            f"{settings.auto_training_minimum_sample_count} 条。"
        )

    unknown_labels = sorted(set(target.astype(str)) - set(class_labels))
    if unknown_labels:
        raise ValueError(f"发现模型不认识的诊断类别：{unknown_labels}")

    counts = Counter(target.astype(str).tolist())
    insufficient = {
        label: counts.get(label, 0)
        for label in class_labels
        if counts.get(label, 0)
        < settings.auto_training_minimum_samples_per_class
    }

    if insufficient:
        raise ValueError(
            "以下类别样本不足："
            f"{insufficient}；每类至少需要 "
            f"{settings.auto_training_minimum_samples_per_class} 条。"
        )

    if features.empty:
        raise ValueError("训练特征为空。")


def _train_candidate(
    features: pd.DataFrame,
    target: pd.Series,
    class_labels: list[str],
) -> tuple[dict[str, Any], dict[str, float], str]:
    features = features.replace([np.inf, -np.inf], np.nan).copy()
    target = target.astype(str).copy()

    constant_columns = [
        column
        for column in features.columns
        if features[column].nunique(dropna=False) <= 1
    ]
    if constant_columns:
        features = features.drop(columns=constant_columns)

    if features.empty:
        raise ValueError("删除常量字段后没有可用于训练的特征。")

    preprocessor, numeric_features, categorical_features = (
        _build_preprocessor(features)
    )

    X_train, X_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=TEST_SIZE,
        stratify=target,
        random_state=RANDOM_STATE,
    )

    minimum_train_class_count = int(y_train.value_counts().min())
    cv_splits = min(3, minimum_train_class_count)
    if cv_splits < 2:
        raise ValueError("训练集中某类别样本不足，无法进行分层交叉验证。")

    cross_validation = StratifiedKFold(
        n_splits=cv_splits,
        shuffle=True,
        random_state=RANDOM_STATE,
    )

    best_name = ""
    best_search: GridSearchCV | None = None
    best_score = float("-inf")

    for model_name, (estimator, parameter_grid) in _model_grids().items():
        pipeline = Pipeline(
            steps=[
                ("preprocessor", clone(preprocessor)),
                ("model", estimator),
            ]
        )

        search = GridSearchCV(
            estimator=pipeline,
            param_grid=parameter_grid,
            scoring="f1_macro",
            cv=cross_validation,
            n_jobs=-1,
            refit=True,
            error_score="raise",
        )
        search.fit(X_train, y_train)

        if float(search.best_score_) > best_score:
            best_score = float(search.best_score_)
            best_name = model_name
            best_search = search

    if best_search is None:
        raise RuntimeError("没有训练出可用候选模型。")

    best_estimator = best_search.best_estimator_
    predicted_labels = best_estimator.predict(X_test)
    predicted_probabilities = best_estimator.predict_proba(X_test)
    model_classes = [str(item) for item in best_estimator.classes_.tolist()]

    metrics = {
        "macro_f1": float(
            f1_score(y_test, predicted_labels, average="macro")
        ),
        "balanced_accuracy": float(
            balanced_accuracy_score(y_test, predicted_labels)
        ),
        "log_loss": float(
            log_loss(y_test, predicted_probabilities, labels=model_classes)
        ),
    }

    final_model = clone(best_estimator)
    final_model.fit(features, target)

    package = {
        "package_version": datetime.now().strftime("%Y.%m.%d.%H%M%S"),
        "model": final_model,
        "feature_columns": features.columns.tolist(),
        "feature_schema": _create_feature_schema(
            features,
            numeric_features,
            categorical_features,
        ),
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        "class_labels": class_labels,
        "model_classes": [str(item) for item in final_model.classes_.tolist()],
        "excluded_columns": constant_columns,
        "best_model_name": best_name,
        "best_params": best_search.best_params_,
        "test_metrics": metrics,
        "python_version": __import__("sys").version,
        "sklearn_version": sklearn.__version__,
        "joblib_version": joblib.__version__,
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "sample_count": int(len(features)),
        "data_source": "confirmed_doctor_annotations",
    }

    return package, metrics, best_name


def _verify_candidate(
    path: Path,
    sample_features: pd.DataFrame,
) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size <= 0:
        raise RuntimeError("候选模型文件不存在或为空。")

    package = joblib.load(path)
    required_keys = {
        "model",
        "feature_columns",
        "class_labels",
        "best_model_name",
        "test_metrics",
        "created_at",
    }
    missing = required_keys - set(package)
    if missing:
        raise RuntimeError(f"候选模型包缺少字段：{sorted(missing)}")

    model = package["model"]
    sample = sample_features.reindex(
        columns=list(package["feature_columns"])
    ).head(1)
    if sample.empty:
        raise RuntimeError("没有候选模型验证样本。")

    prediction = model.predict(sample)
    probabilities = model.predict_proba(sample)
    if len(prediction) != 1 or probabilities.shape[0] != 1:
        raise RuntimeError("候选模型预测验证失败。")
    if not np.all(np.isfinite(probabilities)):
        raise RuntimeError("候选模型概率包含无效数值。")

    return package


def execute_training_job(job_id: int) -> None:
    """
    执行一个 queued 训练任务。

    该函数供 FastAPI BackgroundTasks 调用，因此内部必须创建独立数据库会话。
    第一版只生成 candidate，不替换正式模型。
    """

    annotation_ids: list[int] = []

    try:
        with Session(engine) as db:
            job = db.get(TrainingJob, job_id)
            if job is None or job.status != "queued":
                return

            job.status = "running"
            job.started_at = _utc_now()
            job.message = "正在读取医生确认标注并训练候选模型"
            db.commit()

            if model_service.package is None:
                model_service.load()

            feature_columns = list(model_service.feature_columns)
            current_package = model_service.package or {}
            class_labels = [
                str(item)
                for item in current_package.get(
                    "class_labels",
                    ["其他", "炎症", "感染", "肿瘤"],
                )
            ]

            dataset = build_training_dataset(db, feature_columns)
            annotation_ids = dataset.annotation_ids

            _validate_dataset(dataset.features, dataset.target, class_labels)

            package, metrics, best_model_name = _train_candidate(
                dataset.features,
                dataset.target,
                class_labels,
            )

            version = (
                "candidate-"
                + datetime.now().strftime("%Y%m%d-%H%M%S")
            )
            settings.model_versions_dir.mkdir(parents=True, exist_ok=True)
            candidate_path = settings.model_versions_dir / f"{version}.joblib"

            temporary_path = candidate_path.with_suffix(".tmp.joblib")
            if temporary_path.exists():
                temporary_path.unlink()

            joblib.dump(package, temporary_path, compress=3)
            _verify_candidate(temporary_path, dataset.features)
            temporary_path.replace(candidate_path)

            parent_version = None
            if current_package:
                parent_version = str(
                    current_package.get("package_version", "unknown")
                )

            model_version = ModelVersion(
                version=version,
                model_name=best_model_name,
                file_path=str(candidate_path),
                status="candidate",
                sample_count=len(dataset.target),
                macro_f1=metrics["macro_f1"],
                balanced_accuracy=metrics["balanced_accuracy"],
                log_loss=metrics["log_loss"],
                parent_version=parent_version,
            )
            db.add(model_version)

            annotations = db.scalars(
                select(Annotation).where(Annotation.id.in_(annotation_ids))
            ).all()
            for annotation in annotations:
                annotation.training_status = "included"
                annotation.trained_model_version = version

            job.status = "succeeded"
            job.candidate_version = version
            job.finished_at = _utc_now()
            job.message = (
                "候选模型训练完成；"
                f"模型={best_model_name}，"
                f"样本数={len(dataset.target)}，"
                f"Macro-F1={metrics['macro_f1']:.4f}"
            )
            db.commit()

    except ValueError as exc:
        with Session(engine) as db:
            job = db.get(TrainingJob, job_id)
            if job is not None:
                job.status = "rejected"
                job.finished_at = _utc_now()
                job.message = str(exc)[:1000]
                db.commit()

    except Exception as exc:
        with Session(engine) as db:
            job = db.get(TrainingJob, job_id)
            if job is not None:
                job.status = "failed"
                job.finished_at = _utc_now()
                job.message = f"训练失败：{type(exc).__name__}: {exc}"[:1000]
                db.commit()
        raise
