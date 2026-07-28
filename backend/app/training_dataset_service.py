from dataclasses import dataclass

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Annotation, PatientCase


@dataclass
class TrainingDataset:
    features: pd.DataFrame
    target: pd.Series
    annotation_ids: list[int]


def build_training_dataset(
    db: Session,
    feature_columns: list[str],
) -> TrainingDataset:
    rows = db.execute(
        select(
            Annotation,
            PatientCase,
        )
        .join(
            PatientCase,
            PatientCase.id == Annotation.case_id,
        )
        .where(
            Annotation.status == "已确认",
        )
        .order_by(Annotation.id)
    ).all()

    feature_rows: list[dict[str, object]] = []
    labels: list[str] = []
    annotation_ids: list[int] = []

    for annotation, case in rows:
        values = dict(case.features or {})

        feature_rows.append(
            {
                column: values.get(column)
                for column in feature_columns
            }
        )

        labels.append(
            annotation.true_label
        )

        annotation_ids.append(
            annotation.id
        )

    return TrainingDataset(
        features=pd.DataFrame(
            feature_rows,
            columns=feature_columns,
        ),
        target=pd.Series(
            labels,
            name="诊断结果",
        ),
        annotation_ids=annotation_ids,
    )