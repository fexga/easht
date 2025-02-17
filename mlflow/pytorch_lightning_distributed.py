import os
import torch
import torch.nn as nn
import torch.optim as optim
import torch.utils.data as data
import torchvision.transforms as transforms
from torchvision.datasets import MNIST
from torch.utils.data import DataLoader
import optuna
from optuna.trial import TrialState
import mlflow
import mlflow.pytorch

mlflow.set_tracking_uri("http://mlflow:5000")
mlflow.set_experiment("pytorch-lightning-distributed")

BATCHSIZE = 128
EPOCHS = 5

class Net(nn.Module):
    def __init__(self, trial):
        super(Net, self).__init__()
        layers = []
        input_dim = 28 * 28
        n_layers = trial.suggest_int("n_layers", 1, 3)
        dropout = trial.suggest_float("dropout", 0.2, 0.5)
        for i in range(n_layers):
            output_dim = trial.suggest_int("n_units_l{}".format(i), 32, 128)
            layers.append(nn.Linear(input_dim, output_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout))
            input_dim = output_dim
        layers.append(nn.Linear(input_dim, 10))
        self.layers = nn.Sequential(*layers)

    def forward(self, x):
        x = x.view(x.size(0), -1)
        return self.layers(x)

def objective(trial):
    with mlflow.start_run():
        transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.1307,), (0.3081,))])
        train_dataset = MNIST(root="~/data", train=True, transform=transform, download=True)
        train_loader = DataLoader(dataset=train_dataset, batch_size=BATCHSIZE, shuffle=True)

        model = Net(trial)
        criterion = nn.CrossEntropyLoss()
        optimizer_name = trial.suggest_categorical("optimizer", ["Adam", "RMSprop", "SGD"])
        lr = trial.suggest_float("lr", 1e-5, 1e-1, log=True)
        optimizer = getattr(optim, optimizer_name)(model.parameters(), lr=lr)

        # Log parameters
        mlflow.log_param("optimizer", optimizer_name)
        mlflow.log_param("learning_rate", lr)
        mlflow.log_param("n_layers", trial.params["n_layers"])
        mlflow.log_param("dropout", trial.params["dropout"])

        for epoch in range(EPOCHS):
            model.train()
            for batch_idx, (data, target) in enumerate(train_loader):
                optimizer.zero_grad()
                output = model(data)
                loss = criterion(output, target)
                loss.backward()
                optimizer.step()

            # Log metrics for each epoch
            mlflow.log_metric("loss", loss.item(), step=epoch)

        # Log the model
        mlflow.pytorch.log_model(model, "model")

        return loss.item()

if __name__ == "__main__":
    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=100, timeout=600)

    pruned_trials = [t for t in study.trials if t.state == TrialState.PRUNED]
    complete_trials = [t for t in study.trials if t.state == TrialState.COMPLETE]

    print("Study statistics: ")
    print("  Number of finished trials: ", len(study.trials))
    print("  Number of pruned trials: ", len(pruned_trials))
    print("  Number of complete trials: ", len(complete_trials))

    print("Best trial:")
    trial = study.best_trial

    print("  Value: ", trial.value)

    print("  Params: ")
    for key, value in trial.params.items():
        print("    {}: {}".format(key, value))
