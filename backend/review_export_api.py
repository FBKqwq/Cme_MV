from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse

from build_untouched_physician_review_doc import build_document


app = FastAPI(
    title="医师复验PDF导出接口"
)


@app.get("/api/export-review-doc")
def export_review_doc():

    # 调用你已有的生成程序
    file_path = build_document()

    file_path = Path(file_path)

    return {
        "success": True,
        "message": "医师复验清单生成成功",
        "file_name": file_path.name,
        "download_url": f"/api/download-review-doc"
    }


@app.get("/api/download-review-doc")
def download_review_doc():

    file_path = build_document()

    return FileResponse(
        path=file_path,
        filename=Path(file_path).name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )