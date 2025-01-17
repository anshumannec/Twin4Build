#standard
import os
import time
import matplotlib.pyplot as plt
# from IPython import display
from typing import List, Tuple
import numpy as np
import math
import sys
import time
import pickle
import tqdm
from decimal import Decimal
import pandas as pd

#torch
import torch
import torch.jit as jit
from torch import Tensor
from torch.utils.data import Dataset
from torch.utils.data import DataLoader
import shap

###Only for testing before distributing package
if __name__ == '__main__':
    uppath = lambda _path,n: os.sep.join(_path.split(os.sep)[:-n])
    file_path = uppath(os.path.abspath(__file__), 4)
    sys.path.append(file_path)

from twin4build.saref4bldg.building_space.building_space_adjacent_system import LSTM
from twin4build.saref4bldg.building_space.building_space_adjacent_system import LSTM_NALU
from twin4build.utils.uppath import uppath
from twin4build.logger.Logging import Logging

logger = Logging.get_logger("ai_logfile")
logger.disabled = True
DEVICE = "cpu"
def min_max_norm(y,y_min,y_max,low,high):
    logger.info("[Trainer] : Entered in Mix Max Norm Function")
    y = (y-y_min)/(y_max-y_min)*(high-low) + low
    logger.info("[Trainer] : Entered in Mix Max Norm Function")
    return y

def rescale(y,y_min,y_max,low,high):
    logger.info("[Trainer] : Entered in Rescale Function")
    y = (y-low)/(high-low)*(y_max-y_min) + y_min
    logger.info("[Trainer] : Entered in Rescale Function")
    return y


class Dataset(Dataset):
    def __init__(self, dataset_path):
        logger.info("[Trainer.Dataset] : Entered in Initialise Function")
        logger.info(f"LOADED: {dataset_path}")
        loaded = np.load(dataset_path)
        input = torch.Tensor(loaded[loaded.files[0]])
        output = torch.Tensor(loaded[loaded.files[1]])

        self.input_raw = input.to(DEVICE)
        self.input = input.to(DEVICE)
        self.output = output.to(DEVICE)

        self.input = self.input[:,:-1]
        self.output = self.output[:,1:]-self.output[:,:-1]
        logger.info("[Trainer.Dataset] : Exited from Initialise Function")

    def __len__(self):
        return self.output.shape[0]

    def __getitem__(self, idx):
        input = self.input[idx,:,:]
        output = self.output[idx,:,:]
        return input, output
    


