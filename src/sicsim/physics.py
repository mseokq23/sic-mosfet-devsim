"""DEVSIM model definitions for 4H-SiC (semiconductor) and SiO2 (insulator).

Formulation: Potential / Electrons / Holes (Scharfetter-Gummel, Boltzmann statistics).
Potential reference = intrinsic level.  Because n_i(4H-SiC, 300 K) ~ 1e-8 cm^-3,
minority densities reach ~1e-35 cm^-3; DEVSIM extended (128-bit) precision is
therefore enabled by default (see set_extended_precision).

Included (draft 'minimum physics'): Poisson, e/h continuity, SG currents, SRH,
doping+temperature dependent mobility, incomplete ionization (II), effective
interface charge (static sheet, optional single-level acceptor occupancy) and an
effective channel (surface) mobility.  NOT included: impact ionization,
self-heating, oxide degradation, Fermi-Dirac statistics, field-dependent mobility.
"""
from __future__ import annotations

import numpy as np
import devsim as ds

from .params import Q, EPS0, SiC4H, SiO2, Gate, gate_offset


# ----------------------------------------------------------------- helpers
def set_extended_precision(on: bool = True) -> None:
    for p in ("extended_solver", "extended_model", "extended_equation"):
        ds.set_parameter(name=p, value=bool(on))


def _nm(dev, reg, name, expr, *variables):
    ds.node_model(device=dev, region=reg, name=name, equation=expr)
    for v in variables:
        ds.node_model(device=dev, region=reg, name=f"{name}:{v}",
                      equation=f"simplify(diff({expr},{v}))")


def _em(dev, reg, name, expr, *variables):
    ds.edge_model(device=dev, region=reg, name=name, equation=expr)
    for v in variables:
        for s in ("n0", "n1"):
            ds.edge_model(device=dev, region=reg, name=f"{name}:{v}@{s}",
                          equation=f"simplify(diff({expr},{v}@{s}))")


def solution(dev, reg, name):
    ds.node_solution(device=dev, region=reg, name=name)
    ds.edge_from_node_model(device=dev, region=reg, node_model=name)


def set_node_array(dev, reg, name, values, as_solution=True):
    if as_solution and name not in ds.get_node_model_list(device=dev, region=reg):
        ds.node_solution(device=dev, region=reg, name=name)
    ds.set_node_values(device=dev, region=reg, name=name, values=[float(v) for v in values])


def node_array(dev, reg, name) -> np.ndarray:
    return np.array(ds.get_node_model_values(device=dev, region=reg, name=name))


# ------------------------------------------------------------- parameters
def set_sic_parameters(dev, reg, mat: SiC4H, T: float, interface: dict | None = None):
    d = mat.derived(T)
    p = dict(Permittivity=mat.eps_r * EPS0, ElectronCharge=Q, V_t=d["Vt"], n_i=d["ni"],
             n1D=d["n1D"], p1A=d["p1A"], gD=mat.gD, gA=mat.gA,
             taun=mat.taun, taup=mat.taup, n1=d["ni"], p1=d["ni"],
             mun_min=d["mun_min"], mun_max=d["mun_max"], mun_Nref=d["mun_Nref"],
             mun_delta=d["mun_delta"], mup_min=d["mup_min"], mup_max=d["mup_max"],
             mup_Nref=d["mup_Nref"], mup_delta=d["mup_delta"], mu_surf=d["mu_surf"])
    interface = interface or {}
    # static effective sheet charge: q*(Qf + Qit_eff) [C/cm^2]; signs: + = positive charge
    p["SigmaFixed"] = Q * (interface.get("qf_cm2", 0.0) + interface.get("qit_eff_cm2", 0.0))
    # optional single-level acceptor-like trap (occupancy by electron density)
    p["Nit_trap"] = interface.get("nit_trap_cm2", 0.0)
    p["n1T"] = d["Nc"] * np.exp(-interface.get("trap_Ec_minus_Et", 0.2) / d["Vt"])
    for k, v in p.items():
        ds.set_parameter(device=dev, region=reg, name=k, value=float(v))
    return d


def set_oxide_parameters(dev, reg, ox: SiO2):
    ds.set_parameter(device=dev, region=reg, name="Permittivity", value=ox.eps_r * EPS0)
    ds.set_parameter(device=dev, region=reg, name="ElectronCharge", value=Q)


