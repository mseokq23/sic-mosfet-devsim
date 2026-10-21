| policy / condition | final MAE_norm | Δ vs uncertainty (×10⁻³) [95% CI] | top-10 overlap (actual/displayed) |
|---|---|---|---|
| Random | 0.1263 | +2.5 [+0.9, +3.9] | — |
| Sobol | 0.1240 | +0.2 [-0.9, +1.3] | — |
| Uncertainty | 0.1238 | — | — |
| A0 LLM, first run | 0.1250 | +1.2 [-0.8, +3.6] | 0.63/0.63 |
| A LLM, original payload | 0.1236 | -0.2 [-1.7, +1.3] | 0.62/0.62 |
| B LLM, anonymized | 0.1242 | +0.4 [-1.6, +3.1] | 0.55/0.55 |
| C LLM, perturbed input | 0.1257 | +1.9 [-0.7, +4.8] | 0.49/0.64 |
| D random 10 of top-20 | 0.1259 | +2.1 [-0.3, +5.0] | — |

Initial 60 devices + 10 × 6 rounds, S2 features, RF inverse model, nominal noise; mean over 10 seeds (the seed changes the initial set and the RF; the noise realisation is fixed). Δ: seed-paired difference from the uncertainty policy with a seed bootstrap 95 % CI.
Overlap: share of the 10 picks in the actual / displayed uncertainty top-10 (random 0.50). A0 is the first run of A in another environment; A, B, C, D, uncertainty, random and Sobol ran in one session.
