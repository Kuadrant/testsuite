#default:
#  tester: "someuser"                          # Optional: name of the user, who is running the tests, defaults to whoami/uid
#  cluster:                                    # Workload cluster where tests should run, will get overriden if run on Multicluster
#    project: "kuadrant"                       # Optional: Default namespace for this cluster
#    api_url: "https://api.openshift.com"      # Optional: OpenShift API URL, if None it will OpenShift that you are logged in
#    token: "KUADRANT_RULEZ"                   # Optional: OpenShift Token, if None it will OpenShift that you are logged in
#    kubeconfig_path: "~/.kube/config"         # Optional: Kubeconfig to use, if None the default one is used
#  tools:
#    project: "tools"                          # Optional: OpenShift project, where external tools are located
#  keycloak:
#    url: "KEYCLOAK_URL"
#    username: "KEYCLOAK_ADMIN_USERNAME"
#    password: "KEYCLOAK_ADMIN_PASSWORD"
#    test_user:
#      username: "testUser"
#      password: "testPassword"
#  auth0:
#    client_id: "CLIENT_ID"
#    client_secret: "CLIENT_SECRET"
#    url: "AUTH0_URL"
#  mockserver:
#    url: "MOCKSERVER_URL"
#  tracing:
#    backend: "jaeger"                          # Tracing backend
#    collector_url: "rpc://jaeger-collector.com:4317"  # Tracing collector URL (may be internal)
#    query_url: "http://jaeger-query.com"       # Tracing query URL
#  cfssl: "cfssl"  # Path to the CFSSL library for TLS tests
#  hyperfoil:
#    url: "HYPERFOIL_URL"
#    generate_reports: True                      # True, if each test should generate a report
#    report_dir: "reports"                       # Directory, to which the reports should be saved
#  service_protection:
#    system_project: "kuadrant-system"           # Namespace where Kuadrant resource resides
#    project: "kuadrant"                         # Namespace where tests will run
#    project2: "kuadrant2"                       # Second namespace for tests, that run across multiple namespaces
#    envoy:
#      image: "docker.io/envoyproxy/envoy:v1.23-latest"  # Envoy image, the testsuite should use, only for Authorino tests
#    gateway:                                      # Optional: Reference to Gateway that should be used, if empty testsuite will create its own
#       namespace: "istio-system"
#       name: "istio-ingressgateway"
#    authorino:
#      image: "quay.io/kuadrant/authorino:latest"  # If specified will override the authorino image
#  default_exposer: "kubernetes"                   # Force Exposer typem options: 'openshift', 'kind', 'kubernetes'
#  control_plane:
#    managedzone: aws-mz                           # Name of the ManagedZone resource
#    issuer:                                       # Issuer object for testing TLSPolicy
#      name: "selfsigned-cluster-issuer"           # Name of Issuer CR
#      kind: "ClusterIssuer"                       # Kind of Issuer, can be "Issuer" or "ClusterIssuer"
#  letsencrypt:
#    issuer:                                       # Issuer object for testing TLSPolicy
#      name: "letsencrypt-staging-issuer"          # Name of Issuer CR
#      kind: "Issuer"                              # Kind of Issuer, can be "Issuer" or "ClusterIssuer"
