'''
Main function
'''
import os
import random
from pathlib import Path
from torch.utils.data import DataLoader
import torch
import torch.nn as nn
from torchmetrics import Dice, Precision, Recall, JaccardIndex
import segmentation_models_pytorch as smp
import numpy as np
import argparse
from src.data.dataset import ProcessedWoundDataset
from src.data.make_dataset import make_dataset1, make_dataset2
from src.utils import empty_directory
from src.models.mobilnetv2 import MobileNetV2withDecoder
from src.models.train_model import train, test
from src.models.utils import DiceLoss
from config.defaults import get_cfg_defaults

def main():
    '''
    Main function
    '''

    #Argument parser
    #parser = argparse.ArgumentParser(description='WoundSegmentation with MobileNetV2 and LinkNet')
    #parser.add_argument('--data_only', type=bool, default=False)

    #args = parser.parse_args()
    cfg = get_cfg_defaults()
    #cfg.merge_from_lists(args)
    device = None

    if torch.cuda.is_available():
        device = torch.device("cuda")
        print("Using CUDA device.")
    else:
        if torch.backends.mps.is_available():
            device = torch.device("mps")
            print("Using MPS device.")
        else:
            device = torch.device("cpu")
            print("Using CPU device.")

    
    random.seed(cfg.SYSTEM.SEED)
    np.random.seed(cfg.SYSTEM.SEED)
    torch.manual_seed(cfg.SYSTEM.SEED)

    #Deciding variables based on which paper is to be replicated
    if cfg.MNV2:
        print("MobileNetV2")
        cfg.DATA.PATH = os.getcwd() + '/data_MnV2/'
        cfg.DATA.WS_AUG = False
        cfg.NAME = 'MobileNetv2'
    
    if not cfg.MNV2:
        print("WSeg (LinkNet)")
        cfg.DATA.PATH = os.getcwd() + '/data_WSeg/'
        cfg.DATA.WS_AUG = True
        cfg.NAME = 'WSNet'
    
    #Empty the data directories except 'external' if indicated
    if cfg.DATA.CLEAR:
        print("Emptying data directory except 'external'.")
        for folder in Path(cfg.DATA.PATH).glob('*'):
            if folder.name != 'external' and folder.name != '.DS_Store':
                empty_directory(folder)
        cfg.DATA.MAKE = True
    

    if cfg.DATA.MAKE:
        #Make the dataset1 ready for training
        print("Making dataset 1")
        make_dataset1(cfg.DATA.PATH, cfg.DATA.WS_AUG)

        #Make the dataset2 ready for training
        make_dataset2(cfg.DATA.PATH, cfg.DATA.WS_AUG)

    if cfg.DATA.PROC_ONLY:
        return None
    
    print("Creating Dataloaders")
    datasets = {}

    datasets['train'] = ProcessedWoundDataset(cfg.DATA.PATH + 'processed/train/')
    datasets['val'] = ProcessedWoundDataset(cfg.DATA.PATH + 'processed/val/')
    datasets['test'] = ProcessedWoundDataset(cfg.DATA.PATH + 'processed/test/')

    dataloaders = {x: DataLoader(dataset=datasets[x], batch_size=cfg.TRAIN.BATCH_SIZE, shuffle=True,
                                 num_workers=cfg.SYSTEM.NUM_WORKERS, drop_last=True) for x in ['train','val', 'test']}
    
    # Instantiate the model
    print("Loading the model")
    if cfg.MNV2:
        model = MobileNetV2withDecoder(classes=1)
        
        # Loss function
        criterion = nn.BCELoss()
    
    if not cfg.MNV2:
        model = smp.Linknet(encoder_name="densenet169", encoder_weights="imagenet", in_channels=3, classes=1)

        # Loss function
        criterion = DiceLoss()

    # Optimizer
    optimizer = torch.optim.Adam(model.parameters(), lr=cfg.LR)

    #Evaluation Metrics
    dice_metric = Dice(threshold=0.5)
    precision_metric = Precision(task='binary')
    recall_metric = Recall(task='binary')
    iou_metric = JaccardIndex(task='binary')

    metrics = [dice_metric, precision_metric, recall_metric, iou_metric]

    #Train model
    trained_model, train_results, val_results = train(model, dataloaders, device, 
                                                      criterion, optimizer, cfg.TRAIN.NUM_EPOCHS, metrics,
                                                      model_save_path=cfg.MODEL.MODELS_PATH, 
                                                      model_name = cfg.NAME,
                                                      metric_save_path=cfg.MODEL.VIZ_PATH)
    
    #Test model
    test_results = test(trained_model, dataloaders, device, criterion, metrics, metric_save_path=cfg.MODEL.VIZ_PATH)

if __name__ == '__main__':

    main()
