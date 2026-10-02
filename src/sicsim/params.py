"""4H-SiC / SiO2 material parameters and temperature-dependent derived quantities.

All lengths in cm (DEVSIM convention) unless a name ends with ``_um``.
Every coefficient carries its source tag so the paper's parameter table can be
generated from this file (see ``parameter_table()``).

Baseline set (single consistent set, as recommended in the draft):
  * Eg(T), Nc, Nv        : Levinshtein, Rumyantsev, Shur (2001)  [Levi01]
  * electron mobility    : Roschke & Schwierz, IEEE TED 48, 1442 (2001) [Rosc01, perp. c]
  * hole mobility        : Schaffer et al. (1994) [Scha94] + T-exponents as in [Rao22]
  * ionization energies  : Ikeda, Matsunami, Tanaka (1980): N(h) 66 meV, Al 191 meV [Iked80]
  * permittivity         : 9.7 (common TCAD value; alternative sets -> sensitivity study)
  * electron affinity    : 3.7 eV  (ASSUMPTION - degenerate with gate work function;
                                     absolute Vth is calibrated with Qf, see configs)
The 4H-SiC review (Burin et al., arXiv:2410.06798) explicitly gives no single
recommended set, so alternatives must be reported as a sensitivity study.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict, field

Q = 1.602176634e-19      # C
KB = 1.380649e-23        # J/K
EPS0 = 8.8541878128e-14  # F/cm


@dataclass
class SiC4H:
    eps_r: float = 9.7
    # band gap, Varshni form anchored at 300 K  [Levi01]
    Eg300: float = 3.23
    Eg_alpha: float = 6.5e-4
    Eg_beta: float = 1300.0
    # effective DOS at 300 K, scaled with T^1.5  [Levi01: 3.25e15*T^1.5, 4.8e15*T^1.5]
    Nc300: float = 1.69e19
    Nv300: float = 2.49e19
    chi: float = 3.7
    # incomplete ionization [Iked80]; alpha*: doping-dependent lowering dE = dE0 - alpha*N^(1/3)
    dED: float = 0.066
    gD: float = 2.0
    alphaD: float = 0.0
    dEA: float = 0.191
    gA: float = 4.0
    alphaA: float = 0.0
    # electron mobility Caughey-Thomas with T scaling [Rosc01]
    mun_min: float = 40.0
    mun_max: float = 950.0
    mun_Nref: float = 2.0e17
    mun_delta: float = 0.76
    mun_gmin: float = -0.5
    mun_gmax: float = -2.4
    mun_gref: float = 1.0
    # hole mobility [Scha94] + T exponents [Rao22]
    mup_min: float = 15.9
    mup_max: float = 124.0
    mup_Nref: float = 1.76e19
    mup_delta: float = 0.34
    mup_gmin: float = -0.5
    mup_gmax: float = -2.15
    mup_gref: float = 0.0
    # SRH lifetimes (constant; doping dependence = optional extension)
    taun: float = 1.0e-7
    taup: float = 1.0e-7
    # effective channel (interface-scattering) mobility, combined by Matthiessen's rule
    # 1/mu = 1/mu_bulk + exp(-d/lambda)/mu_surf  (EFFECTIVE model, calibrated)
    mu_surf300: float = 20.0
    mu_surf_gamma: float = 0.0
    surf_lambda_um: float = 0.003

    def derived(self, T: float) -> dict:
        t = T / 300.0
        Vt = KB * T / Q
        Eg = self.Eg300 + self.Eg_alpha * (300.0**2 / (300.0 + self.Eg_beta) - T**2 / (T + self.Eg_beta))
        Nc = self.Nc300 * t**1.5
        Nv = self.Nv300 * t**1.5
        ni = math.sqrt(Nc * Nv) * math.exp(-Eg / (2.0 * Vt))
        # intrinsic level measured from Ec (eV): Ec - Ei
        Ec_minus_Ei = 0.5 * Eg - 0.5 * Vt * math.log(Nv / Nc)
        d = dict(
            T=T, Vt=Vt, Eg=Eg, Nc=Nc, Nv=Nv, ni=ni, Ec_minus_Ei=Ec_minus_Ei,
            n1D=Nc * math.exp(-self.dED / Vt), p1A=Nv * math.exp(-self.dEA / Vt),
            mun_min=self.mun_min * t**self.mun_gmin, mun_max=self.mun_max * t**self.mun_gmax,
            mun_Nref=self.mun_Nref * t**self.mun_gref, mun_delta=self.mun_delta,
            mup_min=self.mup_min * t**self.mup_gmin, mup_max=self.mup_max * t**self.mup_gmax,
            mup_Nref=self.mup_Nref * t**self.mup_gref, mup_delta=self.mup_delta,
            mu_surf=self.mu_surf300 * t**self.mu_surf_gamma,
        )
        return d


@dataclass
class SiO2:
    eps_r: float = 3.9


@dataclass
class Gate:
    # n+ poly-Si gate work function (eV); metal gates -> change here
    phi_m: float = 4.1


def gate_offset(mat: SiC4H, gate: Gate, T: float) -> float:
    """Phi_m - Phi_i  (V). Gate contact BC: Potential = V_G - gate_offset.

    Potential reference = intrinsic level (n = p = n_i at Potential = 0).
    """
    d = mat.derived(T)
    phi_i = mat.chi + d["Ec_minus_Ei"]
    return gate.phi_m - phi_i


def parameter_table(mat: SiC4H | None = None) -> list[dict]:
    mat = mat or SiC4H()
    rows = []
    for k, v in asdict(mat).items():
        rows.append({"name": k, "value": v})
    return rows
