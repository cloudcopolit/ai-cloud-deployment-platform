import pytest

from workflows.contracts import AgentResult, TaskState, TaskStatus


def test_task_state_defaults_to_pending():
    task = TaskState(task_id="task-001", input_data={"path": "app.py"})

    assert task.status == TaskStatus.PENDING
    assert task.input_data == {"path": "app.py"}
    assert task.output_data == {}
    assert task.error is None


def test_task_state_rejects_empty_id():
    with pytest.raises(ValueError, match="task_id"):
        TaskState(task_id=" ")


def test_successful_agent_result():
    result = AgentResult(
        agent_name="code_analyzer",
        success=True,
        output={"files_analyzed": 2},
    )

    assert result.success
    assert result.output["files_analyzed"] == 2
    assert result.error is None


def test_failed_agent_result_requires_error():
    with pytest.raises(ValueError, match="must include an error"):
        AgentResult(agent_name="code_analyzer", success=False)


def test_successful_result_cannot_contain_error():
    with pytest.raises(ValueError, match="cannot contain an error"):
        AgentResult(
            agent_name="code_analyzer",
            success=True,
            error="Unexpected error",
        )
