"""The CloudFormation template a customer deploys once per AWS account (ADR-027/028).

It creates:
- a deploy role that only CloudPilot's principal may assume, and only with the account's
  External ID, capped by a permission boundary;
- the boundary itself, which every role OpenTofu creates must also carry (no escalation);
- an S3 bucket for OpenTofu state and saved plans: versioned, encrypted, TLS-only, private.

The template is plain data (JSON); nothing in it comes from repository content.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

ROLE_PATH = "/cloudpilot/"
ECS_EXECUTION_POLICY = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"


@dataclass(frozen=True)
class OnboardingNames:
    """Deterministic names for one connected account (suffix = 8 hex of our account row id)."""

    account_id: str
    suffix: str

    @property
    def stack_name(self) -> str:
        return f"cloudpilot-onboarding-{self.suffix}"

    @property
    def role_name(self) -> str:
        return f"CloudPilotDeployRole-{self.suffix}"

    @property
    def role_arn(self) -> str:
        return f"arn:aws:iam::{self.account_id}:role{ROLE_PATH}{self.role_name}"

    @property
    def boundary_name(self) -> str:
        return f"CloudPilotDeployBoundary-{self.suffix}"

    @property
    def boundary_arn(self) -> str:
        return f"arn:aws:iam::{self.account_id}:policy{ROLE_PATH}{self.boundary_name}"

    @property
    def state_bucket(self) -> str:
        return f"cloudpilot-state-{self.account_id}-{self.suffix}"


def _deploy_permissions(names: OnboardingNames, region: str) -> list[dict[str, Any]]:
    """What deployments may do: the container-postgres archetype's services in one region."""
    in_region = {"StringEquals": {"aws:RequestedRegion": region}}
    acct = names.account_id
    return [
        {
            "Sid": "ArchetypeServices",
            "Effect": "Allow",
            "Action": [
                "ec2:*Vpc*",
                "ec2:*Subnet*",
                "ec2:*SecurityGroup*",
                "ec2:*InternetGateway*",
                "ec2:*RouteTable*",
                "ec2:*Route",
                "ec2:Describe*",
                "ec2:CreateTags",
                "ec2:DeleteTags",
                "elasticloadbalancing:*",
                "ecs:*",
                "rds:*",
                "logs:*",
                "tag:GetResources",
                "cloudwatch:Describe*",
            ],
            "Resource": "*",
            "Condition": in_region,
        },
        {
            "Sid": "DeploymentSecrets",
            "Effect": "Allow",
            "Action": "secretsmanager:*",
            "Resource": f"arn:aws:secretsmanager:{region}:{acct}:secret:cloudpilot/*",
            "Condition": in_region,
        },
        {
            "Sid": "SecretsList",
            "Effect": "Allow",
            "Action": ["secretsmanager:ListSecrets", "secretsmanager:GetRandomPassword"],
            "Resource": "*",
            "Condition": in_region,
        },
        {
            "Sid": "ServiceKeysViaServicesOnly",
            "Effect": "Allow",
            "Action": [
                "kms:DescribeKey",
                "kms:CreateGrant",
                "kms:Decrypt",
                "kms:GenerateDataKey*",
                "kms:ListAliases",
            ],
            "Resource": "*",
            "Condition": {"StringLike": {"kms:ViaService": f"*.{region}.amazonaws.com"}},
        },
        {
            "Sid": "ImagesReadOnly",
            "Effect": "Allow",
            "Action": [
                "ecr:GetAuthorizationToken",
                "ecr:BatchGetImage",
                "ecr:GetDownloadUrlForLayer",
                "ecr:DescribeImages",
                "ecr:DescribeRepositories",
            ],
            "Resource": "*",
        },
        {
            "Sid": "TaskRolesUnderPathWithBoundary",
            "Effect": "Allow",
            "Action": ["iam:CreateRole", "iam:PutRolePermissionsBoundary"],
            "Resource": f"arn:aws:iam::{acct}:role{ROLE_PATH}*",
            "Condition": {"StringEquals": {"iam:PermissionsBoundary": names.boundary_arn}},
        },
        {
            "Sid": "ManageTaskRolesUnderPath",
            "Effect": "Allow",
            "Action": [
                "iam:GetRole",
                "iam:DeleteRole",
                "iam:TagRole",
                "iam:UntagRole",
                "iam:ListRolePolicies",
                "iam:ListAttachedRolePolicies",
                "iam:ListInstanceProfilesForRole",
                "iam:GetRolePolicy",
                "iam:PutRolePolicy",
                "iam:DeleteRolePolicy",
                "iam:UpdateAssumeRolePolicy",
            ],
            "Resource": f"arn:aws:iam::{acct}:role{ROLE_PATH}*",
        },
        {
            "Sid": "OnlyTheEcsExecutionManagedPolicy",
            "Effect": "Allow",
            "Action": ["iam:AttachRolePolicy", "iam:DetachRolePolicy"],
            "Resource": f"arn:aws:iam::{acct}:role{ROLE_PATH}*",
            "Condition": {"ArnEquals": {"iam:PolicyARN": ECS_EXECUTION_POLICY}},
        },
        {
            "Sid": "PassTaskRolesToEcsOnly",
            "Effect": "Allow",
            "Action": "iam:PassRole",
            "Resource": f"arn:aws:iam::{acct}:role{ROLE_PATH}*",
            "Condition": {"StringEquals": {"iam:PassedToService": "ecs-tasks.amazonaws.com"}},
        },
        {
            "Sid": "ServiceLinkedRolesForTheArchetype",
            "Effect": "Allow",
            "Action": "iam:CreateServiceLinkedRole",
            "Resource": "*",
            "Condition": {
                "StringEquals": {
                    "iam:AWSServiceName": [
                        "ecs.amazonaws.com",
                        "elasticloadbalancing.amazonaws.com",
                        "rds.amazonaws.com",
                    ]
                }
            },
        },
        {
            "Sid": "ReadOwnIdentityAndPolicies",
            "Effect": "Allow",
            "Action": ["sts:GetCallerIdentity", "iam:GetPolicy", "iam:GetPolicyVersion"],
            "Resource": "*",
        },
        {
            "Sid": "StateBucket",
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:GetBucketVersioning",
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
            ],
            "Resource": [
                f"arn:aws:s3:::{names.state_bucket}",
                f"arn:aws:s3:::{names.state_bucket}/*",
            ],
        },
    ]