# --------------------------------------------- equilibrium (neutral) potential
def neutral_potential(donors, acceptors, d: dict, ii: bool = True, iters: int = 200):
    """Charge-neutral equilibrium potential (intrinsic-level reference), vectorized bisection.

    Solves p - n + ND+ - NA- = 0 with n = ni e^{psi/Vt}, p = ni e^{-psi/Vt}.
    """
    donors = np.asarray(donors, float)
    acceptors = np.asarray(acceptors, float)
    Vt, ni = d["Vt"], d["ni"]
    lo = np.full_like(donors, -0.5 * d["Eg"] - 0.5)
    hi = np.full_like(donors, +0.5 * d["Eg"] + 0.5)

    def f(psi):
        n = ni * np.exp(psi / Vt)
        p = ni * np.exp(-psi / Vt)
        if ii:
            ndp = donors / (1.0 + d.get("gD", 2.0) * n / d["n1D"])
            nam = acceptors / (1.0 + d.get("gA", 4.0) * p / d["p1A"])
        else:
            ndp, nam = donors, acceptors
        return p - n + ndp - nam          # strictly decreasing in psi

    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        lo = np.where(fm > 0, mid, lo)
        hi = np.where(fm > 0, hi, mid)
    return 0.5 * (lo + hi)


# ------------------------------------------------------ semiconductor models
def _charge_terms(carrier_e: str, carrier_h: str, ii: bool, intf_mode: str) -> str:
    nd = f"Donors/(1 + gD*{carrier_e}/n1D)" if ii else "Donors"
    na = f"Acceptors/(1 + gA*{carrier_h}/p1A)" if ii else "Acceptors"
    rho = f"-ElectronCharge*kahan4({carrier_h}, -{carrier_e}, {nd}, -{na})"
    if intf_mode == "none":
        return rho
    sigma = "SigmaFixed"
    if intf_mode == "trap":
        sigma = f"(SigmaFixed - ElectronCharge*Nit_trap*{carrier_e}/({carrier_e} + n1T))"
    # sheet charge sigma [C/cm^2] distributed onto interface nodes: sigma*L_intf/NodeVolume
    return f"{rho} - {sigma}*IntfLen/NodeVolume"


def create_sic_potential_only(dev, reg, ii=True, intf_mode="static"):
    if "Potential" not in ds.get_node_model_list(device=dev, region=reg):
        solution(dev, reg, "Potential")
    _nm(dev, reg, "IntrinsicElectrons", "n_i*exp(Potential/V_t)", "Potential")
    _nm(dev, reg, "IntrinsicHoles", "n_i*exp(-Potential/V_t)", "Potential")
    _nm(dev, reg, "PotentialIntrinsicCharge",
        _charge_terms("IntrinsicElectrons", "IntrinsicHoles", ii, intf_mode), "Potential")
    _em(dev, reg, "ElectricField", "(Potential@n0-Potential@n1)*EdgeInverseLength", "Potential")
    _em(dev, reg, "PotentialEdgeFlux", "Permittivity*ElectricField", "Potential")
    ds.equation(device=dev, region=reg, name="PotentialEquation", variable_name="Potential",
                node_model="PotentialIntrinsicCharge", edge_model="PotentialEdgeFlux",
                variable_update="log_damp")


def create_mobility(dev, reg):
    ntot = "(Donors + Acceptors)"
    mub_n = f"(mun_min + (mun_max - mun_min)/(1 + pow({ntot}/mun_Nref, mun_delta)))"
    mub_p = f"(mup_min + (mup_max - mup_min)/(1 + pow({ntot}/mup_Nref, mup_delta)))"
    ds.node_model(device=dev, region=reg, name="MuNbulk", equation=mub_n)
    ds.node_model(device=dev, region=reg, name="MuN", equation=f"1/(1/MuNbulk + SurfFactor/mu_surf)")
    ds.node_model(device=dev, region=reg, name="MuP", equation=mub_p)
    for m in ("MuN", "MuP"):
        ds.edge_from_node_model(device=dev, region=reg, node_model=m)
    ds.edge_model(device=dev, region=reg, name="EdgeMuN", equation="0.5*(MuN@n0 + MuN@n1)")
    ds.edge_model(device=dev, region=reg, name="EdgeMuP", equation="0.5*(MuP@n0 + MuP@n1)")


