output "alb_dns_name" {
  value = aws_lb.this.dns_name
}

output "health_url" {
  value = "http://${aws_lb.this.dns_name}${var.health_path}"
}

output "endpoint_url" {
  value = "http://${aws_lb.this.dns_name}/"
}

output "cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "service_name" {
  value = aws_ecs_service.app.name
}

output "task_family" {
  value = aws_ecs_task_definition.app.family
}

output "log_group" {
  value = aws_cloudwatch_log_group.app.name
}

output "db_identifier" {
  value = aws_db_instance.this.identifier
}
