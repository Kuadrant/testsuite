# Kuadrant E2E testsuite

This repository contains end-to-end tests for Kuadrant project. Currently, it only contains tests for Authorino.

## Requirements

To run the testsuite you currently need an OpenShift 4 cluster with Authorino Operator deployed and namespace where the tests will be executed.

## Configuration

Kuadrant testsuite uses [Dynaconf](https://www.dynaconf.com/) for configuration, which means you can specify the configuration through either settings files in `config` directory or through environmental variables. 
All the required and possible configuration options can be found in `config/settings.local.yaml.tpl`

### Settings files

Settings files are located at `config` directory and are in `yaml` format. To use them for local development, you can create `settings.local.yaml` and put all settings there.

### Environmental variables

You can also configure all the settings through environmental variables as well. We use prefix `KUADRANT` so the variables can look like this:
```bash
export KUADRANT_RHSSO__url="https://my-sso.net"
```
You can find more info on the [Dynaconf wiki page](https://www.dynaconf.com/envvars/)

## Usage

You can run and manage environment for testsuite with the included Makefile, but the recommended way how to run the testsuite is from Container image

### Local development setup

Requirements:
* Python 3.9+
* [pipenv](https://pipenv.pypa.io/en/latest/)
* [CFSSL](https://github.com/cloudflare/cfssl)
* [OpenShift CLI tools](https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html) (oc)

If you have all of those, you can run ```make pipenv-dev``` to install virtual environment and all dependencies
To run all tests you can then use ```make test```

### Running from container

For just running tests, the container image is the easiest option, you can log in to OpenShift and then run it like this
```bash
podman run \
	-v $HOME/.kube/config:/run/kubeconfig:z \
	-e KUADRANT_OPENSHIFT__project=authorino \
	-e KUADRANT_RHSSO__url="https://my-sso.net" \
	-e KUADRANT_RHSSO__password="ADMIN_PASSWORD" \
	-e KUADRANT_RHSSO__username="ADMIN_USERNAME" \
	quay.io/kuadrant/testsuite:latest
```
The results and reports will be saved in `/test-run-results` in the container.
