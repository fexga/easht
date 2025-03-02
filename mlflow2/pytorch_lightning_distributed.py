import os
import torch
import torch.nn as nn
import torch.optim as optim
import torch.utils.data as data
from sklearn.datasets import fetch_20newsgroups
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import CountVectorizer
import optuna
from optuna.trial import TrialState
import mlflow
import mlflow.pytorch
from prometheus_flask_exporter import PrometheusMetrics
from flask import Flask
import requests

app = Flask(__name__)
metrics = PrometheusMetrics(app)

mlflow.set_tracking_uri("http://mlflow:5000")
mlflow.set_experiment("pytorch-lightning-distributed")

BATCHSIZE = 64
EPOCHS = 5

# Define the device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class TextClassificationModel(nn.Module):
    def __init__(self, vocab_size, embed_dim, num_class, sparse):
        super(TextClassificationModel, self).__init__()
        self.embedding = nn.EmbeddingBag(vocab_size, embed_dim, sparse=sparse)
        self.fc = nn.Linear(embed_dim, num_class)
        self.init_weights()

    def init_weights(self):
        initrange = 0.5
        self.embedding.weight.data.uniform_(-initrange, initrange)
        self.fc.weight.data.uniform_(-initrange, initrange)
        self.fc.bias.data.zero_()

    def forward(self, text, offsets):
        embedded = self.embedding(text, offsets)
        return self.fc(embedded)

def get_power_consumption():
    query = 'kepler_container_joules_total'
    prometheus_url = 'http://prometheus-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090/api/v1/query'
    response = requests.get(prometheus_url, params={'query': query})
    result = response.json()['data']['result']
    return float(result[0]['value'][1]) if result else 0.0

def collate_batch(batch):
    label_list, text_list, offsets = [], [], [0]
    for (_label, _text) in batch:
        label_list.append(_label)
        processed_text = torch.tensor(_text, dtype=torch.int64)
        text_list.append(processed_text)
        offsets.append(processed_text.size(0))
    label_list = torch.tensor(label_list, dtype=torch.int64)
    offsets = torch.tensor(offsets[:-1]).cumsum(dim=0)
    text_list = torch.cat(text_list)
    return label_list.to(device), text_list.to(device), offsets.to(device)

def objective(trial):
    with mlflow.start_run():
        # Load dataset
        newsgroups_data = fetch_20newsgroups(subset='all')
        X_train, X_test, y_train, y_test = train_test_split(newsgroups_data.data, newsgroups_data.target, test_size=0.2, random_state=42)

        # Vectorize text data
        vectorizer = CountVectorizer(max_features=10000)
        X_train_vec = vectorizer.fit_transform(X_train)
        X_test_vec = vectorizer.transform(X_test)

        train_dataset = list(zip(y_train, X_train_vec.toarray()))
        test_dataset = list(zip(y_test, X_test_vec.toarray()))

        train_loader = data.DataLoader(train_dataset, batch_size=BATCHSIZE, shuffle=True, collate_fn=collate_batch)
        test_loader = data.DataLoader(test_dataset, batch_size=BATCHSIZE, shuffle=True, collate_fn=collate_batch)

        start_power = get_power_consumption()

        vocab_size = len(vectorizer.vocabulary_)
        embed_dim = trial.suggest_int("embed_dim", 32, 128)
        num_class = len(newsgroups_data.target_names)
        optimizer_name = trial.suggest_categorical("optimizer", ["Adam", "SGD"])  # Exclude RMSprop
        sparse = optimizer_name != "RMSprop"
        model = TextClassificationModel(vocab_size, embed_dim, num_class, sparse=sparse).to(device)

        criterion = nn.CrossEntropyLoss()
        lr = trial.suggest_float("lr", 1e-5, 1e-1, log=True)
        optimizer = getattr(optim, optimizer_name)(model.parameters(), lr=lr)

        # Log parameters
        mlflow.log_param("optimizer", optimizer_name)
        mlflow.log_param("learning_rate", lr)
        mlflow.log_param("embed_dim", embed_dim)

        mlflow.log_param("consumption", start_power)

        for epoch in range(EPOCHS):
            model.train()
            total_acc, total_count = 0, 0
            for idx, (label, text, offsets) in enumerate(train_loader):
                optimizer.zero_grad()
                predicted_label = model(text, offsets)
                loss = criterion(predicted_label, label)
                loss.backward()
                optimizer.step()
                total_acc += (predicted_label.argmax(1) == label).sum().item()
                total_count += label.size(0)

            # Log metrics for each epoch
            mlflow.log_metric("loss", loss.item(), step=epoch)
            mlflow.log_metric("accuracy", total_acc/total_count, step=epoch)
            mlflow.log_metric("consumption", get_power_consumption(), step=epoch)

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

    # Run the Flask app to expose metrics
    app.run(host="0.0.0.0", port=5000)