class Trainer:
    '''
        It loads the network and optimizer state if the load parameter is set to True. 
        The model is an instance of an LSTM with a specific set of hyperparameters. 
        The class also contains a loss function for training, and another loss function for testing.
        Finally, the method sets up the optimizer to use for training the model.
    '''
    def __init__(self, space_name, load=True, hyperparameters=None):
        
        logger.info("[Trainer.Trainer] : Entered in Initialise Function")
        self.warmup_steps = 10
        self.space_name = space_name
        self.best_loss_diff_max = 1000
        self.max_it_stop = 10000000
        self.learning_rate = float(hyperparameters["learning_rate"])
        self.batch_size = hyperparameters["batch_size"]
        self.n_output = 1
        self.n_input = (2,5,3,3)
        self.n_lstm_hidden = tuple([hyperparameters["n_hidden"]]*4)
        # self.n_lstm_hidden = self.n_input
        self.n_lstm_layers = tuple([hyperparameters["n_layer"]]*4)
        self.dropout = 0.


        self.dataset_folder = os.path.join(uppath(os.path.abspath(__file__), 3), "test", "data", "time_series_data", "space_model_dataset")
        self.train_dataset_path = os.path.join(self.dataset_folder, f"{self.space_name}_training.npz")
        self.validation_dataset_path = os.path.join(self.dataset_folder, f"{self.space_name}_validation.npz")
        # self.test_dataset_path = os.path.join(self.dataset_folder, f"{self.space_name}_test.npz")
        self.train_dataset = Dataset(self.train_dataset_path)
        self.validation_dataset = Dataset(self.validation_dataset_path)
        # self.test_dataset = Dataset(self.test_dataset_path)
        self.train_dataloader = DataLoader(self.train_dataset, batch_size=self.batch_size, shuffle=True, drop_last=True)

        self.saved_result_path = os.path.join(uppath(os.path.abspath(__file__), 1), "grid_search_result_new_Dec_to_Jan.json")
        self.saved_serialized_networks_path = os.path.join(uppath(os.path.abspath(__file__), 1), "serialized_networks")
        self.saved_networks_path = os.path.join(uppath(os.path.abspath(__file__), 1), "saved_networks")

        os.chdir(self.saved_networks_path)
        


        self.load_min_max_scale_values()
        self.model = LSTM_NALU(self.n_input, self.n_lstm_hidden, self.n_lstm_layers, self.n_output, self.dropout, self.scaling_value_dict).to(DEVICE)
        self.model.train()

        # self.optimizer = torch.optim.NAdam(self.model.parameters(), lr=self.learning_rate)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)
        # self.optimizer = torch.optim.SGD(self.model.parameters(), lr=self.learning_rate)
        self.loss_train = self.loss_penalized
        self.loss_test = torch.nn.MSELoss()
        model_type = "B%d_LR%s_H%s_L%s" % (self.batch_size,'%.0E' % Decimal(hyperparameters["learning_rate"]),hyperparameters["n_hidden"],hyperparameters["n_layer"])

        self.network_filename_load = self.space_name + "_Network_" + model_type + ".pt"
        self.optimizer_filename_load = self.space_name + "_Optimizer_" + model_type + ".pt"

        self.network_filename_save = self.space_name + "_Network_" + model_type + ".pt"
        self.optimizer_filename_save = self.space_name + "_Optimizer_" + model_type + ".pt"

        self.step_train_filename_load = self.space_name + "_step_train_" + model_type + ".npy"
        self.prec_train_filename_load = self.space_name + "_prec_train_" + model_type + ".npy"

        self.step_train_filename_save = self.space_name + "_step_train_" + model_type + ".npy"
        self.prec_train_filename_save = self.space_name + "_prec_train_" + model_type + ".npy"

        self.step_test_filename_load = self.space_name + "_step_test_" + model_type + ".npy"
        self.prec_test_filename_load = self.space_name + "_prec_test_" + model_type + ".npy"

        self.step_test_filename_save = self.space_name + "_step_test_" + model_type + ".npy"
        self.prec_test_filename_save = self.space_name + "_prec_test_" + model_type + ".npy"

        self.running_validation_loss_filename_load = self.space_name + "_running_validation_loss.npy"
        self.running_validation_loss_filename_save = self.space_name + "_running_validation_loss.npy"

        self.running_validation_loss_model_name_filename_load = self.space_name + "_running_validation_loss_model_name.npy"
        self.running_validation_loss_model_name_filename_save = self.space_name + "_running_validation_loss_model_name.npy"

        if load==True:
            os.chdir(self.saved_networks_path)
            self.model.load_state_dict(torch.load(self.network_filename_load,map_location=torch.device(DEVICE)))
            self.optimizer.load_state_dict(torch.load(self.optimizer_filename_load,map_location=torch.device(DEVICE)))

            self.step_train = np.load(self.step_train_filename_load, allow_pickle=True).tolist()
            self.prec_train = np.load(self.prec_train_filename_load, allow_pickle=True).tolist()

            self.step_test = np.load(self.step_test_filename_load, allow_pickle=True).tolist()
            self.prec_test = np.load(self.prec_test_filename_load, allow_pickle=True).tolist()

            os.chdir(self.saved_serialized_networks_path)

            self.running_validation_loss = np.load(self.running_validation_loss_filename_load, allow_pickle=True).tolist()
            self.running_validation_loss_model_name = np.load(self.running_validation_loss_model_name_filename_load, allow_pickle=True).tolist()

            os.chdir(self.saved_networks_path)

            self.n_step = self.step_train[-1]
        else:
            load_pretrained_model = False   
            if load_pretrained_model:
                print(os.getcwd())
                print(os.listdir())
                self.model.load_state_dict(torch.load(self.network_filename_load,map_location=torch.device(DEVICE)))
            
            self.step_train = []
            self.prec_train = [] 
            self.step_test = []
            self.prec_test = [] 
            self.running_validation_loss = []
            self.running_validation_loss_model_name = []
            self.n_step = 0
        pytorch_total_params = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        print("TOTAL NUMBER OF PARAMETERS IN MODEL: " + str(pytorch_total_params))

        self.n_step_start = self.n_step

        for param_group in self.optimizer.param_groups:
            param_group['lr'] = self.learning_rate

        self.do_test = True
        self.extract_model = True

        self.n_test = 10#math.ceil(len(self.train_dataset)/self.batch_size)

        h_0_input_layer_OUTDOORTEMPERATURE = torch.zeros((self.n_lstm_layers[0],self.batch_size,self.n_lstm_hidden[0])).to(DEVICE)
        c_0_input_layer_OUTDOORTEMPERATURE = torch.zeros((self.n_lstm_layers[0],self.batch_size,self.n_lstm_hidden[0])).to(DEVICE)
        h_0_hidden_layer_OUTDOORTEMPERATURE = torch.zeros((self.n_lstm_layers[0],self.batch_size,self.n_lstm_hidden[0])).to(DEVICE)
        c_0_hidden_layer_OUTDOORTEMPERATURE = torch.zeros((self.n_lstm_layers[0],self.batch_size,self.n_lstm_hidden[0])).to(DEVICE)
        h_0_output_layer_OUTDOORTEMPERATURE = torch.zeros((1,self.batch_size,self.n_output)).to(DEVICE)
        c_0_output_layer_OUTDOORTEMPERATURE = torch.zeros((1,self.batch_size,self.n_output)).to(DEVICE)
        hidden_state_input_OUTDOORTEMPERATURE = (h_0_input_layer_OUTDOORTEMPERATURE,c_0_input_layer_OUTDOORTEMPERATURE)
        hidden_state_hidden_OUTDOORTEMPERATURE = (h_0_hidden_layer_OUTDOORTEMPERATURE,c_0_hidden_layer_OUTDOORTEMPERATURE)
        hidden_state_output_OUTDOORTEMPERATURE = (h_0_output_layer_OUTDOORTEMPERATURE,c_0_output_layer_OUTDOORTEMPERATURE)

        h_0_input_layer_RADIATION = torch.zeros((self.n_lstm_layers[1],self.batch_size,self.n_lstm_hidden[1])).to(DEVICE)
        c_0_input_layer_RADIATION = torch.zeros((self.n_lstm_layers[1],self.batch_size,self.n_lstm_hidden[1])).to(DEVICE)
        h_0_hidden_layer_RADIATION = torch.zeros((self.n_lstm_layers[1],self.batch_size,self.n_lstm_hidden[1])).to(DEVICE)
        c_0_hidden_layer_RADIATION = torch.zeros((self.n_lstm_layers[1],self.batch_size,self.n_lstm_hidden[1])).to(DEVICE)
        h_0_output_layer_RADIATION = torch.zeros((1,self.batch_size,self.n_output)).to(DEVICE)
        c_0_output_layer_RADIATION = torch.zeros((1,self.batch_size,self.n_output)).to(DEVICE)
        hidden_state_input_RADIATION = (h_0_input_layer_RADIATION,c_0_input_layer_RADIATION)
        hidden_state_hidden_RADIATION = (h_0_hidden_layer_RADIATION,c_0_hidden_layer_RADIATION)
        hidden_state_output_RADIATION = (h_0_output_layer_RADIATION,c_0_output_layer_RADIATION)

        h_0_input_layer_SPACEHEATER = torch.zeros((self.n_lstm_layers[2],self.batch_size,self.n_lstm_hidden[2])).to(DEVICE)
        c_0_input_layer_SPACEHEATER = torch.zeros((self.n_lstm_layers[2],self.batch_size,self.n_lstm_hidden[2])).to(DEVICE)
        h_0_hidden_layer_SPACEHEATER = torch.zeros((self.n_lstm_layers[2],self.batch_size,self.n_lstm_hidden[2])).to(DEVICE)
        c_0_hidden_layer_SPACEHEATER = torch.zeros((self.n_lstm_layers[2],self.batch_size,self.n_lstm_hidden[2])).to(DEVICE)
        h_0_output_layer_SPACEHEATER = torch.zeros((1,self.batch_size,self.n_output)).to(DEVICE)
        c_0_output_layer_SPACEHEATER = torch.zeros((1,self.batch_size,self.n_output)).to(DEVICE)
        hidden_state_input_SPACEHEATER = (h_0_input_layer_SPACEHEATER,c_0_input_layer_SPACEHEATER)
        hidden_state_hidden_SPACEHEATER = (h_0_hidden_layer_SPACEHEATER,c_0_hidden_layer_SPACEHEATER)
        hidden_state_output_SPACEHEATER = (h_0_output_layer_SPACEHEATER,c_0_output_layer_SPACEHEATER)

        h_0_input_layer_VENTILATION = torch.zeros((self.n_lstm_layers[3],self.batch_size,self.n_lstm_hidden[3])).to(DEVICE)
        c_0_input_layer_VENTILATION = torch.zeros((self.n_lstm_layers[3],self.batch_size,self.n_lstm_hidden[3])).to(DEVICE)
        h_0_hidden_layer_VENTILATION = torch.zeros((self.n_lstm_layers[3],self.batch_size,self.n_lstm_hidden[3])).to(DEVICE)
        c_0_hidden_layer_VENTILATION = torch.zeros((self.n_lstm_layers[3],self.batch_size,self.n_lstm_hidden[3])).to(DEVICE)
        h_0_output_layer_VENTILATION = torch.zeros((1,self.batch_size,self.n_output)).to(DEVICE)
        c_0_output_layer_VENTILATION = torch.zeros((1,self.batch_size,self.n_output)).to(DEVICE)
        hidden_state_input_VENTILATION = (h_0_input_layer_VENTILATION,c_0_input_layer_VENTILATION)
        hidden_state_hidden_VENTILATION = (h_0_hidden_layer_VENTILATION,c_0_hidden_layer_VENTILATION)
        hidden_state_output_VENTILATION = (h_0_output_layer_VENTILATION,c_0_output_layer_VENTILATION)

        self.hidden_state_train = (hidden_state_input_OUTDOORTEMPERATURE,
                            hidden_state_output_OUTDOORTEMPERATURE,
                            hidden_state_input_RADIATION,
                            hidden_state_output_RADIATION,
                            hidden_state_input_SPACEHEATER,
                            hidden_state_output_SPACEHEATER,
                            hidden_state_input_VENTILATION,
                            hidden_state_output_VENTILATION)
        # self.hidden_state_train = (hidden_state_input_OUTDOORTEMPERATURE,
        #                             hidden_state_hidden_OUTDOORTEMPERATURE,
        #                             hidden_state_output_OUTDOORTEMPERATURE,
        #                             hidden_state_input_RADIATION,
        #                             hidden_state_hidden_RADIATION,
        #                             hidden_state_output_RADIATION,
        #                             hidden_state_input_SPACEHEATER,
        #                             hidden_state_hidden_SPACEHEATER,
        #                             hidden_state_output_SPACEHEATER,
        #                             hidden_state_input_VENTILATION,
        #                             hidden_state_hidden_VENTILATION,
        #                             hidden_state_output_VENTILATION)
        
        h_0_input_layer_OUTDOORTEMPERATURE = torch.zeros((self.n_lstm_layers[0],len(self.validation_dataset),self.n_lstm_hidden[0])).to(DEVICE)
        c_0_input_layer_OUTDOORTEMPERATURE = torch.zeros((self.n_lstm_layers[0],len(self.validation_dataset),self.n_lstm_hidden[0])).to(DEVICE)
        h_0_hidden_layer_OUTDOORTEMPERATURE = torch.zeros((self.n_lstm_layers[0],len(self.validation_dataset),self.n_lstm_hidden[0])).to(DEVICE)
        c_0_hidden_layer_OUTDOORTEMPERATURE = torch.zeros((self.n_lstm_layers[0],len(self.validation_dataset),self.n_lstm_hidden[0])).to(DEVICE)
        h_0_output_layer_OUTDOORTEMPERATURE = torch.zeros((1,len(self.validation_dataset),self.n_output)).to(DEVICE)
        c_0_output_layer_OUTDOORTEMPERATURE = torch.zeros((1,len(self.validation_dataset),self.n_output)).to(DEVICE)
        hidden_state_input_OUTDOORTEMPERATURE = (h_0_input_layer_OUTDOORTEMPERATURE,c_0_input_layer_OUTDOORTEMPERATURE)
        hidden_state_hidden_OUTDOORTEMPERATURE = (h_0_hidden_layer_OUTDOORTEMPERATURE,c_0_hidden_layer_OUTDOORTEMPERATURE)
        hidden_state_output_OUTDOORTEMPERATURE = (h_0_output_layer_OUTDOORTEMPERATURE,c_0_output_layer_OUTDOORTEMPERATURE)

        h_0_input_layer_RADIATION = torch.zeros((self.n_lstm_layers[1],len(self.validation_dataset),self.n_lstm_hidden[1])).to(DEVICE)
        c_0_input_layer_RADIATION = torch.zeros((self.n_lstm_layers[1],len(self.validation_dataset),self.n_lstm_hidden[1])).to(DEVICE)
        h_0_hidden_layer_RADIATION = torch.zeros((self.n_lstm_layers[1],len(self.validation_dataset),self.n_lstm_hidden[1])).to(DEVICE)
        c_0_hidden_layer_RADIATION = torch.zeros((self.n_lstm_layers[1],len(self.validation_dataset),self.n_lstm_hidden[1])).to(DEVICE)
        h_0_output_layer_RADIATION = torch.zeros((1,len(self.validation_dataset),self.n_output)).to(DEVICE)
        c_0_output_layer_RADIATION = torch.zeros((1,len(self.validation_dataset),self.n_output)).to(DEVICE)
        hidden_state_input_RADIATION = (h_0_input_layer_RADIATION,c_0_input_layer_RADIATION)
        hidden_state_hidden_RADIATION = (h_0_hidden_layer_RADIATION,c_0_hidden_layer_RADIATION)
        hidden_state_output_RADIATION = (h_0_output_layer_RADIATION,c_0_output_layer_RADIATION)

        h_0_input_layer_SPACEHEATER = torch.zeros((self.n_lstm_layers[2],len(self.validation_dataset),self.n_lstm_hidden[2])).to(DEVICE)
        c_0_input_layer_SPACEHEATER = torch.zeros((self.n_lstm_layers[2],len(self.validation_dataset),self.n_lstm_hidden[2])).to(DEVICE)
        h_0_hidden_layer_SPACEHEATER = torch.zeros((self.n_lstm_layers[2],len(self.validation_dataset),self.n_lstm_hidden[2])).to(DEVICE)
        c_0_hidden_layer_SPACEHEATER = torch.zeros((self.n_lstm_layers[2],len(self.validation_dataset),self.n_lstm_hidden[2])).to(DEVICE)
        h_0_output_layer_SPACEHEATER = torch.zeros((1,len(self.validation_dataset),self.n_output)).to(DEVICE)
        c_0_output_layer_SPACEHEATER = torch.zeros((1,len(self.validation_dataset),self.n_output)).to(DEVICE)
        hidden_state_input_SPACEHEATER = (h_0_input_layer_SPACEHEATER,c_0_input_layer_SPACEHEATER)
        hidden_state_hidden_SPACEHEATER = (h_0_hidden_layer_SPACEHEATER,c_0_hidden_layer_SPACEHEATER)
        hidden_state_output_SPACEHEATER = (h_0_output_layer_SPACEHEATER,c_0_output_layer_SPACEHEATER)

        h_0_input_layer_VENTILATION = torch.zeros((self.n_lstm_layers[3],len(self.validation_dataset),self.n_lstm_hidden[3])).to(DEVICE)
        c_0_input_layer_VENTILATION = torch.zeros((self.n_lstm_layers[3],len(self.validation_dataset),self.n_lstm_hidden[3])).to(DEVICE)
        h_0_hidden_layer_VENTILATION = torch.zeros((self.n_lstm_layers[3],len(self.validation_dataset),self.n_lstm_hidden[3])).to(DEVICE)
        c_0_hidden_layer_VENTILATION = torch.zeros((self.n_lstm_layers[3],len(self.validation_dataset),self.n_lstm_hidden[3])).to(DEVICE)
        h_0_output_layer_VENTILATION = torch.zeros((1,len(self.validation_dataset),self.n_output)).to(DEVICE)
        c_0_output_layer_VENTILATION = torch.zeros((1,len(self.validation_dataset),self.n_output)).to(DEVICE)
        hidden_state_input_VENTILATION = (h_0_input_layer_VENTILATION,c_0_input_layer_VENTILATION)
        hidden_state_hidden_VENTILATION = (h_0_hidden_layer_VENTILATION,c_0_hidden_layer_VENTILATION)
        hidden_state_output_VENTILATION = (h_0_output_layer_VENTILATION,c_0_output_layer_VENTILATION)

        self.hidden_state_validation = (hidden_state_input_OUTDOORTEMPERATURE,
                                    hidden_state_output_OUTDOORTEMPERATURE,
                                    hidden_state_input_RADIATION,
                                    hidden_state_output_RADIATION,
                                    hidden_state_input_SPACEHEATER,
                                    hidden_state_output_SPACEHEATER,
                                    hidden_state_input_VENTILATION,
                                    hidden_state_output_VENTILATION)
        # self.hidden_state_validation = (hidden_state_input_OUTDOORTEMPERATURE,
        #                             hidden_state_hidden_OUTDOORTEMPERATURE,
        #                             hidden_state_output_OUTDOORTEMPERATURE,
        #                             hidden_state_input_RADIATION,
        #                             hidden_state_hidden_RADIATION,
        #                             hidden_state_output_RADIATION,
        #                             hidden_state_input_SPACEHEATER,
        #                             hidden_state_hidden_SPACEHEATER,
        #                             hidden_state_output_SPACEHEATER,
        #                             hidden_state_input_VENTILATION,
        #                             hidden_state_hidden_VENTILATION,
        #                             hidden_state_output_VENTILATION)
    
        
        

        self.loss_fig, self.loss_ax = plt.subplots()
        for c in self.loss_ax.containers:
            self.loss_ax.bar_label(c, label_type='edge')

        self.grad_fig, self.grad_ax = plt.subplots()

        logger.info("[Trainer.Trainer] : Exited from Initialise Function")



    def loss_penalized(self, output, target, x, input):
        '''
            The function loss_penalized takes as input output, target, x, and input, and computes a loss function based
            on the difference between output and target, as well as several additional constraints that need to be satisfied. 
            These constraints relate to non-negativity of certain variables (x_SPACEHEATER_output and x_RADIATION_output),
            as well as certain gradient constraints :
                (loss_OUTDOORTEMPERATURE_0, loss_OUTDOORTEMPERATURE_1, loss_RADIATION_0, loss_SPACEHEATER_0, loss_SPACEHEATER_1, loss_VENTILATION_0, loss_VENTILATION_1). 
            The function returns both the overall loss and a dictionary containing the individual loss components.
        
        '''
        logger.info("[Trainer] : Entered in Loss Penalised Function")

        (x_OUTDOORTEMPERATURE_input,
            x_RADIATION_input,
            x_SPACEHEATER_input,
            x_VENTILATION_input) = input
        (x_OUTDOORTEMPERATURE_output, x_RADIATION_output, x_SPACEHEATER_output, x_VENTILATION_output) = x
        tol = 1e-8
        grad_OUTDOORTEMPERATURE = torch.autograd.grad(
                x_OUTDOORTEMPERATURE_output, x_OUTDOORTEMPERATURE_input,
                grad_outputs=torch.ones_like(x_OUTDOORTEMPERATURE_output),
                retain_graph=True,
                create_graph=True
            )[0]
        loss_OUTDOORTEMPERATURE_0 = torch.relu(grad_OUTDOORTEMPERATURE[:,:,0].unsqueeze(2))
        loss_OUTDOORTEMPERATURE_1 = torch.relu(-grad_OUTDOORTEMPERATURE[:,:,1].unsqueeze(2))
        # loss_OUTDOORTEMPERATURE_2 = torch.relu(-grad_OUTDOORTEMPERATURE[:,:,2].unsqueeze(2))
        # loss_OUTDOORTEMPERATURE_3 = torch.relu(-grad_OUTDOORTEMPERATURE[:,:,3].unsqueeze(2))
        # loss_OUTDOORTEMPERATURE_4 = torch.relu(-grad_OUTDOORTEMPERATURE[:,:,4].unsqueeze(2))

        RADIATION_is_active = x_RADIATION_input[:,:,0] > tol
        RADIATION_is_inactive = RADIATION_is_active==False
        loss_RADIATION_is_inactive = torch.zeros(x_RADIATION_output.shape).to(DEVICE)
        loss_RADIATION_is_inactive[RADIATION_is_inactive] = torch.abs(x_RADIATION_output[RADIATION_is_inactive])
        grad_RADIATION = torch.autograd.grad(
                x_RADIATION_output, x_RADIATION_input,
                grad_outputs=torch.ones_like(x_RADIATION_output),
                retain_graph=True,
                create_graph=True
            )[0]
        loss_RADIATION_0 = torch.relu(-grad_RADIATION[:,:,0].unsqueeze(2))


        SPACEHEATER_has_flow = x_SPACEHEATER_input[:,:,1] > tol
        SPACEHEATER_has_no_flow = SPACEHEATER_has_flow==False
        SPACEHEATER_has_output = x_SPACEHEATER_output[:,:,0] > tol
        DELTA_x_SPACEHEATER_output = torch.zeros(x_SPACEHEATER_output.shape).to(DEVICE)
        DELTA_x_SPACEHEATER_output[:,1:] = x_SPACEHEATER_output[:,1:]-x_SPACEHEATER_output[:,:-1]
        SPACEHEATER_is_constant = torch.abs(DELTA_x_SPACEHEATER_output[:,:,0]) < tol

        SPACEHEATER_has_no_flow_and_has_output = torch.logical_and(SPACEHEATER_has_no_flow, SPACEHEATER_has_output)
        SPACEHEATER_has_no_flow_and_is_constant = torch.logical_and(SPACEHEATER_has_no_flow, SPACEHEATER_is_constant)
        loss_SPACEHEATER_has_no_flow_and_has_output = torch.zeros(x_SPACEHEATER_output.shape).to(DEVICE)
        loss_SPACEHEATER_has_no_flow_and_has_output[SPACEHEATER_has_no_flow_and_has_output] = torch.relu(DELTA_x_SPACEHEATER_output[SPACEHEATER_has_no_flow_and_has_output])
        loss_SPACEHEATER_has_no_flow_and_is_constant = torch.zeros(x_SPACEHEATER_output.shape).to(DEVICE)
        loss_SPACEHEATER_has_no_flow_and_is_constant[SPACEHEATER_has_no_flow_and_is_constant] = torch.relu(x_SPACEHEATER_output[SPACEHEATER_has_no_flow_and_is_constant])
        grad_SPACEHEATER = torch.autograd.grad(
                x_SPACEHEATER_output, x_SPACEHEATER_input,
                grad_outputs=torch.ones_like(x_SPACEHEATER_output),
                retain_graph=True,
                create_graph=True
            )[0]
        loss_SPACEHEATER_0 = torch.relu(grad_SPACEHEATER[:,:,0].unsqueeze(2))
        loss_SPACEHEATER_1 = torch.relu(-grad_SPACEHEATER[:,:,1].unsqueeze(2))
        loss_SPACEHEATER_2 = torch.relu(-grad_SPACEHEATER[:,:,2].unsqueeze(2))



        VENTILATION_has_flow = x_VENTILATION_input[:,:,1] > tol
        VENTILATION_has_no_flow = VENTILATION_has_flow==False
        VENTILATION_has_output = x_VENTILATION_output[:,:,0] > tol
        DELTA_x_VENTILATION_output = torch.zeros(x_VENTILATION_output.shape).to(DEVICE)
        DELTA_x_VENTILATION_output[:,1:] = x_VENTILATION_output[:,1:]-x_VENTILATION_output[:,:-1]
        VENTILATION_is_constant = torch.abs(DELTA_x_VENTILATION_output[:,:,0]) < tol
        loss_VENTILATION_has_no_flow = torch.zeros(x_VENTILATION_output.shape).to(DEVICE)
        loss_VENTILATION_has_no_flow[VENTILATION_has_no_flow] = torch.abs(x_VENTILATION_output[VENTILATION_has_no_flow])

        grad_VENTILATION = torch.autograd.grad(
                x_VENTILATION_output, x_VENTILATION_input,
                grad_outputs=torch.ones_like(x_VENTILATION_output),
                retain_graph=True,
                create_graph=True
            )[0]
        loss_VENTILATION_0 = torch.relu(grad_VENTILATION[:,:,0].unsqueeze(2))
        # loss_VENTILATION_1 = torch.relu(grad_VENTILATION[:,:,1].unsqueeze(2))
        loss_VENTILATION_1 = torch.relu(-grad_VENTILATION[:,:,2].unsqueeze(2))

        K = 100
        loss_dict = pd.DataFrame.from_dict(data={"Error": torch.mean((output - target)**2).detach().item(),
                                "Nonnegative space heater": torch.mean(K*torch.relu(-x_SPACEHEATER_output)).detach().item(),
                                "Nonnegative radiation": torch.mean(K*torch.relu(-x_RADIATION_output)).detach().item(),
                                "loss_OUTDOORTEMPERATURE_0": torch.mean(K*loss_OUTDOORTEMPERATURE_0).detach().item(),
                                "loss_OUTDOORTEMPERATURE_1": torch.mean(K*loss_OUTDOORTEMPERATURE_1).detach().item(),
                                "loss_RADIATION_is_inactive": torch.mean(K*loss_RADIATION_is_inactive).detach().item(),
                                "loss_RADIATION_0": torch.mean(K*loss_RADIATION_0).detach().item(),
                                "loss_SPACEHEATER_has_no_flow_and_has_output": torch.mean(K*loss_SPACEHEATER_has_no_flow_and_has_output).detach().item(),
                                "loss_SPACEHEATER_has_no_flow_and_is_constant": torch.mean(K*loss_SPACEHEATER_has_no_flow_and_is_constant).detach().item(),
                                "loss_SPACEHEATER_0": torch.mean(K*loss_SPACEHEATER_0).detach().item(),
                                "loss_SPACEHEATER_1": torch.mean(K*loss_SPACEHEATER_1).detach().item(),
                                "loss_SPACEHEATER_2": torch.mean(K*loss_SPACEHEATER_2).detach().item(),
                                "loss_VENTILATION_has_no_flow": torch.mean(K*loss_VENTILATION_has_no_flow).detach().item(),
                                "loss_VENTILATION_0": torch.mean(K*loss_VENTILATION_0).detach().item(),
                                "loss_VENTILATION_1": torch.mean(K*loss_VENTILATION_1).detach().item(),
                    },orient="index")
        
        loss = torch.mean(
            ((output - target)**2 + 
            K*torch.relu(-x_SPACEHEATER_output)**2 +
            K*torch.relu(-x_RADIATION_output)**2 +
            # K*loss_OUTDOORTEMPERATURE + 
            K*loss_OUTDOORTEMPERATURE_0**2 +
            K*loss_OUTDOORTEMPERATURE_1**2 +
            # K*loss_OUTDOORTEMPERATURE_2**2 + 
            # K*loss_OUTDOORTEMPERATURE_3**2 + 
            # K*loss_OUTDOORTEMPERATURE_4**2 + 
            K*loss_RADIATION_is_inactive**2 +
            K*loss_RADIATION_0**2 +
            K*loss_SPACEHEATER_has_no_flow_and_has_output**2 +
            K*loss_SPACEHEATER_has_no_flow_and_is_constant**2 +
            K*loss_SPACEHEATER_0**2 +
            K*loss_SPACEHEATER_1**2 +
            K*loss_SPACEHEATER_2**2 +
            K*loss_VENTILATION_has_no_flow**2 +
            K*loss_VENTILATION_0**2 + 
            K*loss_VENTILATION_1**2)[:,self.warmup_steps:])
        
        logger.info("[Trainer] : Exited from Loss Penalised Function")  
        return loss, loss_dict


    def load_min_max_scale_values(self):
        os.chdir(self.dataset_folder)
        filename = self.space_name + "_scaling_value_dict" + ".pickle"
        filehandler = open(filename, 'rb')
        self.scaling_value_dict = pickle.load(filehandler)

    def get_input_old(self, flat_input):
        x_OUTDOORTEMPERATURE = torch.zeros((flat_input.shape[0], flat_input.shape[1], 2)).to(DEVICE)
        x_RADIATION = torch.zeros((flat_input.shape[0], flat_input.shape[1], 5)).to(DEVICE)
        x_SPACEHEATER = torch.zeros((flat_input.shape[0], flat_input.shape[1], 2)).to(DEVICE)
        x_VENTILATION = torch.zeros((flat_input.shape[0], flat_input.shape[1], 2)).to(DEVICE)
        
        x_OUTDOORTEMPERATURE[:,:,0] = flat_input[:,:,0] #indoor
        x_OUTDOORTEMPERATURE[:,:,1] = flat_input[:,:,5] #outdoor
        # x_OUTDOORTEMPERATURE[:,:,2] = flat_input[:,:,6] #outdoor
        # x_OUTDOORTEMPERATURE[:,:,3] = flat_input[:,:,7] #outdoor
        # x_OUTDOORTEMPERATURE[:,:,4] = flat_input[:,:,8] #outdoor
        x_RADIATION[:,:,0] = flat_input[:,:,4] #radiation
        x_RADIATION[:,:,1] = flat_input[:,:,9] #radiation
        x_RADIATION[:,:,2] = flat_input[:,:,10] #radiation
        x_RADIATION[:,:,3] = flat_input[:,:,11] #radiation
        x_RADIATION[:,:,4] = flat_input[:,:,12] #radiation
        x_SPACEHEATER[:,:,0] = flat_input[:,:,0] #indoor
        x_SPACEHEATER[:,:,1] = flat_input[:,:,1] #energy
        # x_SPACEHEATER[:,:,2] = flat_input[:,:,2] #supply water temperature
        # x_SPACEHEATER[:,:,3] = flat_input[:,:,2]*flat_input[:,:,3] #energy
        x_VENTILATION[:,:,0] = flat_input[:,:,2] #energy
        x_VENTILATION[:,:,1] = flat_input[:,:,3] #energy
        # x_VENTILATION[:,:,2] = flat_input[:,:,4] #supply air temperature
        # x_VENTILATION[:,:,3] = flat_input[:,:,4]*flat_input[:,:,5] #energy in 
        # x_VENTILATION[:,:,4] = flat_input[:,:,4]*flat_input[:,:,0] #energy out

        x_OUTDOORTEMPERATURE.requires_grad = True
        x_RADIATION.requires_grad = True
        x_SPACEHEATER.requires_grad = True
        x_VENTILATION.requires_grad = True

        input = (x_OUTDOORTEMPERATURE,
                x_RADIATION,
                x_SPACEHEATER,
                x_VENTILATION)

        return input
    
    def get_input(self, flat_input):
        x_OUTDOORTEMPERATURE = torch.zeros((flat_input.shape[0], flat_input.shape[1], 2)).to(DEVICE)
        x_RADIATION = torch.zeros((flat_input.shape[0], flat_input.shape[1], 5)).to(DEVICE)
        x_SPACEHEATER = torch.zeros((flat_input.shape[0], flat_input.shape[1], 3)).to(DEVICE)
        x_VENTILATION = torch.zeros((flat_input.shape[0], flat_input.shape[1], 3)).to(DEVICE)
        
        x_OUTDOORTEMPERATURE[:,:,0] = flat_input[:,:,0] #indoor
        x_OUTDOORTEMPERATURE[:,:,1] = flat_input[:,:,5] #outdoor
        # x_OUTDOORTEMPERATURE[:,:,2] = flat_input[:,:,7] #adjacent
        # x_OUTDOORTEMPERATURE[:,:,3] = flat_input[:,:,8] #adjacent
        # x_OUTDOORTEMPERATURE[:,:,4] = flat_input[:,:,9] #adjacent
        x_RADIATION[:,:,0] = flat_input[:,:,6] #radiation
        x_RADIATION[:,:,1] = flat_input[:,:,10] #radiation
        x_RADIATION[:,:,2] = flat_input[:,:,11] #radiation
        x_RADIATION[:,:,3] = flat_input[:,:,12] #radiation
        x_RADIATION[:,:,4] = flat_input[:,:,13] #radiation
        x_SPACEHEATER[:,:,0] = flat_input[:,:,0] #indoor
        x_SPACEHEATER[:,:,1] = flat_input[:,:,1] #valve position
        x_SPACEHEATER[:,:,2] = flat_input[:,:,2] #supply water temperature
        x_VENTILATION[:,:,0] = flat_input[:,:,0] #indoor
        x_VENTILATION[:,:,1] = flat_input[:,:,3] #damper position
        x_VENTILATION[:,:,2] = flat_input[:,:,4] #supply air temperature

        x_OUTDOORTEMPERATURE.requires_grad = True
        x_RADIATION.requires_grad = True
        x_SPACEHEATER.requires_grad = True
        x_VENTILATION.requires_grad = True

        input = (x_OUTDOORTEMPERATURE,
                x_RADIATION,
                x_SPACEHEATER,
                x_VENTILATION)

        return input
    
    def plot_grad_flow(self, named_parameters):
        '''
            Args:
                self: the class instance calling the method.
                flat_input (numpy.ndarray): a 3D numpy array with shape (batch_size, sequence_length, num_features), where batch_size is the number of samples in the batch, sequence_length is the length of the input sequence, and num_features is the number of features in the input.
            
            Returns:
                input (tuple of torch.Tensor): a tuple of four PyTorch tensors with the following shapes and device:
                x_OUTDOORTEMPERATURE: a tensor with shape (batch_size, sequence_length, 2) and device DEVICE.
                x_RADIATION: a tensor with shape (batch_size, sequence_length, 5) and device DEVICE.
                x_SPACEHEATER: a tensor with shape (batch_size, sequence_length, 2) and device DEVICE.
                x_VENTILATION: a tensor with shape (batch_size, sequence_length, 2) and device DEVICE.
        '''

        logger.info("[Trainer.Trainer] : Entered in Plot Grad Flow Function")

        self.grad_ax.clear()
        ave_grads = []
        layers = []
        for n, p in named_parameters:
            if(p.requires_grad) and ("bias" not in n):
                layers.append(n)
                ave_grads.append(p.grad.abs().mean())
        self.grad_ax.plot(ave_grads, alpha=0.3, color="b")
        self.grad_ax.hlines(0, 0, len(ave_grads)+1, linewidth=1, color="k" )
        self.grad_ax.set_xticks(range(0,len(ave_grads), 1), layers, rotation=25)
        self.grad_ax.set_xlim(xmin=0, xmax=len(ave_grads))
        self.grad_ax.set_xlabel("Layers")
        self.grad_ax.set_ylabel("average gradient")
        self.grad_ax.set_title("Gradient flow")
        self.grad_ax.grid(True)

        for tick in self.grad_ax.xaxis.get_majorticklabels():
            tick.set_horizontalalignment("right")
        plt.pause(0.01)


        logger.info("[Trainer.Trainer] : Exited from Plot Grad Flow Function")

    def plot_input_importance(self):
        """
        In progress...
        
        input,output = next(iter(self.train_dataloader))
        input = self.get_input(input)
        name = [xxx]

        e = shap.DeepExplainer(self.model, 
                                torch.from_numpy(input).to(DEVICE))
        shap_values = e.shap_values(torch.from_numpy(input).to(DEVICE))
        df = pd.DataFrame({
            "mean_abs_shap": np.mean(np.abs(shap_values), axis=0), 
            "stdev_abs_shap": np.std(np.abs(shap_values), axis=0), 
            "name": features
        })
        df.sort_values("mean_abs_shap", ascending=False)[:10]
        """
        pass

    def train_batch(self):
        
        logger.info("[Trainer.Trainer] : Entered in Train Batch Function")

        self.model.train()
        input,output = next(iter(self.train_dataloader))
        input = self.get_input(input)

        with torch.backends.cudnn.flags(enabled=False):
            y,hidden_state,x = self.model(input, self.hidden_state_train)

        loss, df_loss = self.loss_train(y,output,x,input)
        self.optimizer.zero_grad()
        loss.backward()
        # self.plot_grad_flow(self.model.named_parameters())
        self.optimizer.step()
        self.n_step += 1
   
        loss = torch.mean(loss).detach()
        self.step_train.append(self.n_step)
        self.prec_train.append(loss)

        if self.verbose:
            print("---Training batch results---")
            print('Avg loss: %s' % "{:.10f}".format(loss))
            
            # self.loss_ax.clear()
            # df_loss.plot(kind="bar", ax=self.loss_ax, rot=25, fontsize=10)#.legend()
            # plt.pause(0.01)
            
        logger.info("[Trainer.Trainer] : Exited from Train Batch Function")


    def validate(self):
        '''
            This function validates a PyTorch neural network model by computing the loss, mean squared error (MSE), 
            and mean absolute error (MAE) for a given validation dataset. It saves the model's state dictionary, 
            optimizer state dictionary, and training and testing data to files. 
            If specified, it also updates a plot of the training and testing loss over time.
        '''
        
        logger.info("[Trainer.Trainer] : Entered in Validate Function")

        self.model.eval()
        os.chdir(self.saved_networks_path)

        self.model.eval()
        input = self.validation_dataset.input
        output = self.validation_dataset.output
        input_raw = self.validation_dataset.input_raw
        input = self.get_input(input)

        y,hidden_state,x = self.model(input, self.hidden_state_validation)
        dT_cumsum = torch.cumsum(y,dim=1)
        T_0 = input_raw[:,0,0]
        T_0 = rescale(T_0,self.model.kwargs["scaling_value_dict"]["indoorTemperature"]["min"],self.model.kwargs["scaling_value_dict"]["indoorTemperature"]["max"],0,1)
        T_0 = T_0.unsqueeze(1)
        T_0 = T_0.repeat(1, dT_cumsum.shape[1]).unsqueeze(2)

        T = T_0 + dT_cumsum
        T_target = input_raw[:,1:,0]
        T_target = rescale(T_target,self.model.kwargs["scaling_value_dict"]["indoorTemperature"]["min"],self.model.kwargs["scaling_value_dict"]["indoorTemperature"]["max"],0,1)
        T_target = T_target.unsqueeze(2)



        y = y[:,self.warmup_steps:]
        output = output[:,self.warmup_steps:]
        T = T[:,self.warmup_steps:]
        T_target = T_target[:,self.warmup_steps:]
        loss = torch.mean(self.loss_test(y,output)).detach()
        MSE = torch.mean((T-T_target)**2).detach()
        MAE = torch.mean(torch.abs(T-T_target)).detach()

        if self.verbose:
            print("---Testing batch results---")
            print('Avg loss: %s' % "{:.10f}".format(loss))
            print('Avg MSE: %s' % "{:.10f}".format(MSE))
            print('Avg MAE: %s' % "{:.10f}".format(MAE))
            logger.info("---Testing batch results---")
            logger.info('Avg loss: %s' % "{:.10f}".format(loss))
            logger.info('Avg MSE: %s' % "{:.10f}".format(MSE))
            logger.info('Avg MAE: %s' % "{:.10f}".format(MAE))
        
        self.step_test.append(self.n_step)
        self.prec_test.append(loss)

        #Saving
        np.save(self.step_train_filename_save, np.array(self.step_train))
        np.save(self.prec_train_filename_save, np.array(self.prec_train))

        np.save(self.step_test_filename_save, np.array(self.step_test))
        np.save(self.prec_test_filename_save, np.array(self.prec_test))

        torch.save(self.model.state_dict(),self.network_filename_save)
        torch.save(self.optimizer.state_dict(),self.optimizer_filename_save)

        logger.info("[Trainer.Trainer] : Exited from Validate Function")


        

    def serialize_model(self):
        '''
            This function serializes the PyTorch model and saves it to a file along with its arguments. 
            It also appends the validation loss to a list of running validation losses and saves the list to a file. 
            The function then finds the model with the lowest validation loss and checks if there has been any improvement in the last best_loss_diff_max iterations. 
            If there has been no improvement, the function sets a flag to stop training and returns it.
            Otherwise, it returns False.
        '''
        do_break = False
        self.model.cpu()
        os.chdir(self.saved_serialized_networks_path)
        filename = "step" + str(self.n_step) + "_" + self.network_filename_save
        torch.save((self.model.kwargs, self.model.state_dict()), filename)
        self.running_validation_loss.append(self.prec_test[-1])
        np.save(self.running_validation_loss_filename_save, np.array(self.running_validation_loss))
        self.running_validation_loss_model_name.append(filename)
        np.save(self.running_validation_loss_model_name_filename_save, np.array(self.running_validation_loss_model_name))
        if self.verbose:
            logger.info("Saved serialized module")
        
        idx = np.nanargmin(np.array(self.running_validation_loss))

        a = self.running_validation_loss_model_name[idx].split("step")[1][:-3]
        b = a.split("_")[0]
        best_n_step = int(b)
        step_diff = self.n_step-best_n_step


        if step_diff>=self.best_loss_diff_max:
            logger.info("No improvement for the last " + str(self.best_loss_diff_max) + " iterations: Stopping...")
            do_break = True

        self.model.train()
        self.model.to(DEVICE)
        self.sort_directory()
        return do_break

    def train(self, verbose=False):
        '''
         It takes a boolean verbose parameter which is set to False by default. 
         If plot is True, it creates a plot for visualization purposes. 
         The function loops indefinitely and calls validate and train_batch functions until the n_step variable 
         reaches a maximum number of iterations.
        '''
        logger.info("[Trainer.Trainer] : Entered in Train Function")

        self.verbose = verbose
        while True:
            if self.verbose:
                print('--------------------------')
            if self.do_test == True:
                self.validate()
                # self.batch_idx_test += 1
                self.do_test = False
                do_break = self.serialize_model()
                if do_break:
                    break
            self.train_batch()
            if self.n_step % self.n_test == 0:
                self.do_test = True

            if np.all(np.isnan(np.array(self.running_validation_loss))):
                break
            idx = np.nanargmin(np.array(self.running_validation_loss))
            a = self.running_validation_loss_model_name[idx].split("step")[1][:-3]
            b = a.split("_")[0]
            best_n_step = int(b)
            step_diff = self.n_step-best_n_step
            running_test_avg = self.prec_test[-1]
            add_args = [self.n_step, running_test_avg.item(), step_diff, np.nanmin(np.array(self.running_validation_loss))]
            progressbar(self.n_step,self.n_step_start,self.max_it_stop, add_args = add_args)

            if self.n_step >= self.max_it_stop:
                break
            
        logger.info("[Trainer.Trainer] : Entered in Train Function")


    def display(self,str_input):

        fill_str = "#"
        n = 100
        n_str_input = len(str_input)
        n_fill_left = math.ceil((n-n_str_input)/2) - 1
        n_fill_right = n-n_fill_left-n_str_input - 2
        n_rows = 3
        i_row = 1 #Index of row placement of input string

        str_output = ""
        for row in range(n_rows):
            if row == i_row:
                for j in range(n_fill_left):
                    str_output += fill_str
                str_output += " "
                str_output += str_input
                str_output += " "
                for j in range(n_fill_right):
                    str_output += fill_str
                str_output += "\n"
            else:
                for j in range(n):
                    str_output += fill_str
                str_output += "\n"

        print(str_output)

    def sort_directory(self):
        os.chdir(self.saved_serialized_networks_path)

        running_validation_loss = np.array(self.running_validation_loss)
        idx = np.argmin(running_validation_loss)
        running_validation_loss_model_name_sorted = self.running_validation_loss_model_name[:]
        running_validation_loss_model_name_sorted.pop(idx)

        for filename in running_validation_loss_model_name_sorted:
            try:
                os.remove(filename)
            except:
                pass

        self.running_validation_loss = [self.running_validation_loss[idx]]
        self.running_validation_loss_model_name = [self.running_validation_loss_model_name[idx]]
        
        np.save(self.running_validation_loss_filename_save, np.array(self.running_validation_loss))
        np.save(self.running_validation_loss_model_name_filename_save, np.array(self.running_validation_loss_model_name))


