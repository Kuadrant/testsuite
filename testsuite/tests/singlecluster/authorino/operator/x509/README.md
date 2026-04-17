# TLS tests
Because for TLS testing we need a lot of different CA (Certificate authorities), intermediate CA and certificates and it can be confusing, here is a description of all available certificate/CA fixtures we use and their description.

```
envoy_ca
├── envoy_cert - Certificate that envoy uses
└── valid_cert - Certificate accepted by envoy
invalid_ca
└── invalid_cert - Certificate rejected by envoy
authorino_ca
└── authorino_cert - Certificate that Authorino uses
```