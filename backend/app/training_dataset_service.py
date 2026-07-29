from dataclasses import dataclass

import pandas as pd

from app.file_repository import FileRepository, file_repository


@dataclass
class TrainingDataset:
    features: pd.DataFrame
    target: pd.Series
    annotation_ids: list[int]


def build_training_dataset(
    feature_columns: list[str],
    repository: FileRepository = file_repository,
) -> TrainingDataset:
    feature_rows: list[dict[str, object]] = []
    labels: list[str] = []
    annotation_ids: list[int] = []

    for annotation, case in repository.confirmed_annotation_pairs():
        values = dict(case.features or {})
        feature_rows.append(
            {column: values.get(column) for column in feature_columns}
        )
        labels.append(annotation.true_label)
        annotation_ids.append(annotation.id)

    return TrainingDataset(
        features=pd.DataFrame(feature_rows, columns=feature_columns),
        target=pd.Series(labels, name="诊断结果"),
        annotation_ids=annotation_ids,
    )