def create_sic_drift_diffusion(dev, reg, ii=True, intf_mode="static", holes=True):
    """Drift-diffusion model.

    holes=True : bipolar (Potential, Electrons, Holes).
    holes=False: unipolar n-channel model - Potential + Electrons; holes stay in equilibrium with the
                 grounded source/body (phi_p = 0 -> p = n_i exp(-psi/V_t), node model
                 IntrinsicHoles).  Justified for n-channel MOSFET operation without impact
                 ionization / body-diode conduction (draft physics scope); removes the
                 ill-conditioned hole continuity equation (p ~ 1e-35 cm^-3 in n+ regions).
    """
    carriers = (("Electrons", "IntrinsicElectrons"), ("Holes", "IntrinsicHoles"))
    for c, init in (carriers if holes else carriers[:1]):
        if c not in ds.get_node_model_list(device=dev, region=reg):
            solution(dev, reg, c)
            ds.set_node_values(device=dev, region=reg, name=c, init_from=init)
    H = "Holes" if holes else "IntrinsicHoles"
    hv = ("Electrons", "Holes") if holes else ("Electrons", "Potential")
    create_mobility(dev, reg)
    # Poisson with full carrier dependence
    _nm(dev, reg, "PotentialNodeCharge", _charge_terms("Electrons", H, ii, intf_mode), *hv)
    ds.equation(device=dev, region=reg, name="PotentialEquation", variable_name="Potential",
                node_model="PotentialNodeCharge", edge_model="PotentialEdgeFlux",
                variable_update="log_damp")
    # SRH
    usrh = f"(Electrons*{H} - n_i^2)/(taup*(Electrons + n1) + taun*({H} + p1))"
    _nm(dev, reg, "USRH", usrh, *hv)
    _nm(dev, reg, "ElectronGeneration", "-ElectronCharge*USRH", *hv)
    # Bernoulli / SG currents
    _em(dev, reg, "vdiff", "(Potential@n0 - Potential@n1)/V_t", "Potential")
    ds.edge_model(device=dev, region=reg, name="Bern01", equation="B(vdiff)")
    ds.edge_model(device=dev, region=reg, name="Bern01:Potential@n0",
                  equation="dBdx(vdiff)*vdiff:Potential@n0")
    ds.edge_model(device=dev, region=reg, name="Bern01:Potential@n1",
                  equation="-Bern01:Potential@n0")
    jn = ("ElectronCharge*EdgeMuN*EdgeInverseLength*V_t*"
          "kahan3(Electrons@n1*Bern01, Electrons@n1*vdiff, -Electrons@n0*Bern01)")
    _em(dev, reg, "ElectronCurrent", jn, "Electrons", "Potential")
    _nm(dev, reg, "NCharge", "-ElectronCharge*Electrons", "Electrons")
    ds.equation(device=dev, region=reg, name="ElectronContinuityEquation", variable_name="Electrons",
                time_node_model="NCharge", edge_model="ElectronCurrent",
                node_model="ElectronGeneration", variable_update="positive")
    if holes:
        _nm(dev, reg, "HoleGeneration", "ElectronCharge*USRH", *hv)
        jp = ("-ElectronCharge*EdgeMuP*EdgeInverseLength*V_t*"
              "kahan3(Holes@n1*Bern01, -Holes@n0*Bern01, -Holes@n0*vdiff)")
        _em(dev, reg, "HoleCurrent", jp, "Holes", "Potential")
        _nm(dev, reg, "PCharge", "ElectronCharge*Holes", "Holes")
        ds.equation(device=dev, region=reg, name="HoleContinuityEquation", variable_name="Holes",
                    time_node_model="PCharge", edge_model="HoleCurrent",
                    node_model="HoleGeneration", variable_update="positive")


