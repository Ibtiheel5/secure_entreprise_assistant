"""Wrapper MLflow (import tardif). Le Model Registry n'existe que si le backend MLflow est une base SQL
(sqlite/postgres) ; avec un file store, l'enregistrement est ignoré et signalé, pas simulé."""
import time
from contextlib import contextmanager


@contextmanager
def tracked_run(experiment: str, run_name: str, params: dict):
    import mlflow
    mlflow.set_experiment(experiment)
    with mlflow.start_run(run_name=run_name) as run:
        mlflow.log_params({k: str(v)[:250] for k, v in params.items()})
        t0 = time.time()
        yield run
        mlflow.log_metric("duration_s", time.time() - t0)


def log_metrics(metrics: dict, step: int | None = None):
    import mlflow
    mlflow.log_metrics({k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))}, step=step)


def log_model_dir(path: str, registered_name: str | None = None) -> str | None:
    import mlflow
    mlflow.log_artifacts(path, artifact_path="model")
    if not registered_name:
        return None
    try:
        v = mlflow.register_model(f"runs:/{mlflow.active_run().info.run_id}/model", registered_name)
        return str(v.version)
    except Exception as exc:  # backend sans registry
        print(f"[mlflow] model registry unavailable ({type(exc).__name__}); artifacts logged only")
        return None
