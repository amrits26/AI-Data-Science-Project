# Local TLS Certificates

Place local development TLS files in this directory for nginx:

- `fullchain.pem`
- `privkey.pem`

PowerShell self-signed example:

```powershell
$cert = New-SelfSignedCertificate -DnsName "localhost" -CertStoreLocation "cert:\LocalMachine\My"
$pwd = ConvertTo-SecureString -String "changeit" -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath ".\deploy\nginx\certs\localhost.pfx" -Password $pwd
```

Then convert PFX to PEM with OpenSSL:

```powershell
openssl pkcs12 -in .\deploy\nginx\certs\localhost.pfx -out .\deploy\nginx\certs\fullchain.pem -nodes
Copy-Item .\deploy\nginx\certs\fullchain.pem .\deploy\nginx\certs\privkey.pem
```

For production, replace with CA-issued certificates.
