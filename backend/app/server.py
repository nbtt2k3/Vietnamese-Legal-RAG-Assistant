from app.factory import create_app
from app.services.health_service import check_pipeline_dependencies


def _check_pipeline_dependencies(pipeline) -> dict:
    return check_pipeline_dependencies(pipeline)


app = create_app()
