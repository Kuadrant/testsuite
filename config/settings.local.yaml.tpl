#default:
#  skip_cleanup: false
#  openshift:
#    project: "authorino"
#  rhsso:
#    url: "SSO_URL"
#    username: "SSO_ADMIN_USERNAME"
#    password: "SSO_ADMIN_PASSWORD"
#    test_user:
#      username: "testUser"
#      password: "testPassword"
#  authorino:
#    image: "quay.io/kuadrant/authorino:latest"  # If specified will override the authorino image
#    deploy: false                               # If false, the testsuite will use already deployed authorino for testing
#    url: ""                                     # URL for already deployed Authorino