import logging
from pathlib import Path
from typing import Dict

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torch.utils.data import TensorDataset
import pandas as pd

logger = logging.getLogger(__name__)


class PyTorchModelTrainer:
    def __init__(
            self,
            model: nn.Module,
            optimizer: nn.Module,
            criterion: nn.Module,
            device: str,
            batch_size: int,
            max_iters: int,
            eval_iters: int,
            init_model: Dict
    ):
        self.model = model
        self.optimizer = optimizer
        self.criterion = criterion
        self.device = device
        self.max_iters = max_iters
        self.batch_size = batch_size
        self.eval_iters = eval_iters

        if init_model:
            self.load_from_checkpoint(init_model)

    def fit(self, data_dictionary: Dict[str, pd.DataFrame]):
        data_loaders_dictionary = self.create_data_loaders_dictionary(data_dictionary)
        epochs = self.calc_n_epochs(
            n_obs=len(data_dictionary['train_features']),
            batch_size=self.batch_size,
            n_iters=self.max_iters
        )
        for epoch in range(epochs):
            # evaluation
            losses = self.estimate_loss(data_loaders_dictionary, data_dictionary)
            logger.info(
                f"epoch ({epoch}/{epochs}):"
                f" train loss {losses['train']:.4f} ; test loss {losses['test']:.4f}"
            )
            # training
            for batch_data in data_loaders_dictionary['train']:
                xb, yb = batch_data
                xb = xb.to(self.device)  # type: ignore
                yb = yb.to(self.device)
                yb_pred = self.model(xb)
                loss = self.criterion(yb_pred, yb)

                self.optimizer.zero_grad(set_to_none=True)
                loss.backward()
                self.optimizer.step()

    @torch.no_grad()
    def estimate_loss(
            self,
            data_loader_dictionary: Dict[str, DataLoader],
            data_dictionary: Dict[str, pd.DataFrame]
    ) -> Dict[str, float]:

        self.model.eval()
        epochs = self.calc_n_epochs(
            n_obs=len(data_dictionary['test_features']),
            batch_size=self.batch_size,
            n_iters=self.eval_iters
        )
        loss_dictionary = {}
        for split in ['train', 'test']:
            losses = torch.zeros(epochs)
            for i, batch in enumerate(data_loader_dictionary[split]):
                xb, yb = batch
                xb = xb.to(self.device)
                yb = yb.to(self.device)
                yb_pred = self.model(xb)
                loss = self.criterion(yb_pred, yb)
                losses[i] = loss.item()

            loss_dictionary[split] = losses.mean()

        self.model.train()
        return loss_dictionary

    def create_data_loaders_dictionary(
            self,
            data_dictionary: Dict[str, pd.DataFrame]
    ) -> Dict[str, DataLoader]:
        data_loader_dictionary = {}
        for split in ['train', 'test']:
            labels_shape = data_dictionary[f'{split}_labels'].shape
            labels_view = labels_shape[0] if labels_shape[1] == 1 else labels_shape
            dataset = TensorDataset(
                torch.from_numpy(data_dictionary[f'{split}_features'].values).float(),
                torch.from_numpy(data_dictionary[f'{split}_labels'].astype(float).values)
                .long()
                .view(labels_view)
            )
            # todo currently assuming class labels are strings ['0.0', '1.0' .. n_classes].
            #  need to resolve it per ClassifierModel

            data_loader = DataLoader(
                dataset,
                batch_size=self.batch_size,
                shuffle=True,
                drop_last=True,
                num_workers=0,
            )
            data_loader_dictionary[split] = data_loader

        return data_loader_dictionary

    @staticmethod
    def calc_n_epochs(n_obs: int, batch_size: int, n_iters: int) -> int:
        n_batches = n_obs // batch_size
        epochs = n_iters // n_batches
        return epochs

    def save(self, path: Path):
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
        }, path)

    def load_from_file(self, path: Path):
        checkpoint = torch.load(path)
        return self.load_from_checkpoint(checkpoint)

    def load_from_checkpoint(self, checkpoint: Dict):
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        return self
