from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


DiagnosisLabel = Literal[
    "其他",
    "炎症",
    "感染",
    "肿瘤",
]

Gender = Literal["男", "女"]

TrainingStatus = Literal[
    "pending",
    "included",
    "rejected",
]


class CaseCreate(BaseModel):
    """创建病例并进行预测的请求。"""

    case_code: str = Field(
        min_length=1,
        max_length=64,
    )

    age: int = Field(
        ge=0,
        le=120,
    )

    gender: Gender

    fever_duration: float = Field(
        ge=0,
        le=365,
    )

    max_temperature: float = Field(
        ge=34,
        le=43,
    )

    features: dict[str, Any] = Field(
        default_factory=dict,
    )


class CaseResponse(BaseModel):
    """病例响应。"""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    case_code: str
    age: int
    gender: str
    fever_duration: float
    max_temperature: float
    features: dict[str, Any]
    created_at: datetime


class PredictionResponse(BaseModel):
    """模型预测响应。"""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    case_id: int
    predicted_label: str
    probabilities: dict[str, float]
    model_version: str
    created_at: datetime


class CasePredictionResponse(BaseModel):
    """创建病例并预测后的完整响应。"""

    case: CaseResponse
    prediction: PredictionResponse


class AnnotationCreate(BaseModel):
    """医生提交真实诊断标注。"""

    true_label: DiagnosisLabel

    doctor_name: str = Field(
        min_length=1,
        max_length=100,
    )

    remark: str | None = Field(
        default=None,
        max_length=500,
    )


class AnnotationResponse(BaseModel):
    """医生标注响应。"""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    case_id: int
    true_label: str
    doctor_name: str
    status: str
    remark: str | None

    training_status: str
    trained_model_version: str | None = None
    validated_by: str | None = None
    validated_at: datetime | None = None

    created_at: datetime


class CaseHistoryItem(BaseModel):
    """病例历史记录。"""

    case: CaseResponse
    prediction: PredictionResponse | None = None
    annotation: AnnotationResponse | None = None


class CaseDetailResponse(BaseModel):
    """病例详情响应。"""

    case: CaseResponse

    prediction: PredictionResponse | None = None

    annotation: AnnotationResponse | None = None


class BatchCaseItem(BaseModel):
    """Excel 中的一行病例数据。"""

    excel_row: int = Field(
        ge=2,
    )

    case_code: str = Field(
        min_length=1,
        max_length=64,
    )

    age: int = Field(
        ge=0,
        le=120,
    )

    gender: Gender

    fever_duration: float = Field(
        ge=0,
    )

    max_temperature: float = Field(
        ge=34,
        le=43,
    )

    features: dict[str, Any] = Field(
        default_factory=dict,
    )


class BatchPredictionRequest(BaseModel):
    """Excel 批量预测请求。"""

    rows: list[BatchCaseItem] = Field(
        min_length=1,
        max_length=500,
    )


class BatchPredictionResultItem(BaseModel):
    """一条病例的批量预测结果。"""

    excel_row: int
    case_id: int
    case_code: str
    predicted_label: str
    probabilities: dict[str, float]


class BatchPredictionResponse(BaseModel):
    """批量预测成功响应。"""

    total: int
    success_count: int
    model_version: str
    results: list[BatchPredictionResultItem]