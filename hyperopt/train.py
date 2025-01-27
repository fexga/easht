import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, transforms
from torch.utils.data import DataLoader
from hyperopt import fmin, tpe, hp, STATUS_OK, Trials
from hyperopt.mongoexp import MongoTrials
import pymongo
from bson import SON
import os

# Define the neural network model
class Net(nn.Module):
    def __init__(self, units1, units2):
        super(Net, self).__init__()
        self.fc1 = nn.Linear(28 * 28, units1)
        self.fc2 = nn.Linear(units1, units2)
        self.fc3 = nn.Linear(units2, 10)

    def forward(self, x):
        x = x.view(-1, 28 * 28)
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        x = self.fc3(x)
        return x

def objective(params):
    transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.5,), (0.5,))])
    train_dataset = datasets.MNIST('.', train=True, download=True, transform=transform)
    test_dataset = datasets.MNIST('.', train=False, download=True, transform=transform)
    train_loader = DataLoader(train_dataset, batch_size=int(params['batch_size']), shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=1000, shuffle=False)

    model = Net(int(params['units1']), int(params['units2']))
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=params['lr'])

    for epoch in range(5):
        model.train()
        for batch_idx, (data, target) in enumerate(train_loader):
            optimizer.zero_grad()
            output = model(data)
            loss = criterion(output, target)
            loss.backward()
            optimizer.step()

    model.eval()
    test_loss = 0
    correct = 0
    with torch.no_grad():
        for data, target in test_loader:
            output = model(data)
            test_loss += criterion(output, target).item()
            pred = output.argmax(dim=1, keepdim=True)
            correct += pred.eq(target.view_as(pred)).sum().item()

    test_loss /= len(test_loader.dataset)
    accuracy = 100. * correct / len(test_loader.dataset)
    return {'loss': -accuracy, 'status': STATUS_OK}

if __name__ == "__main__":
    mongo_uri = "mongo://mongo:27017/hyperopt/jobs"
    trials = MongoTrials(mongo_uri, exp_key='exp1')

    space = {
        'units1': hp.quniform('units1', 32, 128, 1),
        'units2': hp.quniform('units2', 32, 128, 1),
        'batch_size': hp.quniform('batch_size', 32, 128, 1),
        'lr': hp.loguniform('lr', -5, -1)
    }

    best = fmin(objective, space, algo=tpe.suggest, max_evals=100, trials=trials)
    print(f'Best parameters: {best}')


