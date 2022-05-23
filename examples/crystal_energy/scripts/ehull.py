from copy import deepcopy

import numpy as np
import re
from scripts import stability
from scripts import nrelmatdbtaps


# --------------------------------------------------------------------------------------------
# function to alphabetically sort the composition e.g., Li1Sc1F4 would be F4Li1Sc1
# and also get the individual elements in the composition
def sort_comp(comp):
    # split by the digits
    # e.g., for "Li1Sc1F4": ['Li', '1', 'Sc', '1', 'F', '4', '']
    split = np.asarray(re.split('(\d+)', comp))
    ele_stoichs = [''.join(split[i:i+2]) for i in range(0, len(split), 2)]
    sorted_comp = ''.join(sorted(ele_stoichs))
    # also return the elements
    elements = tuple(sorted(split[range(0, len(split) - 1, 2)]))
    return sorted_comp, elements


# --------------------------------------------------------------------------------------------
# function to compute the decomposition energy for a given composition 
def convex_hull_stability(comp,
                          predicted_energy,
                          df_competing_phases,
                          inputs_file=None,
                          out_file=None):
    """
    :param comp: composition such as Li1Sc1F4
    :param predicted_energy: predicted eV/atom for the structure corresponding to this composition
    :param df_competing_phases: pandas dataframe of competing phases used to 
        construct the convex hull for the elements of the given composition
    :param inputs_file: write the statistics necessary for the convex hull analysis to a file. 
        Only contains composition-level information
    :param out_file: write the results of the stability analysis.
    """
    comp, eles = sort_comp(comp)

    df_cp = df_competing_phases.copy()
    # UPDATE: if the composition is already in ICSD,
    # then just compare the total energy directly
    if comp in df_cp.reduced_composition.values:
        competing_energy = df_cp.set_index(
            'reduced_composition').loc[comp].energyperatom
        decomp_energy = predicted_energy - competing_energy
        return decomp_energy
    else:
        df_cp = df_cp.append({'sortedformula': comp,
                              'energyperatom': predicted_energy,
                              'reduced_composition': comp},
                             ignore_index=True)

    # Create input file for stability analysis
    inputs = nrelmatdbtaps.create_input_DFT(eles, df_cp, chempot='ferev2')
    # if this function failed to create the input, then skip this structure
    if inputs is None:
        return

    # The inputs used to be written to a file, and then read back in.
    # I updated the functions to store the inputs in a list, and then parse that list 
    if inputs_file is not None:
        print(f"writing {inputs_file}")
        with open(inputs_file, 'w') as out:
            out.write('\n'.join(inputs) + '\n')

    # Run stability function (args: input filename, composition)
    try:
        stable_state = stability.run_stability(inputs, comp, out_file=out_file)
        stoic = frac_stoic(comp)
        if stable_state == 'UNSTABLE':
            hull_nrg = stability_nrg(stoic, comp, inputs, stable=False)
        elif stable_state == 'STABLE':
            hull_nrg = stability_nrg(stoic, comp, inputs, stable=True)
        else:
            print(f"ERR: unrecognized stable_state: '{stable_state}'.")
            print(f"\tcomp: {comp}")
            return
    except SystemError as e:
        print(e)
        print(f"Failed at stability.run_stability for {comp} "
              f"(pred_energy: {predicted_energy}). Skipping\n")
        return
    return hull_nrg


# --------------------------------------------------------------------------------------------
# function to calculate fractional stoichiometry using sortedformula
# e.g., sortedformula = 'Na1Cl1', frac = [0.5,0.5]
def frac_stoic(sortedformula):
    comp_, stoic_ = stability.split_formula(sortedformula)
    stoic_ = list(map(int, stoic_))
    frac = list(np.zeros(len(stoic_)))
    for zz in range(len(frac)):
        frac[zz] = stoic_[zz] / sum(stoic_)
    return frac


# ------------------------------------------------------------------------------------------------------------------
# function to compute decomposition energy for a STABLE or UNSTABLE phase
# (args: fractional stoichiometry and phase)
# stable: if unstable, slowly decrease the discrete energies from above until stability is reached
# if stable, slowly increase until unstability is reached
def stability_nrg(stoich, phase, inputs, stable=False):
    stoich_dummy = deepcopy(stoich)

    A_, B, els_, stoich_ = stability.read_input(inputs)  # read input file for stoichiometry list

    for j in range(len(A_)):  # loop over all stoichiometries in A_ to find the phase of interest
        if list(A_[j]) == stoich:
            index = j

    original_nrg = B[index]  # save the original formation energy corresponding index found in the above loop

    discrete_nrgs = np.arange(0.001, 6.002, 0.002)  # discretize formation energies
    for jj in range(len(discrete_nrgs)):
        if stable:
            # if the structure is already stable, 
            # then increase the energy untill its unstable
            discrete_nrgs[jj] = B[index] + discrete_nrgs[jj]
        else:
            # if its unstable, then decrease the energy until its stable
            discrete_nrgs[jj] = B[index] - discrete_nrgs[jj]

    Hd = None
    # for each discretized formation energy, check if the opposite stability is achieved
    for ii in range(len(discrete_nrgs)):
        B[index] = discrete_nrgs[ii]
        new_stability = stability.run_stability(inputs, phase, B=B) 
        if stable and new_stability == 'UNSTABLE':
            Hd = original_nrg - discrete_nrgs[ii]
            break
        elif not stable and new_stability == 'STABLE':
            Hd = original_nrg - discrete_nrgs[ii]
            break
    #print(f"{stable = } switched: {original_nrg =} to {B[index] =}.")
    #print(f"{ii = }, {discrete_nrgs[ii] = }, {Hd =}")

    return Hd


'''
#--------------------------------------------------------------
# loop over all structures to compute DFT energy above the hull
for i in range(len(df)):
     if df.DFT_stability[i] == 'UNSTABLE':
         stoic = frac_stoic(df.alphabetical_formula[i])
         nrg_hull = e_hull_DFT(stoic,df.alphabetical_formula[i])
         df['ehull_DFT'].values[i] = nrg_hull

     else:
         stoic = frac_stoic(df.alphabetical_formula[i])
         nrg_hull = Hd_DFT(stoic,df.alphabetical_formula[i])
         df['ehull_DFT'].values[i] = nrg_hull
     


# loop over all structures to compute predicted energy above the hull
for i in range(len(df)):
     if df.predicted_stability[i] == 'UNSTABLE':
         stoic = frac_stoic(df.alphabetical_formula[i])
         nrg_hull = e_hull_pred(stoic,df.alphabetical_formula[i])
         df['ehull_predicted'].values[i] = nrg_hull

     else:
         stoic = frac_stoic(df.alphabetical_formula[i])
         nrg_hull = Hd_pred(stoic,df.alphabetical_formula[i])
         df['ehull_predicted'].values[i] = nrg_hull


df.to_parquet('decomposition.parquet',index=False)
'''