def render_template(
    names: OnboardingNames, *, external_id: str, platform_principal_arn: str, region: str
) -> str:
    permissions = {"Version": "2012-10-17", "Statement": _deploy_permissions(names, region)}
    tags = [{"Key": "cloudpilot:purpose", "Value": "onboarding"}]
    template = {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": (
            "CloudPilot onboarding: a deploy role CloudPilot assumes with an External ID, its "
            "permission boundary, and an encrypted S3 bucket for OpenTofu state and plans."
        ),
        "Resources": {
            "DeployBoundary": {
                "Type": "AWS::IAM::ManagedPolicy",
                "Properties": {
                    "ManagedPolicyName": names.boundary_name,
                    "Path": ROLE_PATH,
                    "Description": "Limit for CloudPilot's deploy role and every role it creates",
                    "PolicyDocument": permissions,
                },
            },
            "DeployRole": {
                "Type": "AWS::IAM::Role",
                "Properties": {
                    "RoleName": names.role_name,
                    "Path": ROLE_PATH,
                    "MaxSessionDuration": 3600,
                    "PermissionsBoundary": {"Ref": "DeployBoundary"},
                    "AssumeRolePolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": {"AWS": platform_principal_arn},
                                "Action": "sts:AssumeRole",
                                "Condition": {"StringEquals": {"sts:ExternalId": external_id}},
                            }
                        ],
                    },
                    "Policies": [
                        {"PolicyName": "cloudpilot-deploy", "PolicyDocument": permissions}
                    ],
                    "Tags": tags,
                },
            },
            "StateBucket": {
                "Type": "AWS::S3::Bucket",
                "DeletionPolicy": "Retain",
                "UpdateReplacePolicy": "Retain",
                "Properties": {
                    "BucketName": names.state_bucket,
                    "VersioningConfiguration": {"Status": "Enabled"},
                    "BucketEncryption": {
                        "ServerSideEncryptionConfiguration": [
                            {"ServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}
                        ]
                    },
                    "PublicAccessBlockConfiguration": {
                        "BlockPublicAcls": True,
                        "BlockPublicPolicy": True,
                        "IgnorePublicAcls": True,
                        "RestrictPublicBuckets": True,
                    },
                    "OwnershipControls": {"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]},
                    "LifecycleConfiguration": {
                        "Rules": [
                            {
                                "Id": "expire-old-versions",
                                "Status": "Enabled",
                                "NoncurrentVersionExpiration": {"NoncurrentDays": 30},
                            }
                        ]
                    },
                    "Tags": [{"Key": "cloudpilot:purpose", "Value": "state"}],
                },
            },
            "StateBucketTlsOnly": {
                "Type": "AWS::S3::BucketPolicy",
                "Properties": {
                    "Bucket": {"Ref": "StateBucket"},
                    "PolicyDocument": {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Sid": "DenyPlainHttp",
                                "Effect": "Deny",
                                "Principal": "*",
                                "Action": "s3:*",
                                "Resource": [
                                    f"arn:aws:s3:::{names.state_bucket}",
                                    f"arn:aws:s3:::{names.state_bucket}/*",
                                ],
                                "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                            }
                        ],
                    },
                },
            },
        },
        "Outputs": {
            "RoleArn": {"Value": {"Fn::GetAtt": ["DeployRole", "Arn"]}},
            "StateBucketName": {"Value": {"Ref": "StateBucket"}},
            "PermissionsBoundaryArn": {"Value": {"Ref": "DeployBoundary"}},
        },
    }
    return json.dumps(template, indent=2) + "\n"
