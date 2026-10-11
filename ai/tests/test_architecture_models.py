import pytest

from agents.architecture.models import (
    ArchitectureComponent,
    ArchitectureProposal,
)


def test_architecture_component_accepts_valid_data():
    component = ArchitectureComponent(
        name="API",
        responsibility="Expose application endpoints",
        technology="FastAPI",
    )

    assert component.name == "API"
    assert component.responsibility == "Expose application endpoints"
    assert component.technology == "FastAPI"


@pytest.mark.parametrize("name", ["", "   "])
def test_architecture_component_rejects_empty_name(name):
    with pytest.raises(ValueError, match="Component name"):
        ArchitectureComponent(
            name=name,
            responsibility="Expose application endpoints",
        )


@pytest.mark.parametrize("responsibility", ["", "   "])
def test_architecture_component_rejects_empty_responsibility(
    responsibility,
):
    with pytest.raises(ValueError, match="Component responsibility"):
        ArchitectureComponent(
            name="API",
            responsibility=responsibility,
        )


def test_architecture_proposal_accepts_valid_data():
    component = ArchitectureComponent(
        name="API",
        responsibility="Expose application endpoints",
    )
    proposal = ArchitectureProposal(
        project_name="CloudPilot",
        summary="A cloud deployment platform",
        components=(component,),
        interactions=("Client sends a request to the API",),
        deployment_requirements=("Python 3.12",),
        assumptions=("The application exposes an HTTP interface",),
        open_questions=("Which cloud provider will be used?",),
    )

    assert proposal.project_name == "CloudPilot"
    assert proposal.components == (component,)
    assert proposal.open_questions == ("Which cloud provider will be used?",)


@pytest.mark.parametrize(
    ("project_name", "summary", "message"),
    [
        ("", "A valid summary", "Project name"),
        ("CloudPilot", "", "Architecture summary"),
        ("   ", "A valid summary", "Project name"),
        ("CloudPilot", "   ", "Architecture summary"),
    ],
)
def test_architecture_proposal_rejects_empty_required_fields(
    project_name,
    summary,
    message,
):
    with pytest.raises(ValueError, match=message):
        ArchitectureProposal(
            project_name=project_name,
            summary=summary,
        )


def test_architecture_proposal_defaults_to_empty_collections():
    proposal = ArchitectureProposal(
        project_name="CloudPilot",
        summary="A cloud deployment platform",
    )

    assert proposal.components == ()
    assert proposal.interactions == ()
    assert proposal.deployment_requirements == ()
    assert proposal.assumptions == ()
    assert proposal.open_questions == ()


def test_architecture_proposal_is_immutable():
    proposal = ArchitectureProposal(
        project_name="CloudPilot",
        summary="A cloud deployment platform",
    )

    with pytest.raises(AttributeError):
        proposal.project_name = "Changed"
