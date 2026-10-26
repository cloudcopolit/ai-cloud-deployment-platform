#!/usr/bin/env python3
"""Refresh CloudPilot's AWS price table from the public AWS Price List (no credentials).

    python scripts/refresh_aws_prices.py [--region us-east-1]

Downloads the per-service on-demand offer files from pricing.us-east-1.amazonaws.com, picks
the exact SKUs the architecture agent prices (listed in SELECTORS), and writes
ai/src/cloudpilot_ai/architecture/prices/<region>.json with each price, its unit, the SKU,
AWS's own description, and the offer's publication date. The plan's `pricing_as_of` is the
oldest publication date among the offers it used. Standard library only; the downloaded JSON
is parsed as data.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

BASE = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws"
OUT_DIR = Path(__file__).resolve().parents[1] / "ai" / "src" / "cloudpilot_ai" / "architecture" / "prices"

# key -> (offer, regional?, attribute filters, first tier only)
SELECTORS: dict[str, tuple[str, bool, dict[str, str]]] = {
    "fargate_vcpu_hour": ("AmazonECS", True, {"usagetype": "{P}Fargate-vCPU-Hours:perCPU"}),
    "fargate_gb_hour": ("AmazonECS", True, {"usagetype": "{P}Fargate-GB-Hours"}),
    "alb_hour": ("AWSELB", True, {"usagetype": "{P}LoadBalancerUsage", "productFamily": "Load Balancer-Application"}),
    "alb_lcu_hour": ("AWSELB", True, {"usagetype": "{P}LCUUsage", "productFamily": "Load Balancer-Application"}),
    "public_ipv4_hour": ("AmazonVPC", True, {"usagetype": "{P}PublicIPv4:InUseAddress"}),
    "rds_postgres_t4g_micro_hour": (
        "AmazonRDS",
        True,
        {
            "usagetype": "{P}InstanceUsage:db.t4g.micro",
            "databaseEngine": "PostgreSQL",
            "deploymentOption": "Single-AZ",
        },
    ),
    "rds_gp3_gb_month": (
        "AmazonRDS",
        True,
        {"usagetype": "{P}RDS:GP3-Storage", "databaseEngine": "PostgreSQL", "deploymentOption": "Single-AZ"},
    ),
    "elasticache_redis_t4g_micro_hour": (
        "AmazonElastiCache",
        True,
        {"usagetype": "{P}NodeUsage:cache.t4g.micro", "cacheEngine": "Redis"},
    ),
    "msk_t3_small_broker_hour": ("AmazonMSK", True, {"usagetype": "{P}Kafka.t3.small"}),
    "msk_storage_gb_month": ("AmazonMSK", True, {"usagetype": "{P}Kafka.Storage.GP2"}),
    "mq_rabbitmq_t3_micro_hour": ("AmazonMQ", True, {"usagetype": "{P}RabbitMQ-Single-InstanceUsage:mq.t3.micro"}),
    "mq_rabbitmq_storage_gb_month": ("AmazonMQ", True, {"usagetype": "{P}TimedStorage-RabbitMQ-ByteHrs"}),
    "opensearch_t3_small_hour": ("AmazonES", True, {"usagetype": "{P}ESInstance:t3.small"}),
    "s3_standard_gb_month": ("AmazonS3", True, {"usagetype": "{P}TimedStorage-ByteHrs", "volumeType": "Standard"}),
    "secretsmanager_secret_month": ("AWSSecretsManager", True, {"usagetype": "{P}AWSSecretsManager-Secrets"}),
    # CloudWatch lists a "Legacy" and a "Current" SKU for the same usage; price the current one.
    "cloudwatch_logs_ingest_gb": (
        "AmazonCloudWatch",
        True,
        {"usagetype": "{P}DataProcessing-Bytes", "version": "Current"},
    ),
    "cloudwatch_logs_storage_gb_month": (
        "AmazonCloudWatch",
        True,
        {"usagetype": "{P}TimedStorage-ByteHrs", "version": "Current"},
    ),
    "ecr_storage_gb_month": ("AmazonECR", True, {"usagetype": "{P}TimedStorage-ByteHrs"}),
    "cloudfront_us_transfer_out_gb": ("AmazonCloudFront", False, {"usagetype": "US-DataTransfer-Out-Bytes"}),
    "route53_hosted_zone_month": ("AmazonRoute53", False, {"usagetype": "HostedZone"}),
}
# us-east-1 usage types carry no prefix for some services and "USE1-" for others; both tried.
REGION_PREFIX = {"us-east-1": ["", "USE1-"]}


def _download(offer: str, region: str | None) -> dict:
    url = f"{BASE}/{offer}/current/{region}/index.json" if region else f"{BASE}/{offer}/current/index.json"
    with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 - fixed https URL
        return json.load(response)


def _match(product: dict, filters: dict[str, str], prefixes: list[str]) -> bool:
    attributes = {**product.get("attributes", {}), "productFamily": product.get("productFamily")}
    for key, wanted in filters.items():
        if "{P}" in wanted:
            if attributes.get(key) not in {wanted.replace("{P}", p) for p in prefixes}:
                return False
        elif attributes.get(key) != wanted:
            return False
    return True


def refresh(region: str) -> dict:
    prefixes = REGION_PREFIX.get(region)
    if prefixes is None:
        raise SystemExit(f"no usage-type prefix mapping for {region}; add it to REGION_PREFIX")
    offers: dict[tuple[str, bool], dict] = {}
    items: dict[str, dict] = {}
    for key, (offer, regional, filters) in SELECTORS.items():
        cache_key = (offer, regional)
        if cache_key not in offers:
            offers[cache_key] = _download(offer, region if regional else None)
        data = offers[cache_key]
        skus = [sku for sku, product in data["products"].items() if _match(product, filters, prefixes)]
        if len(skus) != 1:
            raise SystemExit(f"{key}: expected exactly one SKU, found {len(skus)}: {skus[:5]}")
        sku = skus[0]
        dimensions = [
            dim for term in data["terms"]["OnDemand"][sku].values() for dim in term["priceDimensions"].values()
        ]
        first = min(dimensions, key=lambda d: float(d.get("beginRange") or 0))
        items[key] = {
            "usd": float(first["pricePerUnit"]["USD"]),
            "unit": first["unit"],
            "sku": sku,
            "offer": offer,
            "description": first["description"].strip(),
            "published": data["publicationDate"][:10],
        }
    return {
        "region": region,
        "source": "AWS Price List (public on-demand offers), first pricing tier",
        "pricing_as_of": min(item["published"] for item in items.values()),
        "items": dict(sorted(items.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()
    table = refresh(args.region)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{args.region}.json"
    path.write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path} ({len(table['items'])} prices, pricing_as_of {table['pricing_as_of']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
