import os
import torch
import torch.nn as nn
import torch.optim as optim
import torch.utils.data as dt
from torch.utils.data import DataLoader, Dataset
from torchtext.datasets import IMDB
from torchtext.data.utils import get_tokenizer
from collections import Counter
import ray
from ray import tune
from ray.tune.schedulers import ASHAScheduler
import pytorch_lightning as pl
from ray.tune.integration.pytorch_lightning import TuneReportCallback

ray.init(address="auto", ignore_reinit_error=True)

# Custom Dataset for IMDB
class IMDBDataset(Dataset):
    def __init__(self, data, vocab, tokenizer, max_length=512):
        self.data = list(data)
        self.vocab = vocab
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        label, text = self.data[idx]
        # Convert label: 1 (pos) -> 1, 2 (neg) -> 0
        label = 1 if label == 2 else 0
        
        # Tokenize and convert to indices
        tokens = self.tokenizer(text)[:self.max_length]
        indices = [self.vocab.get(token, self.vocab['<unk>']) for token in tokens]
        
        # Pad to max_length
        if len(indices) < self.max_length:
            indices.extend([self.vocab['<pad>']] * (self.max_length - len(indices)))
        
        return torch.tensor(indices), torch.tensor(label, dtype=torch.long)

# Create vocabulary
def build_vocab(train_data, tokenizer, min_freq=5):
    counter = Counter()
    for _, text in train_data:
        counter.update(tokenizer(text))
    
    vocab = {'<pad>': 0, '<unk>': 1}
    for word, freq in counter.items():
        if freq >= min_freq:
            vocab[word] = len(vocab)
    
    return vocab

# Create a PyTorch Lightning Module for Text Classification
class LightningTextModel(pl.LightningModule):
    def __init__(self, config, vocab_size):
        super(LightningTextModel, self).__init__()
        self.config = config
        self.vocab_size = vocab_size
        
        # Embedding layer
        self.embedding = nn.Embedding(vocab_size, config["embedding_dim"], padding_idx=0)
        
        # Build network layers
        layers = []
        input_dim = config["embedding_dim"]
        
        for i in range(config["n_layers"]):
            output_dim = int(config["n_units_l{}".format(i)])
            layers.append(nn.Linear(input_dim, output_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(config["dropout"]))
            input_dim = output_dim
        
        # Output layer for binary classification
        layers.append(nn.Linear(input_dim, 2))
        self.layers = nn.Sequential(*layers)
        
        self.criterion = nn.CrossEntropyLoss()
    
    def forward(self, x):
        # x shape: (batch_size, seq_length)
        embedded = self.embedding(x)  # (batch_size, seq_length, embedding_dim)
        # Global average pooling
        pooled = embedded.mean(dim=1)  # (batch_size, embedding_dim)
        return self.layers(pooled)
    
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
        pred = output.argmax(dim=1)
        accuracy = (pred == target).float().mean()
        self.log("val_loss", loss, on_step=False, on_epoch=True, prog_bar=True)
        self.log("val_accuracy", accuracy, on_step=False, on_epoch=True, prog_bar=True)
        return {"val_loss": loss, "val_accuracy": accuracy}
    
    def configure_optimizers(self):
        optimizer_name = self.config["optimizer"]
        lr = self.config["lr"]
        optimizer_class = getattr(optim, optimizer_name)
        return optimizer_class(self.parameters(), lr=lr)

# Global variables for data (to avoid reloading in each trial)
train_dataset = None
val_dataset = None
vocab_size = None

def prepare_data():
    global train_dataset, val_dataset, vocab_size
    
    if train_dataset is not None:
        return
    
    print("Loading IMDB dataset...")
    tokenizer = get_tokenizer('basic_english')
    
    # Load IMDB data
    train_data = list(IMDB(split='train'))
    test_data = list(IMDB(split='test'))
    
    print("Building vocabulary...")
    vocab = build_vocab(train_data, tokenizer)
    vocab_size = len(vocab)
    
    print(f"Vocabulary size: {vocab_size}")
    
    # Create datasets
    train_dataset = IMDBDataset(train_data, vocab, tokenizer, max_length=256)
    val_dataset = IMDBDataset(test_data, vocab, tokenizer, max_length=256)

# Training function for Ray Tune
def train_text_lightning(config):
    global train_dataset, val_dataset, vocab_size
    
    prepare_data()
    
    model = LightningTextModel(config, vocab_size)
    metrics = {"val_loss": "val_loss", "val_accuracy": "val_accuracy"}
    
    # Create data loaders
    train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=64, shuffle=False, num_workers=0)
    
    # Ray Tune's callback
    callback = TuneReportCallback(metrics, on="validation_end")
    trainer = pl.Trainer(
        max_epochs=1,
        enable_checkpointing=False,
        logger=False,
        enable_progress_bar=False,
        callbacks=[callback],
        num_sanity_val_steps=0
    )
    trainer.fit(model, train_loader, val_loader)

# Search space for text classification
search_space = {
    "n_layers": tune.choice([1, 2, 3]),
    "n_units_l0": tune.choice([64, 128, 256]),
    "n_units_l1": tune.choice([64, 128, 256]),
    "n_units_l2": tune.choice([64, 128, 256]),
    "embedding_dim": tune.choice([50, 100, 200]),
    "dropout": tune.uniform(0.2, 0.5),
    "lr": tune.loguniform(1e-5, 1e-2),
    "optimizer": tune.choice(["Adam", "RMSprop", "SGD"])
}

scheduler = ASHAScheduler(
    metric="val_loss",
    mode="min",
    max_t=1,
    grace_period=1,
    reduction_factor=2,
    brackets=1
)

analysis = tune.run(
    train_text_lightning,
    resources_per_trial={"cpu": 1},
    config=search_space,
    num_samples=10,
    max_concurrent_trials=5,
    scheduler=scheduler,
    storage_path="/tmp/ray_results"
)

# Print best trial results
best_trial = analysis.get_best_trial("val_loss", "min")
print("Best trial config: {}".format(best_trial.config))
print("Best trial final validation loss: {}".format(best_trial.last_result["val_loss"]))
print("Best trial final validation accuracy: {}".format(best_trial.last_result["val_accuracy"]))

best_trial = analysis.get_best_trial("val_accuracy", "max")
best_val_acc = best_trial.last_result["val_accuracy"]
print(f"BEST_VAL_ACCURACY: {best_val_acc}")

# Write to file for easy retrieval
with open("/tmp/best_val_accuracy.txt", "w") as f:
    f.write(str(best_val_acc))

