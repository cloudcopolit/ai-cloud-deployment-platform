from AI.domain.questions.models import Choice, Question

QUESTION_BANK: dict[str, Question] = {
    q.id: q
    for q in (
        Question(
            id="target_environment",
            text="Which environment is this analysis for?",
            choices=(
                Choice("dev", "Development"),
                Choice("staging", "Staging"),
                Choice("prod", "Production"),
            ),
        ),
        Question(
            id="aws_region",
            text="Which AWS region should we assume for this project?",
            choices=(
                Choice("us-east-1", "US East (N. Virginia)"),
                Choice("eu-west-1", "Europe (Ireland)"),
                Choice("me-south-1", "Middle East (Bahrain)"),
                Choice("unknown", "Not decided yet"),
            ),
        ),
        Question(
            id="deployment_status",
            text="Is this code already deployed to AWS?",
            choices=(
                Choice("yes", "Yes"),
                Choice("no", "No"),
                Choice("partial", "Partly"),
            ),
        ),
    )
}