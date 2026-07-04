import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_job_service_uses_explicit_job_runner_boundary():
    source = (APP / "services" / "job_service.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    class_names = {
        node.name for node in tree.body if isinstance(node, ast.ClassDef)
    }
    assert "JobPhase" in class_names
    assert "JobStage" in class_names
    assert "JobRunner" in class_names
    assert "JobService" in class_names
    assert "JobRunner(job, cmd).start()" in source
    assert "JobPhase.RUNNING" in source
    assert "JobPhase.COMPLETED" in source
    assert "JobPhase.FAILED" in source
    assert "JobPhase.CANCELLED" in source
    assert "JobStage.QUEUED" in source
    assert "JobStage.STARTING" in source
    assert "JobStage.COMPLETE" in source
    assert "JobStage.FAILED" in source
    assert "JobStage.CANCELLED" in source
    assert "queue.SimpleQueue" in source
    assert "self.retry_queue.put" in source

    start_job = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "start_job"
    )
    nested_functions = [
        node.name
        for node in ast.walk(start_job)
        if isinstance(node, ast.FunctionDef) and node is not start_job
    ]

    assert "worker" not in nested_functions
