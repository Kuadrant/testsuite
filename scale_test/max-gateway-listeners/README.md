# Create 2 gateways with 64 listeners each and confirm they are reachable with DNSPolicy applied
### How to run
```shell
kube-burner init -c ./config.yaml --timeout 30m --uuid $(whoami)-$(openssl rand -hex 3) --log-level debug
```

### Configuration
```shell
export PROMETHEUS_TOKEN=$(oc whoami -t)
export PROMETHEUS_URL=https://thanos-querier-openshift-monitoring.your.thanos.route.com
export OS_INDEXING=  # set as empty string if don't want indexing
export ES_SERVER=  # format: https://username:password@your.opensearch.instance.com
export SKIP_CLEANUP=true  # No automatic way to test the enforced policies, so generally set to true
export USE_STANDALONE_MESH=false # false indicates that Openshift Ingress is used
```
If you installed OSSMv3 yourself (IE you are not using Openshift Ingress feature available since OCP v4.19):
```
export USE_STANDALONE_MESH=true
```

#### Cloud configuration (One of the following)
```shell
# AWS
export DNS_PROVIDER=aws
export KUADRANT_ZONE_ROOT_DOMAIN=kuadrant.aws.domain.net  # DNS provider specific root domain
export KUADRANT_AWS_REGION=us-east-1
export KUADRANT_AWS_ACCESS_KEY_ID=EXAMPLEKEY
export KUADRANT_AWS_SECRET_ACCESS_KEY=AKIAEXAMPLEKEY

# GCP
export DNS_PROVIDER=gcp
export KUADRANT_ZONE_ROOT_DOMAIN=gcp.my.domain.net  # DNS provider specific root domain
export GCP_CONFIG_JSON='{\"type\":\"service_account\",\"project_id\":\"my-project\",\"private_key_id\":\"123321\", ...}'
export GCP_PROJECT_ID=my-project

# Azure
export DNS_PROVIDER=azure
export KUADRANT_ZONE_ROOT_DOMAIN=some.azure.domain.net  # DNS provider specific root domain
export AZURE_CONFIG_JSON='{\"tenantId\":\"abcd-4320\",\"subscriptionId\":\"321-231-123\", ...}'
```

### Test created dns records
```shell
./test.sh <KUBE_BURNER_RUN_UUID>
```

### Cleanup

Manually remove DNSPolicies
```shell
kubectl delete dnspolicy --all -n max-gateway-listeners-scale-test-0
```

Wait for all the DNSRecords to get removed, it might take a while. Then proceed with
```shell
kube-burner destroy --uuid <KUBE_BURNER_RUN_UUID>
```
