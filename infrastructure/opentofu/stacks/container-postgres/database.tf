resource "random_password" "db" {
  length  = 32
  special = false # the password goes into a URL
}

resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-db"
  subnet_ids = aws_subnet.private[*].id
}

# Sandbox settings (shown as risks in the plan): no backups, no final snapshot, no deletion
# protection, so destroy leaves nothing behind (ADR-024). No log export either: RDS would
# create its log group itself, outside the state, and it would outlive destroy.
resource "aws_db_instance" "this" { # nosemgrep: terraform.aws.security.aws-rds-backup-no-retention.aws-rds-backup-no-retention, terraform.aws.security.aws-db-instance-no-logging.aws-db-instance-no-logging
  identifier                 = "${var.name_prefix}-db"
  engine                     = "postgres"
  engine_version             = var.db_engine_version
  instance_class             = var.db_instance_class
  allocated_storage          = var.db_storage_gb
  storage_type               = "gp3"
  storage_encrypted          = true
  db_name                    = "app"
  username                   = "appuser"
  password                   = random_password.db.result
  db_subnet_group_name       = aws_db_subnet_group.this.name
  vpc_security_group_ids     = [aws_security_group.db.id]
  publicly_accessible        = false
  multi_az                   = false
  backup_retention_period    = 0
  skip_final_snapshot        = true
  deletion_protection        = false
  delete_automated_backups   = true
  apply_immediately          = true
  auto_minor_version_upgrade = true
}

resource "aws_secretsmanager_secret" "db" {
  name                    = "cloudpilot/${var.deployment_id}/db"
  description             = "Database connection for CloudPilot deployment ${var.deployment_id}"
  recovery_window_in_days = 0 # deleted with the deployment
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    DATABASE_URL = "postgresql://${aws_db_instance.this.username}:${random_password.db.result}@${aws_db_instance.this.address}:${aws_db_instance.this.port}/${aws_db_instance.this.db_name}"
    DB_PASSWORD  = random_password.db.result
  })
}
