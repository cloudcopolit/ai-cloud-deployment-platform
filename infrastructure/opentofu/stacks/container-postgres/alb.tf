# Internet-facing by design: the security group admits only the CIDR given at deploy time
# (ADR-024), and the policy check refuses any other 0.0.0.0/0 ingress (ADR-033).
# trivy:ignore:AWS-0053
resource "aws_lb" "this" {
  name               = "${var.name_prefix}-alb"
  load_balancer_type = "application"
  internal           = false
  subnets            = aws_subnet.public[*].id
  security_groups    = [aws_security_group.alb.id]
  idle_timeout       = 30

  drop_invalid_header_fields = true
}

resource "aws_lb_target_group" "app" {
  name                 = "${var.name_prefix}-tg"
  port                 = var.container_port
  protocol             = "HTTP"
  target_type          = "ip"
  vpc_id               = aws_vpc.this.id
  deregistration_delay = 10

  health_check {
    path                = var.health_path
    matcher             = "200-399"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

# HTTP only until the deployment has a domain and a certificate: shown as the HTTP_ONLY risk
# on every plan (ADR-024).
# trivy:ignore:AWS-0054
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP" # nosemgrep: terraform.aws.security.insecure-load-balancer-tls-version.insecure-load-balancer-tls-version

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}
