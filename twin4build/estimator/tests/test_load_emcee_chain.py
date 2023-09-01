import matplotlib.pyplot as plt
import matplotlib
import pickle
import math
import numpy as np
import os
import datetime
import sys
import corner
import seaborn as sns
if __name__ == '__main__':
    uppath = lambda _path,n: os.sep.join(_path.split(os.sep)[:-n])
    file_path = uppath(os.path.abspath(__file__), 4)
    sys.path.append(file_path)
from twin4build.utils.uppath import uppath
from twin4build.estimator.estimator import Estimator
from twin4build.model.model import Model
from test_estimator import extend_model
def test():
    flat_attr_list = ["m1_flow_nominal", "m2_flow_nominal", "tau1", "tau2", "tau_m", "nominalUa.hasValue", "workingPressure.hasValue", "flowCoefficient.hasValue", "waterFlowRateMax", "c1", "c2", "c3", "c4", "eps_motor", "f_motorToAir", "kp", "Ti", "Td"]
    flat_attr_list = [r"$\dot{m}_{w,nom}$", r"$\dot{m}_{a,nom}$", r"$\tau_1$", r"$\tau_2$", r"$\tau_m$", r"$UA_{nom}$", r"$\Delta P_{v,nom}$", r"$K_{v}$", r"$\dot{m}_{w,nom}$", r"$c_1$", r"$c_2$", r"$c_3$", r"$c_4$", r"$\epsilon$", r"$f_{motorToAir}$", r"$K_p$", r"$T_i$", r"$T_d$"]

    colors = sns.color_palette("deep")
    blue = colors[0]
    orange = colors[1]
    green = colors[2]
    red = colors[3]
    purple = colors[4]
    brown = colors[5]
    pink = colors[6]
    grey = colors[7]
    beis = colors[8]
    sky_blue = colors[9]
    # load_params()

    do_plot = True
    do_inference = False

    # loaddir = os.path.join(uppath(os.path.abspath(__file__), 2), "chain_logs", "20230829_155706_chain_log.pickle")
    loaddir = os.path.join(uppath(os.path.abspath(__file__), 2), "chain_logs", "20230830_194210_chain_log.pickle")
    with open(loaddir, 'rb') as handle:
        result = pickle.load(handle)

    list_ = ["chain.logl", "chain.logP", "chain.x", "chain.betas"]
    for key in list_:
        result[key] = np.concatenate(result[key],axis=0)

    for key in result.keys():
        if key not in list_:
            result[key] = np.array(result[key])


    print(f"chain.swaps_proposed: {result['chain.swaps_proposed']}")
    print(f"chain.swaps_accepted: {result['chain.swaps_accepted']}")

    print(f"chain.jumps_proposed: {result['chain.jumps_proposed']}")
    print(f"chain.jumps_accepted: {result['chain.jumps_accepted']}")

    ndim = result["chain.x"].shape[3]
    ntemps = result["chain.x"].shape[1]
    nwalkers = result["chain.x"].shape[2] #Round up to nearest even number and multiply by 2

    assert len(flat_attr_list) == ndim, "Number of parameters in flat_attr_list does not match number of parameters in chain.x"
    
    plt.rcParams['mathtext.fontset'] = 'cm'

    nparam = len(flat_attr_list)
    ncols = 3
    nrows = math.ceil(nparam/ncols)
    fig_trace_beta, axes_trace = plt.subplots(nrows=nrows, ncols=ncols, layout='compressed')
    fig_trace_beta.set_size_inches((17, 12))
    # fig_trace_beta.suptitle("Parameter trace plots")

    
    nsample = 500
    burnin = 500
    nsample_checkpoint = 50
    cm = plt.get_cmap('RdYlBu', ntemps)
    cb = None
    n_checkpoint = int(np.floor(nsample/nsample_checkpoint))
    

    # list_ = ["chain.logl", "chain.logP", "chain.x", "chain.betas"]
    # for key in list_:
    #     for i, arr in enumerate(result[key]):
    #         result[key][i] = arr[-nsample_checkpoint:]
        
    # for key in result.keys():
    #     result[key] = np.concatenate(result[key],axis=0)
        # result["chain.jumps_accepted"].append(chain.jumps_accepted)
        # result["chain.jumps_proposed"].append(chain.jumps_proposed)
        # result["chain.logl"].append(chain.logl)
        # result["chain.logP"].append(chain.logP)
        # result["chain.swaps_accepted"].append(chain.swaps_accepted)
        # result["chain.swaps_proposed"].append(chain.swaps_proposed)
        # result["chain.x"].append(chain.x)
        # result["chain.betas"].append(chain.betas)
    if do_plot:
        chain_logl = result["chain.logl"]
        bool_ = chain_logl<-5e+9
        chain_logl[bool_] = np.nan
        chain_logl[np.isnan(chain_logl)] = np.nanmin(chain_logl)

        logl_min = np.min(chain_logl)
        logl_max = np.max(chain_logl)
        min_alpha = 0.1
        max_alpha = 1
        vmin = np.min(result["chain.betas"])
        vmax = np.max(result["chain.betas"])
        for nt in reversed(range(ntemps)):
            for nw in range(nwalkers):
                x = result["chain.x"][:, nt, nw, :]
                betas = result["chain.betas"][:, nt]
                logl = chain_logl[:, nt, nw]
                # alpha = (max_alpha-min_alpha)*(logl-logl_min)/(logl_max-logl_min) + min_alpha
                alpha = (max_alpha-min_alpha)*(betas-vmin)/(vmax-vmin) + min_alpha
                # Trace plots
                
                
                for j, attr in enumerate(flat_attr_list):
                    row = math.floor(j/ncols)
                    col = int(j-ncols*row)
                    sc = axes_trace[row, col].scatter(range(result["chain.betas"].shape[0]), x[:,j], c=betas, vmin=vmin, vmax=vmax, s=4, cmap=cm, alpha=alpha)
                    axes_trace[row, col].axvline(burnin, color="black", linestyle="--", linewidth=2, alpha=0.8)

                    # if plotted==False:
                    #     axes_trace[row, col].text(x_left+dx/2, 0.44, 'Burnin', ha='center', va='center', rotation='horizontal', fontsize=15, transform=axes_trace[row, col].transAxes)
                    #     axes_trace[row, col].arrow(x_right, 0.5, -dx, 0, head_width=0.1, head_length=0.05, color="black", transform=axes_trace[row, col].transAxes)
                    #     axes_trace[row, col].arrow(x_left, 0.5, dx, 0, head_width=0.1, head_length=0.05, color="black", transform=axes_trace[row, col].transAxes)
                    #     axes_trace[row, col].set_ylabel(attr, fontsize=20)
                    #     plotted = True

        x_right = 0.515
        x_left = 0.1
        dx = x_right-x_left
        for j, attr in enumerate(flat_attr_list):
            row = math.floor(j/ncols)
            col = int(j-ncols*row)

            axes_trace[row, col].axvline(burnin, color="black", linestyle="--", linewidth=2, alpha=0.8)
            axes_trace[row, col].text(x_left+dx/2, 0.44, 'Burnin', ha='center', va='center', rotation='horizontal', fontsize=15, transform=axes_trace[row, col].transAxes)
            axes_trace[row, col].arrow(x_right, 0.5, -dx, 0, head_width=0.1, head_length=0.05, color="black", transform=axes_trace[row, col].transAxes)
            axes_trace[row, col].arrow(x_left, 0.5, dx, 0, head_width=0.1, head_length=0.05, color="black", transform=axes_trace[row, col].transAxes)
            axes_trace[row, col].set_ylabel(attr, fontsize=20)
        
        # fig_trace.legend(labels, loc='lower right', bbox_to_anchor=(1,-0.1), ncol=len(labels))#, bbox_transform=fig.transFigure)
        cb = fig_trace_beta.colorbar(sc, ax=axes_trace)
        cb.set_label(label=r"$\beta = \frac{1}{T}$", size=30)#, weight='bold')
        cb.solids.set(alpha=1)
        # fig_trace_beta.tight_layout()
        dist = (vmax-vmin)/(ntemps)/2
        tick_start = vmin+dist
        tick_end = vmax-dist
        tick_locs = np.linspace(tick_start, tick_end, ntemps)[::-1]
        cb.set_ticks(tick_locs)
        ticklabels = [str(round(float(label), 2)) for label in result["chain.betas"][0,:] if label!='']
        cb.set_ticklabels(ticklabels, size=12)

        parameter_chain = result["chain.x"][burnin:,0,:,:]
        corner.corner(parameter_chain, labels=flat_attr_list, show_titles=True, plot_contours=True, bins=100, max_n_ticks=3,)
        plt.show()

    # color = cm(1)
    # fig_trace_loglike, axes_trace_loglike = plt.subplots(nrows=1, ncols=1)
    # fig_trace_loglike.set_size_inches((17, 12))
    # fig_trace_loglike.suptitle("Trace plots of log likelihoods")
    # vmin = np.nanmin(-chain_logl)
    # vmax = np.nanmax(-chain_logl)
    # for nt in range(1):
    #     for nw in range(nwalkers):
    #         logl = chain_logl[:, nt, nw]
    #         axes_trace_loglike.scatter(range(logl.shape[0]), -logl, color=color, s=4, alpha=0.8)
    # axes_trace_loglike.set_yscale("log")
    # plt.show()
    if do_inference:
        startPeriod = datetime.datetime(year=2022, month=2, day=1, hour=8, minute=0, second=0)
        endPeriod = datetime.datetime(year=2022, month=2, day=1, hour=21, minute=0, second=0)
        stepSize = 600
        Model.extend_model = extend_model
        model = Model(id="model", saveSimulationResult=True)
        model.load_model(infer_connections=False)
        estimator = Estimator(model)


        coil = model.component_dict["coil"]
        valve = model.component_dict["valve"]
        fan = model.component_dict["fan"]
        controller = model.component_dict["controller"]

        targetParameters = {coil: ["m1_flow_nominal", "m2_flow_nominal", "tau1", "tau2", "tau_m", "nominalUa.hasValue"],
                                        valve: ["workingPressure.hasValue", "flowCoefficient.hasValue", "waterFlowRateMax"],
                                        fan: ["c1", "c2", "c3", "c4", "eps_motor", "f_motorToAir"],
                                        controller: ["kp", "Ti", "Td"]}
                
        percentile = 3
        targetMeasuringDevices = {model.component_dict["coil outlet air temperature sensor"]: {"standardDeviation": 0.5/percentile},
                                    model.component_dict["coil outlet water temperature sensor"]: {"standardDeviation": 0.5/percentile},
                                    model.component_dict["fan power meter"]: {"standardDeviation": 50/percentile},
                                    model.component_dict["valve position sensor"]: {"standardDeviation": 0.01/percentile}}

        
        parameter_chain = result["chain.x"][burnin:,0,:,:]
        parameter_chain = parameter_chain.reshape((parameter_chain.shape[0]*parameter_chain.shape[1], parameter_chain.shape[2]))
        estimator.run_emcee_inference(model, parameter_chain, targetParameters, targetMeasuringDevices, startPeriod, endPeriod, stepSize)

if __name__ == '__main__':
    test()