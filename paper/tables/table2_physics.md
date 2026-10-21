| 423 K physics of the test data | Oracle | Mismatch | Mixture (post hoc) |
|---|---|---|---|
| baseline (γ = +1, r = 0) | 0.072 (-17%)* | — | 0.082 (-5%) |
| γ = 0 | 0.073 (-15%)* | **0.537** | 0.083 (-3%) |
| γ = -1 | 0.076 (-12%)* | **0.928** | 0.088 (+1%) |
| r = 0.1 | 0.057 (-34%)* | 0.084 | 0.079 (-8%) |
| r = 0.3 | 0.033 (-62%)* | **0.132** | 0.080 (-7%) |
| series resistance (test data only) | — | **0.261** | — |

S1 = 0.112, S1×2 = 0.086 (300 K features only, the same in every scenario). Oracle: trained with the test physics; Mismatch: trained with the baseline physics only; Mixture: trained on the five assumptions mixed (post hoc).
( ): change from S1×2; *: paired bootstrap 95 % CI of S2 - S1×2 below 0; bold: above S1. Series resistance 0.1–0.3 mΩ·cm² added to the test devices only (S1 0.378, S1×2 0.405, S2 0.261).
