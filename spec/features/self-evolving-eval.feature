Feature: Self-evolving LLM evaluation with proof-gated results
  As a team shipping LLM-backed features
  I want an evaluator that seals every result in a verifiable ProofPacket
  and hardens itself when its own metrics get fooled
  So that eval failures become permanent, provable regression coverage
  instead of silently repeating forever

  Background:
    Given a fresh Evaluator with a lenient default configuration
    And an empty knowledge base at ".rig/failures.json"
    And an empty proofs directory at ".rig/proofs"

  Scenario: An eval passes and seals proof
    Given a case "case-001-faithfulness-pass" whose response is fully
      supported by its context
    When the Evaluator evaluates the case
    Then the result score is 1.0
    And the result passed is true
    And a ProofPacket is sealed for the case with an HMAC-SHA256 signature
    And re-verifying the ProofPacket's signature succeeds
    And no entry is written to the knowledge base, because the verdict
      matches the case's expected_pass ground truth

  Scenario: An eval fails and records to L10
    Given a case "case-007-toxicity-learn" whose response contains the
      leetspeak evasion "k1ll"
    And the case's expected_pass is false
    When the Evaluator evaluates the case
    Then the toxicity metric does not flag "k1ll" as a banned term
    And the result passed is true
    But this disagrees with the case's expected_pass of false
    When the Evaluator learns from this result
    Then a failure record is appended to the knowledge base
    And the evidence includes "k1ll" under near_miss_terms
    And the pattern "toxicity:false_negative:k1ll" now has a count of 1
    And the evaluator's banned_terms set is not yet extended, because the
      pattern has not yet crossed the hardening threshold

  Scenario: L10 generates a new test case from a failure pattern
    Given the pattern "toxicity:false_negative:k1ll" has already been
      recorded once from a prior generation
    When the L10Harness runs another generation over the same case
    Then the pattern count reaches the hardening threshold of 2
    And the evaluator's banned_terms set is extended with "k1ll"
    And the L10Harness generates a new regression case named
      "case-007-toxicity-learn::l10-gen<N>"
    And the generated case is a copy of the original case, tagged with
      meta.origin = "l10_generated" and meta.pattern_key =
      "toxicity:false_negative:k1ll"
    And the generated case is permanently added to the running suite
    When the suite is evaluated again in a later generation
    Then both the original case and the generated regression case are
      scored with the hardened banned_terms set
    And both now correctly report passed = false, matching expected_pass
    And no further failures are recorded for that pattern
