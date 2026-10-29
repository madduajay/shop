# Pending Thread3 SSL trust confirmation

No trust action has been executed. This request comes from the user's explicit restriction on new security/trust changes.

## Concise request for the user

May I temporarily add **Thread3 test CA cb05212b69d0** to your **user login keychain for SSL**, run the isolated Thread3 Chrome tests, and then remove that exact certificate and trust setting? Its SHA-256 is `5de00475f0e727621fcaac0f00d5874509e87276b8b7b9b0eb0196e614e29d08` and it expires at **2026-10-23 09:48:52 UTC**. Tests use `https://atlas.localhost:8543`, `https://jacket.localhost:8543` and their port-8545 test counterparts. No DNS edits, original private keys, original services, or TLS bypass flags will be used.

## Scope and security impact

- CA public certificate: `/private/var/folders/nq/mxk415m507b6cnnlxvd42v9c0000gn/T/thread3-tls-gh9zfub6/ca.pem`.
- Target keychain: `/Users/ajaybabum/Library/Keychains/login.keychain-db`; user trust domain only, not admin/system trust.
- Proposed trust policy: SSL only. The new CA carries critical DNS name constraints for `atlas.localhost` and `jacket.localhost`; its leaf SANs are exactly those names.
- Trust applies to applications using user trust and is not limited to the disposable Chrome profile. Certificate trust is not port-scoped; only Thread3 test listeners are restricted to 8543/8545.
- The CA signing private key was generated in memory and discarded. Only the temporary leaf key exists on disk, owner-only (0600), outside original projects. No real account grant or persistent app credential is created.
- The keychain trust entry persists until explicitly removed. Certificate expiry does not automatically delete that entry. I will remove it after tests, on failures as well as success, and verify removal. A crash could delay cleanup; the exact cleanup command below remains available without the temporary certificate file.
- All original TLS certificates and keychain entries remain untouched. This adds/removes only the new SHA-256-identified certificate.

## Prepared commands (not executed)

Install, only after specific approval and the supported execution review:

```sh
security add-trusted-cert -r trustRoot -p ssl -k '/Users/ajaybabum/Library/Keychains/login.keychain-db' '/private/var/folders/nq/mxk415m507b6cnnlxvd42v9c0000gn/T/thread3-tls-gh9zfub6/ca.pem'
```

Cleanup that exact certificate and its user trust settings:

```sh
security delete-certificate -Z '5de00475f0e727621fcaac0f00d5874509e87276b8b7b9b0eb0196e614e29d08' -t '/Users/ajaybabum/Library/Keychains/login.keychain-db'
```

The commands were checked against the installed `security` CLI help. No private original certificate key was inspected or reused. Existing hostnames resolve to loopback in the approved execution context. No supported separate trusted certificate is available from the non-secret existing configuration; original private-key reuse is prohibited. Chrome warning bypasses and certificate-error override flags are not proposed.

## Execution outcome

Approval was received for the exact fingerprint at 04:03 UTC. The escalated CLI installation attempt timed out after 90 seconds. The cleanup block ran, and a separate read-only check independently confirmed that the exact certificate and its trust entry are absent. Chrome was not started. The next step is interactive execution of the already approved command on the Mac and completion of any native OS authorization, rather than another unattended retry. No broader permission or different certificate is requested.
