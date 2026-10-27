resource "aws_cloudwatch_log_group" "app" {
  name              = "/cloudpilot/${var.deployment_id}"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role" "execution" {
  name                 = "${var.name_prefix}-exec"
  path                 = "/cloudpilot/"
  permissions_boundary = var.permissions_boundary_arn
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "execution_secret" {
  name = "read-deployment-secret"
  role = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = aws_secretsmanager_secret.db.arn
    }]
  })
}

resource "aws_ecs_cluster" "this" {
  name = "${var.name_prefix}-cluster"
}

resource "aws_ecs_task_definition" "app" {
  family                   = "${var.name_prefix}-app"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.execution.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([{
    name         = "app"
    image        = var.image
    essential    = true
    portMappings = [{ containerPort = var.container_port, protocol = "tcp" }]
    environment = [for k, v in merge(var.environment, {
      PORT    = tostring(var.container_port)
      DB_HOST = aws_db_instance.this.address
      DB_PORT = tostring(aws_db_instance.this.port)
      DB_NAME = aws_db_instance.this.db_name
      DB_USER = aws_db_instance.this.username
    }) : { name = k, value = v }]
    secrets = [
      { name = "DATABASE_URL", valueFrom = "${aws_secretsmanager_secret.db.arn}:DATABASE_URL::" },
      { name = "DB_PASSWORD", valueFrom = "${aws_secretsmanager_secret.db.arn}:DB_PASSWORD::" },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "app"
      }
    }
  }])

  depends_on = [aws_secretsmanager_secret_version.db]
}

resource "aws_ecs_service" "app" {
  name                               = "${var.name_prefix}-app"
  cluster                            = aws_ecs_cluster.this.id
  task_definition                    = aws_ecs_task_definition.app.arn
  desired_count                      = var.desired_count
  launch_type                        = "FARGATE"
  health_check_grace_period_seconds  = 60
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100
  propagate_tags                     = "SERVICE"
  wait_for_steady_state              = false # the runner waits and checks health itself

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = true # no NAT gateway (ADR-024)
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = var.container_port
  }

  depends_on = [aws_lb_listener.http, aws_iam_role_policy_attachment.execution]
}
