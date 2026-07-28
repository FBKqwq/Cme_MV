from collections import Counter
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database import Base, engine, get_db
from app.model_service import model_service
from app.models import (
    Annotation,
    PatientCase,
    Prediction,
)
from app.schemas import (
    AnnotationCreate,
    AnnotationResponse,
    BatchPredictionRequest,
    BatchPredictionResponse,
    BatchPredictionResultItem,
    CaseCreate,
    CaseDetailResponse,
    CaseHistoryItem,
    CasePredictionResponse,
    CaseResponse,
    PredictionResponse,
)
from app.training_executor import execute_training_job
from app.training_service import (
    create_training_job_if_needed,
)
from app.review.router import (
    load_repository as load_review_repository,
    router as review_router,
)


settings = get_settings()

DBSession = Annotated[
    Session,
    Depends(get_db),
]


def get_current_model_version() -> str:
    """
    从当前模型包中生成模型版本名称。
    """

    if model_service.package is None:
        return "diagnosis-model-unknown"

    model_name = str(
        model_service.package.get(
            "best_model_name",
            "diagnosis-model",
        )
    )

    package_version = str(
        model_service.package.get(
            "package_version",
            "unknown",
        )
    )

    return (
        f"{model_name}-v{package_version}"
    )[:50]


@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    FastAPI 应用生命周期。
    """

    # 只创建不存在的表。
    # 已有数据库字段修改仍然使用 Alembic。
    Base.metadata.create_all(
        bind=engine,
    )

    # 应用启动时加载当前正式模型。
    model_service.load()

    print(
        "真实诊断模型加载成功，"
        f"输入字段数："
        f"{len(model_service.feature_columns)}"
    )

    # 复验数据可由人工维护；缺失时仅将复验模块标记为 degraded。
    load_review_repository(settings.review_data_root)

    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="医院病人诊断辅助预测系统后端接口",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(review_router)


@app.get("/")
def root() -> dict[str, str]:
    """
    根路径。
    """

    return {
        "status": "ok",
        "message": "医院诊断辅助预测系统后端正在运行",
        "docs": "/docs",
    }


@app.get("/api/model/info")
def get_model_info() -> dict:
    """
    返回当前正式模型的信息。
    """

    return model_service.get_info()


@app.post(
    "/api/cases/predict",
    response_model=CasePredictionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_case_and_real_prediction(
    payload: CaseCreate,
    db: DBSession,
) -> CasePredictionResponse:
    """
    保存病例并调用真实机器学习模型预测。
    """

    existing_case = db.scalar(
        select(PatientCase).where(
            PatientCase.case_code
            == payload.case_code
        )
    )

    if existing_case is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该病例编号已经存在。",
        )

    feature_values = dict(
        payload.features
    )

    standard_feature_values = {
        "年龄": payload.age,
        "性别": payload.gender,
        "发烧时长": payload.fever_duration,
        "最高体温": payload.max_temperature,
    }

    for (
        feature_name,
        feature_value,
    ) in standard_feature_values.items():
        if (
            feature_name
            in model_service.feature_columns
        ):
            feature_values[
                feature_name
            ] = feature_value

    try:
        prediction_result = (
            model_service.predict(
                feature_values
            )
        )

    except Exception as exc:
        print(
            "真实模型预测失败：",
            repr(exc),
        )

        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "真实模型预测失败，"
                "请检查病例字段的取值和格式。"
            ),
        ) from exc

    case_record = PatientCase(
        case_code=payload.case_code,
        age=payload.age,
        gender=payload.gender,
        fever_duration=(
            payload.fever_duration
        ),
        max_temperature=(
            payload.max_temperature
        ),
        features=feature_values,
    )

    db.add(case_record)

    try:
        db.flush()

        model_version = (
            get_current_model_version()
        )

        probabilities = {
            str(label): float(value)
            for label, value
            in prediction_result[
                "probabilities"
            ].items()
        }

        prediction_record = Prediction(
            case_id=case_record.id,
            predicted_label=str(
                prediction_result[
                    "predicted_label"
                ]
            ),
            probabilities=probabilities,
            model_version=model_version,
        )

        db.add(prediction_record)
        db.commit()

        db.refresh(case_record)
        db.refresh(prediction_record)

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail="预测完成，但数据库保存失败。",
        ) from exc

    return CasePredictionResponse(
        case=CaseResponse.model_validate(
            case_record
        ),
        prediction=(
            PredictionResponse.model_validate(
                prediction_record
            )
        ),
    )


@app.get(
    "/api/case-history",
    response_model=list[CaseHistoryItem],
)
def list_case_history(
    db: DBSession,
) -> list[CaseHistoryItem]:
    """
    返回病例历史记录。
    """

    case_records = db.scalars(
        select(PatientCase)
        .options(
            selectinload(
                PatientCase.predictions
            ),
            selectinload(
                PatientCase.annotations
            ),
        )
        .order_by(
            PatientCase.id.desc()
        )
    ).all()

    history_items: list[
        CaseHistoryItem
    ] = []

    for case_record in case_records:
        latest_prediction = max(
            case_record.predictions,
            key=lambda item: item.id,
            default=None,
        )

        latest_annotation = max(
            case_record.annotations,
            key=lambda item: item.id,
            default=None,
        )

        history_items.append(
            CaseHistoryItem(
                case=(
                    CaseResponse.model_validate(
                        case_record
                    )
                ),
                prediction=(
                    PredictionResponse.model_validate(
                        latest_prediction
                    )
                    if latest_prediction is not None
                    else None
                ),
                annotation=(
                    AnnotationResponse.model_validate(
                        latest_annotation
                    )
                    if latest_annotation is not None
                    else None
                ),
            )
        )

    return history_items


@app.get("/api/health")
def health_check() -> dict[str, str]:
    """
    检查 FastAPI 服务。
    """

    return {
        "status": "ok",
        "message": "FastAPI 后端运行正常",
        "version": settings.app_version,
    }


@app.get("/api/db-health")
def database_health_check() -> dict[str, str]:
    """
    检查 PostgreSQL 数据库连接。
    """

    try:
        with engine.connect() as connection:
            database = connection.scalar(
                text(
                    "SELECT current_database()"
                )
            )

            user = connection.scalar(
                text(
                    "SELECT current_user"
                )
            )

            version = connection.scalar(
                text(
                    "SHOW server_version"
                )
            )

        return {
            "status": "ok",
            "message": (
                "PostgreSQL 数据库连接正常"
            ),
            "database": str(database),
            "user": str(user),
            "postgresql_version": str(version),
        }

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "数据库连接失败，"
                "请检查 .env 配置。"
            ),
        ) from exc


@app.get(
    "/api/cases",
    response_model=list[CaseResponse],
)
def list_cases(
    db: DBSession,
) -> list[PatientCase]:
    """
    返回全部病例。
    """

    result = db.scalars(
        select(PatientCase).order_by(
            PatientCase.id.desc()
        )
    )

    return list(
        result.all()
    )


@app.post(
    "/api/cases/batch-predict",
    response_model=BatchPredictionResponse,
    status_code=status.HTTP_201_CREATED,
)
def batch_predict_cases(
    payload: BatchPredictionRequest,
    db: DBSession,
) -> BatchPredictionResponse:
    """
    批量保存病例并执行预测。

    任意一条失败时，整批数据回滚。
    """

    case_codes = [
        row.case_code.strip()
        for row in payload.rows
    ]

    case_code_counts = Counter(
        case_codes
    )

    duplicate_case_codes = sorted(
        case_code
        for case_code, count
        in case_code_counts.items()
        if count > 1
    )

    if duplicate_case_codes:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "本次导入存在重复病例编号："
                + "、".join(
                    duplicate_case_codes
                )
            ),
        )

    existing_case_codes = list(
        db.scalars(
            select(
                PatientCase.case_code
            ).where(
                PatientCase.case_code.in_(
                    case_codes
                )
            )
        ).all()
    )

    if existing_case_codes:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "数据库中已经存在以下病例编号："
                + "、".join(
                    sorted(
                        existing_case_codes
                    )
                )
            ),
        )

    model_version = (
        get_current_model_version()
    )

    allowed_feature_names = set(
        model_service.feature_columns
    )

    result_items: list[
        BatchPredictionResultItem
    ] = []

    try:
        for row in payload.rows:
            feature_values: dict[
                str,
                object,
            ] = {}

            for (
                feature_name,
                feature_value,
            ) in row.features.items():
                if (
                    feature_name
                    not in allowed_feature_names
                ):
                    continue

                if (
                    feature_value is None
                    or feature_value == ""
                ):
                    continue

                feature_values[
                    feature_name
                ] = feature_value

            base_feature_values = {
                "年龄": row.age,
                "性别": row.gender,
                "发烧时长": (
                    row.fever_duration
                ),
                "最高体温": (
                    row.max_temperature
                ),
            }

            for (
                feature_name,
                feature_value,
            ) in base_feature_values.items():
                if (
                    feature_name
                    in allowed_feature_names
                ):
                    feature_values[
                        feature_name
                    ] = feature_value

            try:
                prediction_result = (
                    model_service.predict(
                        feature_values
                    )
                )

            except Exception as exc:
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail=(
                        f"Excel 第 {row.excel_row} 行"
                        "模型预测失败："
                        f"{str(exc)}"
                    ),
                ) from exc

            case_record = PatientCase(
                case_code=(
                    row.case_code.strip()
                ),
                age=row.age,
                gender=row.gender,
                fever_duration=(
                    row.fever_duration
                ),
                max_temperature=(
                    row.max_temperature
                ),
                features=feature_values,
            )

            db.add(case_record)
            db.flush()

            probabilities = {
                str(label): float(value)
                for label, value
                in prediction_result[
                    "probabilities"
                ].items()
            }

            prediction_record = Prediction(
                case_id=case_record.id,
                predicted_label=str(
                    prediction_result[
                        "predicted_label"
                    ]
                ),
                probabilities=probabilities,
                model_version=model_version,
            )

            db.add(prediction_record)
            db.flush()

            result_items.append(
                BatchPredictionResultItem(
                    excel_row=row.excel_row,
                    case_id=case_record.id,
                    case_code=(
                        case_record.case_code
                    ),
                    predicted_label=(
                        prediction_record
                        .predicted_label
                    ),
                    probabilities=(
                        probabilities
                    ),
                )
            )

        db.commit()

    except HTTPException:
        db.rollback()
        raise

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "批量预测已经终止，"
                "所有数据均未保存。"
            ),
        ) from exc

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail=(
                "批量预测发生未知错误，"
                "所有数据均未保存。"
            ),
        ) from exc

    return BatchPredictionResponse(
        total=len(
            payload.rows
        ),
        success_count=len(
            result_items
        ),
        model_version=model_version,
        results=result_items,
    )


@app.get(
    "/api/cases/{case_id}",
    response_model=CaseDetailResponse,
)
def get_case(
    case_id: int,
    db: DBSession,
) -> CaseDetailResponse:
    """
    返回病例、最近预测和最近医生标注。
    """

    case_record = db.scalar(
        select(PatientCase)
        .options(
            selectinload(
                PatientCase.predictions
            ),
            selectinload(
                PatientCase.annotations
            ),
        )
        .where(
            PatientCase.id == case_id
        )
    )

    if case_record is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="病例不存在。",
        )

    latest_prediction = max(
        case_record.predictions,
        key=lambda item: item.id,
        default=None,
    )

    latest_annotation = max(
        case_record.annotations,
        key=lambda item: item.id,
        default=None,
    )

    return CaseDetailResponse(
        case=CaseResponse.model_validate(
            case_record
        ),
        prediction=(
            PredictionResponse.model_validate(
                latest_prediction
            )
            if latest_prediction is not None
            else None
        ),
        annotation=(
            AnnotationResponse.model_validate(
                latest_annotation
            )
            if latest_annotation is not None
            else None
        ),
    )


@app.post(
    "/api/cases/{case_id}/annotations",
    response_model=AnnotationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_annotation(
    case_id: int,
    payload: AnnotationCreate,
    background_tasks: BackgroundTasks,
    db: DBSession,
) -> Annotation:
    """
    保存医生确认的真实诊断。

    新标注进入 pending 状态。
    pending 数量达到阈值时创建训练任务，
    并在接口返回后执行后台训练。
    """

    case_record = db.get(
        PatientCase,
        case_id,
    )

    if case_record is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail="病例不存在。",
        )

    annotation_record = Annotation(
        case_id=case_id,
        true_label=payload.true_label,
        doctor_name=payload.doctor_name,
        remark=payload.remark,
        status="已确认",
        training_status="pending",
    )

    try:
        db.add(annotation_record)
        db.commit()
        db.refresh(annotation_record)

    except SQLAlchemyError as exc:
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
            detail="医生标注保存失败。",
        ) from exc

    try:
        training_job = (
            create_training_job_if_needed(
                db
            )
        )

    except SQLAlchemyError as exc:
        db.rollback()

        print(
            "检查自动训练任务失败：",
            repr(exc),
        )

        # 标注已经保存成功。
        # 训练任务创建失败不应该让医生标注接口返回失败。
        return annotation_record

    if training_job is not None:
        print(
            f"已创建训练任务，"
            f"job_id={training_job.id}，"
            "准备在后台执行。"
        )

        background_tasks.add_task(
            execute_training_job,
            training_job.id,
        )

    return annotation_record
