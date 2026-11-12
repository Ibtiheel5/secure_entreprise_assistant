from sqlalchemy.orm import Session

from app.database.models import ModelExperiment


def register_experiment(db: Session, *, model_name: str, version: str, params: dict, metrics: dict,
                        mlflow_run_id: str | None = None) -> ModelExperiment:
    exp = ModelExperiment(model_name=model_name, version=version, params=params, metrics=metrics,
                          mlflow_run_id=mlflow_run_id, is_deployed=False)
    db.add(exp)
    db.commit()
    return exp