def create_oxide(dev, reg):
    if "Potential" not in ds.get_node_model_list(device=dev, region=reg):
        solution(dev, reg, "Potential")
    _em(dev, reg, "ElectricField", "(Potential@n0-Potential@n1)*EdgeInverseLength", "Potential")
    _em(dev, reg, "PotentialEdgeFlux", "Permittivity*ElectricField", "Potential")
    ds.equation(device=dev, region=reg, name="PotentialEquation", variable_name="Potential",
                edge_model="PotentialEdgeFlux", variable_update="default")


# ---------------------------------------------------------------- contacts
def bias_name(contact: str) -> str:
    return f"{contact}_bias"


def _contact_charge_edge(dev, reg):
    if "contactcharge_edge" not in ds.get_edge_model_list(device=dev, region=reg):
        _em(dev, reg, "contactcharge_edge", "Permittivity*ElectricField", "Potential")


def create_ohmic_contact(dev, reg, contact, dd=False, holes=True):
    """Ohmic BC using the neutral II-consistent equilibrium potential Psi_eq (node solution)."""
    bn = bias_name(contact)
    if bn not in ds.get_parameter_list(device=dev):
        ds.set_parameter(device=dev, name=bn, value=0.0)
    _contact_charge_edge(dev, reg)
    ds.contact_node_model(device=dev, contact=contact, name=f"{contact}_phi",
                          equation=f"Potential - Psi_eq - {bn}")
    ds.contact_node_model(device=dev, contact=contact, name=f"{contact}_phi:Potential", equation="1")
    ds.contact_equation(device=dev, contact=contact, name="PotentialEquation",
                        node_model=f"{contact}_phi", edge_charge_model="contactcharge_edge")
    if dd:
        ds.contact_node_model(device=dev, contact=contact, name=f"{contact}_n",
                              equation="Electrons - n_i*exp(Psi_eq/V_t)")
        ds.contact_node_model(device=dev, contact=contact, name=f"{contact}_n:Electrons", equation="1")
        ds.contact_equation(device=dev, contact=contact, name="ElectronContinuityEquation",
                            node_model=f"{contact}_n", edge_current_model="ElectronCurrent")
        if holes:
            ds.contact_node_model(device=dev, contact=contact, name=f"{contact}_p",
                                  equation="Holes - n_i*exp(-Psi_eq/V_t)")
            ds.contact_node_model(device=dev, contact=contact, name=f"{contact}_p:Holes", equation="1")
            ds.contact_equation(device=dev, contact=contact, name="HoleContinuityEquation",
                                node_model=f"{contact}_p", edge_current_model="HoleCurrent")


def create_gate_contact(dev, reg, contact, mat: SiC4H, gate: Gate, T: float):
    bn = bias_name(contact)
    if bn not in ds.get_parameter_list(device=dev):
        ds.set_parameter(device=dev, name=bn, value=0.0)
    ds.set_parameter(device=dev, name="GateOffset", value=gate_offset(mat, gate, T))
    _contact_charge_edge(dev, reg)
    ds.contact_node_model(device=dev, contact=contact, name=f"{contact}_phi",
                          equation=f"Potential - {bn} + GateOffset")
    ds.contact_node_model(device=dev, contact=contact, name=f"{contact}_phi:Potential", equation="1")
    ds.contact_equation(device=dev, contact=contact, name="PotentialEquation",
                        node_model=f"{contact}_phi", edge_charge_model="contactcharge_edge")


def create_oxide_interface(dev, interface):
    ds.interface_model(device=dev, interface=interface, name="continuousPotential",
                       equation="Potential@r0-Potential@r1")
    ds.interface_model(device=dev, interface=interface, name="continuousPotential:Potential@r0",
                       equation="1")
    ds.interface_model(device=dev, interface=interface, name="continuousPotential:Potential@r1",
                       equation="-1")
    ds.interface_equation(device=dev, interface=interface, name="PotentialEquation",
                          interface_model="continuousPotential", type="continuous")


def contact_current(dev, contact) -> float:
    i = ds.get_contact_current(device=dev, contact=contact, equation="ElectronContinuityEquation")
    try:
        i += ds.get_contact_current(device=dev, contact=contact, equation="HoleContinuityEquation")
    except ds.error:
        pass                                  # unipolar model: no hole equation
    return i


def contact_charge(dev, contact) -> float:
    return ds.get_contact_charge(device=dev, contact=contact, equation="PotentialEquation")
