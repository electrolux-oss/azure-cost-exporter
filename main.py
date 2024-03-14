#!/usr/bin/python
# -*- coding:utf-8 -*-
# Filename: main.py

import os
import sys
import argparse
import yaml
from app.exporter import MetricExporter
from envyaml import EnvYAML
from prometheus_client import start_http_server
import logging


class key_value_arg(argparse.Action):
    def __call__(self, parser, namespace,
                 values, option_string=None):
        setattr(namespace, self.dest, dict())

        for kvpair in values:
            assert len(kvpair.split("=")) == 2

            key, value = kvpair.split("=")
            getattr(namespace, self.dest)[key] = value


def generate_secret_yaml(file_path, config):
    needed_secrets = dict()
    for target in config["target_azure_accounts"]:
        needed_secrets[target["TenantId"]] = {
            "client_id": "PUT_CLIENT_ID_HERE", "client_secret": "PUT_CLIENT_SECRET_HERE"}

    with open(file_path, "w") as secret_yaml:
        yaml.dump(needed_secrets, secret_yaml)


def get_configs():
    parser = argparse.ArgumentParser(
        description="Azure Cost Exporter, exposing Azure cost data as Prometheus metrics.")
    parser.add_argument("-c", "--config", required=True,
                        help="The config file (exporter_config.yaml) for the exporter")
    parser.add_argument("-s", "--secret", default="./secret.yaml",
                        help="The secrets file (secret.yaml) that contains the credentials for each target account")
    args = parser.parse_args()

    if (not os.path.exists(args.config) or not os.path.isfile(args.config)):
        logging.error(
            "Azure Cost Exporter config file does not exist, or it is not a file!")
        sys.exit(1)

    config = EnvYAML(args.config)

    # config validation
    if len(config["target_azure_accounts"]) == 0:
        logging.error(
            "There should be at leaest one target Azure accounts defined in the config!")
        sys.exit(1)

    labels = config["target_azure_accounts"][0].keys()

    if "TenantId" not in labels or "Subscription" not in labels:
        logging.error(
            "TenantId and Subscription are mandatory keys in target_azure_accounts!")
        sys.exit(1)

    for i in range(1, len(config["target_azure_accounts"])):
        if labels != config["target_azure_accounts"][i].keys():
            logging.error(
                "All the target Azure accounts should have the same set of keys (labels)!")
            sys.exit(1)

    # read and validate secret
    if (not os.path.exists(args.secret)):
        logging.error(
            "Azure Cost Exporter secret file does not exist. secret.yaml is generated based on your config file.")
        generate_secret_yaml(args.secret, config)
        sys.exit(1)
    elif (not os.path.isfile(args.secret)):
        logging.error(
            "The specified Azure Cost Exporter secret path is not a file!")
        sys.exit(1)

    secret = EnvYAML(args.secret)

    for tenant in config["target_azure_accounts"]:
        if tenant["TenantId"] not in secret:
            logging.error("The secret for tenant %s is missing in %s!" %
                          (tenant, args.secret))
            sys.exit(1)

    return config, secret


def main(config, secrets):
    app_metrics = MetricExporter(
        polling_interval_seconds=config["polling_interval_seconds"],
        metric_name=config["metric_name"],
        group_by=config["group_by"],
        targets=config["target_azure_accounts"],
        secrets=secrets
    )
    start_http_server(config["exporter_port"])
    app_metrics.run_metrics_loop()


if __name__ == "__main__":
    logger_format = "%(asctime)-15s %(levelname)-8s %(message)s"
    logging.basicConfig(level=logging.WARNING, format=logger_format)
    config, secrets = get_configs()
    main(config, secrets)
