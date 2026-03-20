import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import select

from app.core.deps import DbDep, ResearcherDep
from app.core.s3 import generate_presigned_url
from app.models.dataset import Dataset, DatasetExport
from app.schemas.dataset import DatasetCreate, DatasetResponse, ExportResponse
from app.services.export import run_export

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("", response_model=list[DatasetResponse])
async def list_datasets(db: DbDep, researcher: ResearcherDep):
    result = await db.execute(select(Dataset).order_by(Dataset.created_at.desc()))
    return [
        DatasetResponse(
            id=str(d.id), name=d.name, description=d.description,
            filter_config=d.filter_config, created_by=str(d.created_by), created_at=d.created_at,
        )
        for d in result.scalars().all()
    ]


@router.post("", response_model=DatasetResponse, status_code=201)
async def create_dataset(payload: DatasetCreate, db: DbDep, researcher: ResearcherDep):
    dataset = Dataset(
        name=payload.name,
        description=payload.description,
        filter_config=payload.filter_config,
        created_by=researcher.id,
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return DatasetResponse(
        id=str(dataset.id), name=dataset.name, description=dataset.description,
        filter_config=dataset.filter_config, created_by=str(dataset.created_by), created_at=dataset.created_at,
    )


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(dataset_id: uuid.UUID, db: DbDep, researcher: ResearcherDep):
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return DatasetResponse(
        id=str(dataset.id), name=dataset.name, description=dataset.description,
        filter_config=dataset.filter_config, created_by=str(dataset.created_by), created_at=dataset.created_at,
    )


@router.post("/{dataset_id}/export", response_model=ExportResponse, status_code=202)
async def trigger_export(
    dataset_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DbDep,
    researcher: ResearcherDep,
):
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    export = DatasetExport(dataset_id=dataset_id, format="jsonl", status="pending")
    db.add(export)
    await db.commit()
    await db.refresh(export)

    background_tasks.add_task(run_export, export.id)

    return ExportResponse(
        id=str(export.id), dataset_id=str(export.dataset_id), format=export.format,
        status=export.status, s3_key=export.s3_key, row_count=export.row_count,
        error_message=export.error_message, created_at=export.created_at,
        completed_at=export.completed_at, download_url=None,
    )


@router.get("/{dataset_id}/exports", response_model=list[ExportResponse])
async def list_exports(dataset_id: uuid.UUID, db: DbDep, researcher: ResearcherDep):
    result = await db.execute(
        select(DatasetExport)
        .where(DatasetExport.dataset_id == dataset_id)
        .order_by(DatasetExport.created_at.desc())
    )
    exports = result.scalars().all()

    return [
        ExportResponse(
            id=str(e.id), dataset_id=str(e.dataset_id), format=e.format,
            status=e.status, s3_key=e.s3_key, row_count=e.row_count,
            error_message=e.error_message, created_at=e.created_at,
            completed_at=e.completed_at,
            download_url=generate_presigned_url(e.s3_key) if e.s3_key and e.status == "done" else None,
        )
        for e in exports
    ]
