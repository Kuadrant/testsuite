# Kuadrant E2E testsuite

This repository contains end-to-end tests for Kuadrant project. Currently, it only contains tests for Authorino.

## Requirements

To run the testsuite you currently need an OpenShift 4.x cluster with Authorino Operator deployed and namespace where the tests will be executed.

## Configuration

Kuadrant testsuite uses [Dynaconf](https://www.dynaconf.com/) for configuration, which means you can specify the configuration through either settings files in `config` directory or through environmental variables. 
All the required and possible configuration options can be found in `config/settings.local.yaml.tpl`

### OpenShift auto-fetching

Some configuration options can be fetched from OpenShift if there are correctly deployed [tools](https://github.com/3scale-qe/tools).
Tools can be deployed by using `overlays/kuadrant` overlay and deploying RHSSO with the provided script like this:
```bash
oc apply -k overlays/kuadrant/ --namespace tools
NAMESPACE=tools ./base/rhsso/deploy-rhsso.sh
```

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

If you omit any options, Testsuite will run only subset of tests that don't require that variable e.g. not providing Auth0 will result in skipping Auth0 tests.

NOTE: For binding kubeconfig file, the "others" need to have permission to read, otherwise it will not work.
The results and reports will be saved in `/test-run-results` in the container.

#### With tools setup

```bash
podman run \
	-v $HOME/.kube/config:/run/kubeconfig:z \
	-e KUADRANT_OPENSHIFT__project=authorino \
	-e KUADRANT_OPENSHIFT2__project=authorino2 \
	-e KUADRANT_AUTH0__url="AUTH0_URL" \
	-e KUADRANT_AUTH0__client_id="AUTH0_CLIENT_ID" \
	-e KUADRANT_AUTH0__client_secret="AUTH0_CLIENT_SECRET" \	
	quay.io/kuadrant/testsuite:latest
```

#### Without tools

```bash
podman run \
	-v $HOME/.kube/config:/run/kubeconfig:z \
	-e KUADRANT_OPENSHIFT__project=authorino \
	-e KUADRANT_OPENSHIFT2__project=authorino2 \
	-e KUADRANT_RHSSO__url="https://my-sso.net" \
	-e KUADRANT_RHSSO__password="ADMIN_PASSWORD" \
	-e KUADRANT_RHSSO__username="ADMIN_USERNAME" \
	-e KUADRANT_AUTH0__url="AUTH0_URL" \
	-e KUADRANT_AUTH0__client_id="AUTH0_CLIENT_ID" \
	-e KUADRANT_AUTH0__client_secret="AUTH0_CLIENT_SECRET" \
	quay.io/kuadrant/testsuite:latest
```

## Developing tests

For developing tests for Authorino you might need to know content of the authorization JSON, you can do that through this AuthConfig, which will return all the context in the response

```yaml
apiVersion: authorino.kuadrant.io/v1beta1
kind: AuthConfig
metadata:
  name: example
spec:
  response:
  - name: auth-json
    json:
      properties:
      - name: context
        valueFrom: { authJSON: context }
      - name: auth
        valueFrom: { authJSON: auth }
```

Another thing which might helpful is using playground for developing OPA policies https://play.openpolicyagent.org/.