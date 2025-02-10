import torch
import torch.nn as nn
import torch.optim as optim
import torch.utils.data as data
import torchvision.transforms as transforms
from torchvision.datasets import MNIST
import ray
from ray import tune
from ray.tune.schedulers import ASHAScheduler

BATCHSIZE = 128
EPOCHS = 5

class Net(nn.Module):
    def __init__(self, config):
        super(Net, self).__init__()
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

    def forward(self, x):
        x = x.view(x.size(0), -1)
        return self.layers(x)

def train_mnist(config):
    transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.1307,), (0.3081,))])
    train_dataset = MNIST(root="~/data", train=True, transform=transform, download=True)
    train_loader = data.DataLoader(dataset=train_dataset, batch_size=BATCHSIZE, shuffle=True)

    model = Net(config)
    criterion = nn.CrossEntropyLoss()
    optimizer = getattr(optim, config["optimizer"])(model.parameters(), lr=config["lr"])

    for epoch in range(EPOCHS):
        model.train()
        for batch_idx, (data, target) in enumerate(train_loader):
            optimizer.zero_grad()
            output = model(data)
            loss = criterion(output, target)
            loss.backward()
            optimizer.step()

        tune.report(loss=loss.item())

if __name__ == "__main__":
    config = {
        "n_layers": tune.choice([1, 2, 3]),
        "n_units_l0": tune.choice([32, 64, 128]),
        "n_units_l1": tune.choice([32, 64, 128]),
        "n_units_l2": tune.choice([32, 64, 128]),
        "dropout": tune.uniform(0.2, 0.5),
        "lr": tune.loguniform(1e-5, 1e-1),
        "optimizer": tune.choice(["Adam", "RMSprop", "SGD"])
    }

    scheduler = ASHAScheduler(
        metric="loss",
        mode="min",
        max_t=EPOCHS,
        grace_period=1,
        reduction_factor=2
    )

    analysis = tune.run(
        train_mnist,
        config=config,
        num_samples=10,
        scheduler=scheduler
    )

    print("Best hyperparameters found were: ", analysis.best_config)

