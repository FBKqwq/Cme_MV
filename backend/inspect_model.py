from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn


MODEL_PATH = (
    Path(__file__).resolve().parent
    / "models"
    / "诊断结果四分类模型.joblib"
)


def print_attribute(
    obj: Any,
    attribute_name: str,
    indent: str = "",
) -> None:
    if hasattr(obj, attribute_name):
        value = getattr(obj, attribute_name)

        print(
            f"{indent}{attribute_name}: "
            f"{value}"
        )


def inspect_object(
    obj: Any,
    name: str = "model",
    indent: str = "",
) -> None:
    print(
        f"{indent}{name} 类型："
        f"{type(obj).__module__}."
        f"{type(obj).__name__}"
    )

    print_attribute(
        obj,
        "classes_",
        indent,
    )

    print_attribute(
        obj,
        "n_features_in_",
        indent,
    )

    print_attribute(
        obj,
        "feature_names_in_",
        indent,
    )

    print(
        f"{indent}支持 predict："
        f"{hasattr(obj, 'predict')}"
    )

    print(
        f"{indent}支持 predict_proba："
        f"{hasattr(obj, 'predict_proba')}"
    )

    if hasattr(obj, "named_steps"):
        print(f"{indent}Pipeline 步骤：")

        for step_name, step_object in (
            obj.named_steps.items()
        ):
            inspect_object(
                step_object,
                name=step_name,
                indent=indent + "  ",
            )

    if isinstance(obj, dict):
        print(
            f"{indent}字典键："
            f"{list(obj.keys())}"
        )

        for key, value in obj.items():
            print()
            inspect_object(
                value,
                name=str(key),
                indent=indent + "  ",
            )


def main() -> None:
    print("=" * 60)
    print("模型文件检查")
    print("=" * 60)

    print(f"模型路径：{MODEL_PATH}")
    print(f"文件是否存在：{MODEL_PATH.exists()}")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"没有找到模型文件：{MODEL_PATH}"
        )

    print()
    print("运行环境版本：")
    print(f"Python sklearn：{sklearn.__version__}")
    print(f"joblib：{joblib.__version__}")
    print(f"numpy：{np.__version__}")
    print(f"pandas：{pd.__version__}")

    print()
    print("正在加载模型……")

    model = joblib.load(MODEL_PATH)

    print("模型加载成功。")
    print()

    inspect_object(model)

    print()
    print("=" * 60)
    print("检查结束")
    print("=" * 60)


if __name__ == "__main__":
    main()