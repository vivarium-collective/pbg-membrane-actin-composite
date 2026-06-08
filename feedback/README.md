# Expert feedback

YAML feedback reports generated from the investigation report
(https://vivarium-collective.github.io/pbg-membrane-actin-composite/) arrive as
GitHub issues labelled `feedback` (the report's "→ GitHub issue" button opens a
prefilled issue), or can be added here manually. The YAML can also be downloaded
from the report and attached/committed by hand.

Schema (mirrors the report's per-section comment boxes):

```yaml
meta:
  investigation: <slug>
  reviewer: "<name>"
  focus: expert-review
  overall_assessment: |
    <one paragraph>
annotations:
  <section_key>:        # executive | scientific_argument | <study_key> |
    - text: |           # global_visual_design | global_interpretation
        <comment>
```

Integrate with `/pbg-investigation` (fold annotations into the relevant study/investigation specs).
