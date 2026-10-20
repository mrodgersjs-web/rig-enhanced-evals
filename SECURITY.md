# Security Policy

## Supported versions

| Version | Supported |
| :-- | :-: |
| `main` branch | yes |
| latest tagged release | yes |
| older releases | best effort |

`rig-enhanced-evals` is stdlib-only Python. The evaluator writes
proof packets to disk; see the threat model.

## Threat model in scope

- Integrity of the knowledge base file: the evaluator records
  failures and signatures there. A tampered knowledge base could
  poison the L10 learning loop. The evaluator re-reads the KB on
  every instantiation, so a corrupted file surfaces as broken
  evaluations.
- Proof packet integrity: every result carries a signed proof
  packet. The verifier recomputes the HMAC; tampering is caught.
- Dataset injection: the loader rejects datasets whose required
  fields are missing or whose IDs collide.

The library is OUT of scope for:

- the correctness of an LLM under evaluation. The evaluator
  measures behaviour against a rule set; it does not judge the
  underlying model.

## Reporting a vulnerability

Please email **security@rodgersintelligence.com** with:

- a description of the issue and impact
- the commit SHA or tag you reproduced against
- a minimal reproduction

We aim to acknowledge within 3 business days. Please do not file a
public issue for a security report.
