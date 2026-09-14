# Research OS execution boundary

## Enforced on the local Windows backend

- Commands are argument arrays; shell strings and shell interpolation are not accepted.
- The working directory and absolute path arguments must remain inside declared roots.
- Only allow-listed environment variables are inherited; secret-like variables are removed.
- Python, R, Stata and LaTeX scripts must be project-local and match an approved SHA-256.
- Output directories are single-use idempotency boundaries and required outputs are checked.
- Each process is attached to a Windows Job Object with kill-on-close. Timeout and cancellation terminate the process tree rather than only the parent.
- stdout, stderr, inputs, outputs, hashes, elapsed time, return code and isolation capabilities are recorded.

## Honest limitations

The local Windows backend does not provide an AppContainer, VM, container, or firewall namespace. Its `network_policy=deny` value is therefore a declared policy, **not OS-level network blocking**. A caller that requires OS-enforced network denial must set `require_os_network_isolation=true`; this backend then fails closed. Likewise, filesystem enforcement is path-policy based rather than an OS access-control sandbox.

Consequences:

- This boundary is tested for path checks, environment filtering and process-tree termination.
- It is not production-certified for executing untrusted code against restricted data.
- Hash approval means provenance and researcher authorization; it does not prove code safety.
- A future container, AppContainer, or Sandbox-Agent backend may satisfy the stronger boundary without changing Tool or ResearchState contracts.

External-network and external-write tools remain separate, permission-gated tool classes. Native analysis adapters do not receive credentials by default.