def progressbar(current,start,stop, add_args=None):
    total_time = stop-start
    relative_time = current-start
    n_ticks_total = 40
    n_ticks_current = math.ceil(relative_time/total_time*n_ticks_total)
    percent_done = math.ceil(relative_time/total_time*100)

    progress_str = '|'
    for i in range(n_ticks_total):
        if n_ticks_current > i:
            progress_str += '#'
        else:
            progress_str += '-'
    if add_args:
        progress_str += '| ' + str(percent_done) + '% '
        for arg in add_args:
            progress_str += "-- " + str(arg) + " "
    else:
        progress_str += '| ' + str(percent_done) + '% '
    sys.stdout.write('\r\x1b[K' + progress_str)
    sys.stdout.flush()



######################################################
# for i,space_name in enumerate(saved_space_list):
#     # clear_output(wait=True)
#     train = False
#     try:
#         trainer = Trainer(space_name, data_paths, load=True)
#         running_validation_loss = np.array(trainer.running_validation_loss)

#         if running_validation_loss.size==1:
#             print("Space \"" + space_name + "\" exists and has size 1")
#             # print(trainer.running_validation_loss_model_name)

#             best_idx = int(trainer.running_validation_loss_model_name[0].split("_step")[1].split(".pt")[0])

            
#             best_loss_diff = trainer.n_step-best_idx
#             if best_loss_diff>=trainer.best_loss_diff_max:
#                 print("No improvement for the last " + str(trainer.best_loss_diff_max) + " iterations: Skipping...")
#             else:
#                 train = True

