## ADDED Requirements

### Requirement: Executable database acceptance must be calibrated before model comparison
The benchmark MUST validate public behavior using a pinned real database when correctness depends on database transaction or concurrency semantics. It MUST calibrate reference, structurally equivalent correct, negative and assertion-specific mutation implementations before comparing model conditions. Legitimate behavior MUST remain accepted.

#### Scenario: Equivalent solution and broken boundary
- **WHEN** calibration runs two structurally different correct implementations and a mutation violating one public behavior
- **THEN** both correct implementations pass and the mutation fails the corresponding behavioral assertion, without requiring a particular helper or SQL name

### Requirement: Evaluation evidence must remain condition independent
The evaluator MUST NOT receive Practice text, condition labels, private answer hints in candidate inputs, or infer condition from evaluator workspace names. Model workspaces MUST exclude private acceptance material and other attempts. Isolation MUST be verified through executable access probes before effectiveness calls.

#### Scenario: Candidate tries accessing hidden material
- **WHEN** an isolation probe requests host private files or another attempt's database
- **THEN** access is denied and the observed denial is recorded before model execution is permitted

### Requirement: Failed delivery must remain visible
The experiment MUST preserve planned attempt denominators and distinguish execution health, semantic behavior and quality. Missing knowledge delivery MUST NOT silently become a successful injected condition. Raw candidate responses, code and executable observations MUST support reported comparisons.

#### Scenario: Retrieval or authorized model route unavailable
- **WHEN** retrieval cannot deliver its declared content or the authorized model cannot respond
- **THEN** the affected condition is marked unavailable with its cause, retained in the planned denominator, and not substituted without explicit authorization
