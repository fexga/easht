import torch.nn as nn
import torch.optim as optim
import torch.utils.data as dt
import torchvision.transforms as transforms
from torchvision.datasets import FashionMNIST
import ray
from ray import tune
import pytorch_lightning as pl
from ray.tune.integration.pytorch_lightning import TuneReportCallback
from ray.tune.schedulers import MedianStoppingRule


ray.init(address="auto", ignore_reinit_error=True)

class LightningMNISTModel(pl.LightningModule):
    def __init__(self, config):
        super(LightningMNISTModel, self).__init__()
        self.config = config
        
        # Build network layers
        layers = []
        input_dim = 28 * 28
        for i in range(config["n_layers"]):
            output_dim = int(config["n_units_l{}".format(i)])
            layers.append(nn.Linear(input_dim, output_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(config["dropout"]))
            input_dim = output_dim
        layers.append(nn.Linear(input_dim, 10))
        self.layers = nn.Sequential(*layers)
        
        self.criterion = nn.CrossEntropyLoss()
    
    def forward(self, x):
        x = x.view(x.size(0), -1)
        return self.layers(x)
    
    def training_step(self, batch, batch_idx):
        data, target = batch
        output = self(data)
        loss = self.criterion(output, target)
        self.log("loss", loss, on_step=False, on_epoch=True, prog_bar=True)
        return loss
    
    def validation_step(self, batch, batch_idx):
        data, target = batch
        output = self(data)
        loss = self.criterion(output, target)
        pred = output.argmax(dim=1, keepdim=True)
        accuracy = pred.eq(target.view_as(pred)).float().mean()
        self.log("val_loss", loss, on_step=False, on_epoch=True, prog_bar=True)
        self.log("val_accuracy", accuracy, on_step=False, on_epoch=True, prog_bar=True)
        return {"val_loss": loss, "val_accuracy": accuracy}
    
    def configure_optimizers(self):
        optimizer_name = self.config["optimizer"]
        lr = self.config["lr"]
        optimizer_class = getattr(optim, optimizer_name)
        return optimizer_class(self.parameters(), lr=lr)
    
    def train_dataloader(self):
        transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.1307,), (0.3081,))])
        train_dataset = FashionMNIST(root="/tmp/data", train=True, transform=transform, download=True)
        return dt.DataLoader(dataset=train_dataset, batch_size=128, shuffle=True)
    
    def val_dataloader(self):
        transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.1307,), (0.3081,))])
        val_dataset = FashionMNIST(root="/tmp/data", train=False, transform=transform, download=True)
        return dt.DataLoader(dataset=val_dataset, batch_size=128)


def train_mnist_lightning(config):
    model = LightningMNISTModel(config)
    metrics = {"val_loss": "val_loss", "val_accuracy": "val_accuracy"}
    
    callback = TuneReportCallback(metrics, on="validation_end")
    trainer = pl.Trainer(
        min_epochs=10,          
        enable_checkpointing=False,
        logger=False,
        enable_progress_bar=False,
        callbacks=[callback],
        num_sanity_val_steps=0
    )
    trainer.fit(model)

search_space = {
    "n_layers": tune.choice([1, 2, 3]),
    "n_units_l0": tune.choice([32, 64, 128]),
    "n_units_l1": tune.choice([32, 64, 128]),
    "n_units_l2": tune.choice([32, 64, 128]),
    "dropout": tune.uniform(0.2, 0.5),
    "lr": tune.loguniform(1e-5, 1e-1),
    "optimizer": tune.choice(["Adam", "RMSprop", "SGD"])
}

scheduler = MedianStoppingRule(
    metric="val_loss",
    mode="min",
    grace_period=5,
    min_samples_required=1
)

analysis = tune.run(
    train_mnist_lightning,
    resources_per_trial={"cpu": 1},
    config=search_space,
    num_samples=15,
    max_concurrent_trials=5,
    scheduler=scheduler,
    storage_path="/tmp/ray_results"
)

best_trial = analysis.get_best_trial("val_loss", "min")
print("Best trial config: {}".format(best_trial.config))
print("Best trial final validation loss: {}".format(best_trial.last_result["val_loss"]))
print("Best trial final validation accuracy: {}".format(best_trial.last_result["val_accuracy"]))

best_trial = analysis.get_best_trial("val_accuracy", "max")
best_val_acc = best_trial.last_result["val_accuracy"]
print(f"BEST_VAL_ACCURACY: {best_val_acc}")

# Optionally, also write to a small file for easy retrieval
with open("/tmp/best_val_accuracy.txt", "w") as f:
    f.write(str(best_val_acc))