#         else:
#             print("Space \"" + space_name + "\" exists but has size " + str(running_validation_loss.size))
#             trainer = Trainer(space_name, data_paths, load=True)
#             train = True

#     except Exception as inst:
#         # print(inst)
#         print("Can't load \"" + space_name + "\"")
#         trainer = Trainer(space_name, data_paths, load=False)
#         train = True

#     if train == True:
#         print("Space number " + str(i))
#         trainer.load_min_max_scale_values()
#         trainer.scan_directory()
#         trainer.train(verbose=False)
#         trainer.sort_directory()
##################################################################
# Ø20-601b-2
# Ø22-511-2



if __name__=="__main__":
    space_name = "OE20-601b-2"
    # space_name = "OE22-511-2"
    batch_list = [2**6, 2**8]
    lr_list = [3e-2, 8e-3, 3e-3]
    n_hidden_list = [3, 5, 8]
    n_layers_list = [1, 2, 3]


    # batch_list = [2**6] #2**8
    # lr_list = [3e-2] #3e-2
    # n_hidden_list = [5] #3
    # n_layers_list = [2] #3
    import json
    result_dict = {str(lr):{
                    str(batch): {
                        str(n_hidden): {
                            str(n_layers): {
                                "name": None,
                                "loss": None
                                            } 
                                        for n_layers in n_layers_list
                                        }
                                for n_hidden in n_hidden_list
                                }
                            for batch in batch_list}
                        for lr in lr_list
                    }
    # result_dict = {"0.01": {"64": {"3": {"1": {"name": "step2100_OE20-601b-2_Network_B64_LR1E-02_H3_L1.pt", "loss": 0.02344849519431591}, "2": {"name": "step560_OE20-601b-2_Network_B64_LR1E-02_H3_L2.pt", "loss": 0.023655638098716736}, "3": {"name": "step640_OE20-601b-2_Network_B64_LR1E-02_H3_L3.pt", "loss": 0.02367391437292099}}, "5": {"1": {"name": "step710_OE20-601b-2_Network_B64_LR1E-02_H5_L1.pt", "loss": 0.023694857954978943}, "2": {"name": "step820_OE20-601b-2_Network_B64_LR1E-02_H5_L2.pt", "loss": 0.023654529824852943}, "3": {"name": "step1620_OE20-601b-2_Network_B64_LR1E-02_H5_L3.pt", "loss": 0.02336055412888527}}, "8": {"1": {"name": "step2450_OE20-601b-2_Network_B64_LR1E-02_H8_L1.pt", "loss": 0.02326839603483677}, "2": {"name": "step1900_OE20-601b-2_Network_B64_LR1E-02_H8_L2.pt", "loss": 0.0233263298869133}, "3": {"name": "step500_OE20-601b-2_Network_B64_LR1E-02_H8_L3.pt", "loss": 0.023639842867851257}}}, "256": {"3": {"1": {"name": "step110_OE20-601b-2_Network_B256_LR1E-02_H3_L1.pt", "loss": 0.023774802684783936}, "2": {"name": "step670_OE20-601b-2_Network_B256_LR1E-02_H3_L2.pt", "loss": 0.023775974288582802}, "3": {"name": "step790_OE20-601b-2_Network_B256_LR1E-02_H3_L3.pt", "loss": 0.023732785135507584}}, "5": {"1": {"name": "step300_OE20-601b-2_Network_B256_LR1E-02_H5_L1.pt", "loss": 0.02369525097310543}, "2": {"name": "step1380_OE20-601b-2_Network_B256_LR1E-02_H5_L2.pt", "loss": 0.023386912420392036}, "3": {"name": "step330_OE20-601b-2_Network_B256_LR1E-02_H5_L3.pt", "loss": 0.023685939610004425}}, "8": {"1": {"name": None, "loss": None}, "2": {"name": None, "loss": None}, "3": {"name": None, "loss": None}}}}, "0.03": {"64": {"3": {"1": {"name": "step2650_OE20-601b-2_Network_B64_LR3E-02_H3_L1.pt", "loss": 0.02335312031209469}, "2": {"name": "step810_OE20-601b-2_Network_B64_LR3E-02_H3_L2.pt", "loss": 0.023666540160775185}, "3": {"name": "step310_OE20-601b-2_Network_B64_LR3E-02_H3_L3.pt", "loss": 0.023673372343182564}}, "5": {"1": {"name": "step570_OE20-601b-2_Network_B64_LR3E-02_H5_L1.pt", "loss": 0.023640941828489304}, "2": {"name": "step560_OE20-601b-2_Network_B64_LR3E-02_H5_L2.pt", "loss": 0.023660844191908836}, "3": {"name": "step1270_OE20-601b-2_Network_B64_LR3E-02_H5_L3.pt", "loss": 0.02334899641573429}}, "8": {"1": {"name": "step160_OE20-601b-2_Network_B64_LR3E-02_H8_L1.pt", "loss": 0.023721905425190926}, "2": {"name": "step1590_OE20-601b-2_Network_B64_LR3E-02_H8_L2.pt", "loss": 0.0232962928712368}, "3": {"name": "step390_OE20-601b-2_Network_B64_LR3E-02_H8_L3.pt", "loss": 0.023636072874069214}}}, "256": {"3": {"1": {"name": None, "loss": None}, "2": {"name": None, "loss": None}, "3": {"name": None, "loss": None}}, "5": {"1": {"name": None, "loss": None}, "2": {"name": None, "loss": None}, "3": {"name": None, "loss": None}}, "8": {"1": {"name": None, "loss": None}, "2": {"name": None, "loss": None}, "3": {"name": None, "loss": None}}}}, "0.06": {"64": {"3": {"1": {"name": "step120_OE20-601b-2_Network_B64_LR6E-02_H3_L1.pt", "loss": 0.023708876222372055}, "2": {"name": "step1640_OE20-601b-2_Network_B64_LR6E-02_H3_L2.pt", "loss": 0.02362268604338169}, "3": {"name": "step510_OE20-601b-2_Network_B64_LR6E-02_H3_L3.pt", "loss": 0.023645667359232903}}, "5": {"1": {"name": "step840_OE20-601b-2_Network_B64_LR6E-02_H5_L1.pt", "loss": 0.023590784519910812}, "2": {"name": "step1450_OE20-601b-2_Network_B64_LR6E-02_H5_L2.pt", "loss": 0.02329147420823574}, "3": {"name": "step320_OE20-601b-2_Network_B64_LR6E-02_H5_L3.pt", "loss": 0.02364453300833702}}, "8": {"1": {"name": "step830_OE20-601b-2_Network_B64_LR6E-02_H8_L1.pt", "loss": 0.023641113191843033}, "2": {"name": "step420_OE20-601b-2_Network_B64_LR6E-02_H8_L2.pt", "loss": 0.023611322045326233}, "3": {"name": "step1690_OE20-601b-2_Network_B64_LR6E-02_H8_L3.pt", "loss": np.nan}}}, "256": {"3": {"1": {"name": None, "loss": None}, "2": {"name": None, "loss": None}, "3": {"name": None, "loss": None}}, "5": {"1": {"name": None, "loss": None}, "2": {"name": None, "loss": None}, "3": {"name": None, "loss": None}}, "8": {"1": {"name": None, "loss": None}, "2": {"name": None, "loss": None}, "3": {"name": None, "loss": None}}}}}    
    
    for batch_size in batch_list:
        for learning_rate in lr_list:
            for n_hidden in n_hidden_list:
                for n_layer in n_layers_list:
                    if result_dict[str(learning_rate)][str(batch_size)][str(n_hidden)][str(n_layer)]["name"] is None:
                        hyperparameters = {"batch_size": batch_size,
                                            "learning_rate": learning_rate,
                                            "n_hidden": n_hidden,
                                            "n_layer": n_layer}
                        trainer = Trainer(space_name, load=False, hyperparameters=hyperparameters)
                        
                        trainer.train(verbose=True)
                        trainer.sort_directory()
                        result_dict[str(learning_rate)][str(batch_size)][str(n_hidden)][str(n_layer)]["name"] = trainer.running_validation_loss_model_name[0]
                        result_dict[str(learning_rate)][str(batch_size)][str(n_hidden)][str(n_layer)]["loss"] = float(trainer.running_validation_loss[0])
                        print(json.dumps(result_dict, indent=4))
                        with open(trainer.saved_result_path, 'w') as f:
                            json.dump(result_dict, f)


    # %mprun -f trainer.load_dataset_into_RAM trainer.load_dataset_into_RAM()
    # %lprun -f trainer.train_batch -f trainer.test_batch -f trainer.train -f trainer.load_dataset_into_DEVICE trainer.train()
