"""
Neural network implementation module
"""
from language.language import Language
from neural_net.training_generation import dfs_representation, generate_training_examples
import torch
from torch.utils.data import DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score
from neural_net.dataset import SequenceDataset
from networkx import DiGraph


class NeuralNetError(Exception):
    pass


class NeuralNet:
    """
    Neural network implementation for usage with the Genetic Viewer as its fitness function

    -- Parameters --
        language: Language to be used
        n_gen: Number of consecutive rules to be applied to the initial graphs when generating
            the training data

    -- Methods --
        predict(graph_before, graph_after, graph_final): Returns a prediction on the fitness of the
        (graph_before, graph_after, graph_final) sequence
    """

    def __init__(self, language: Language, n_gen: int, n_items: int = None, lr: float = 0.0001, 
                 num_epochs: int = 400, device_str: str = None, batch_size: int = 2**16) -> None:
        self.language = language
        self.n_gen = n_gen
        self.n_items = n_items
        self.lr = lr
        self.num_epochs = num_epochs
        if device_str is None:
            self.device = torch.device("cpu")
        else:
            self.device = torch.device(device_str)
        self.batch_size = batch_size
        train_set, test_set = self._prepare_for_training(language, n_gen, n_items)
        self.metrics = self._train(train_set, test_set)

    def init_weights(m):
        if isinstance(m, torch.nn.Linear):
            torch.nn.init.xavier_normal_(m.weight)
            torch.nn.init.constant_(m.bias, 0)
        
    def _evaluate_model(self, dataset, set_name=None, print_results=False) -> tuple[float, float]:
        """Returns evaluation metrics for the model (loss, accuracy, auc) on a DataSet"""
        net = self.net
        net.eval()
        criterion = self.criterion
        x = dataset.x
        y = dataset.y
        if self.device != torch.device("cpu"):
            x = x.to(torch.device("cpu"))
            y = y.to(torch.device("cpu"))
            net = net.to(torch.device("cpu"))
        with torch.no_grad():
            y_hat = net(x)
            loss = criterion(y_hat, y)
            predictions = (y_hat.squeeze() > 0.5) == y.squeeze()
            accuracy = predictions.sum() / predictions.numel()
            try:
                auc = roc_auc_score(y, y_hat)
            except ValueError:
                auc = accuracy
        if print_results:
            if set_name:
                print(f"{set_name}: ", end="")
            print(f"Loss: {loss:.3f}, Accuracy: {accuracy:.3f}, AUC: {auc:.3f}")
        return {"loss": loss, "accuracy": accuracy, "AUC": auc}

    def _prepare_for_training(self, language: Language, n_gen: int, n_items: int = None) -> None:
        """
        Generates training examples and initializes the network for training
        """
        self._data, self._labels, self._input_len = generate_training_examples(language, n_gen, n_items)
        self.net = torch.nn.Sequential(
            torch.nn.Linear(self._input_len * 3, 100),
            torch.nn.ReLU(),
            torch.nn.Linear(100, 1),
            torch.nn.Sigmoid()
        ).to(self.device)
        self.net.apply(NeuralNet.init_weights)
        self.criterion = torch.nn.BCELoss()
        self.optimizer = torch.optim.Adam(params=self.net.parameters(), lr=self.lr)
        x_train, x_test, y_train, y_test = train_test_split(self._data, self._labels, train_size=0.8)
        # x_val, x_test, y_val, y_test = train_test_split(x_test, y_test, train_size=0.5)
        train_set = SequenceDataset(x_train, y_train, device=self.device)
        test_set = SequenceDataset(x_test, y_test, device=self.device)
        # validation_set = SequenceDataset(x_val, y_val, device=self.device)
        return train_set, test_set
    
    def _calculate_metrics(self, train_set: SequenceDataset, test_set: SequenceDataset):
        """
        Calculates the loss and AUC of the neural network for the current epoch
        """
        net = self.net
        criterion = self.criterion
        y_hat_train = net(train_set.x)
        y_hat_test = net(test_set.x)
        loss_train = criterion(y_hat_train, train_set.y)
        loss_test = criterion(y_hat_test, test_set.y)
        auc_train = roc_auc_score(train_set.y, y_hat_train)
        auc_test = roc_auc_score(test_set.y, y_hat_test)
        return loss_train, loss_test, auc_train, auc_test
    
    def _train(self, train_set, test_set) -> None:
        """
        Starts training the neural network on the generated training sample
        """
        train_loader = DataLoader(train_set, batch_size=min(len(train_set), self.batch_size), shuffle=True)
        # validation_loader = DataLoader(validation_set, batch_size=min(len(validation_set), 1024), shuffle=False)
        net = self.net
        criterion = self.criterion
        optimizer = self.optimizer
        metrics_epoch = torch.empty(size=(self.num_epochs, 4), dtype=torch.float32, requires_grad=False)
        for epoch in range(self.num_epochs):
            net.train()
            # print(f"\rEpoch: {epoch + 1}/{self.num_epochs}", end='')
            for x, y in train_loader:
                optimizer.zero_grad()
                y_hat = net(x)
                loss = criterion(y_hat, y)
                loss.backward()
                optimizer.step()
            with torch.no_grad():
                metrics = self._calculate_metrics(train_set, test_set)
                metrics_epoch[epoch][0] = metrics[0]
                metrics_epoch[epoch][1] = metrics[1]
                metrics_epoch[epoch][2] = metrics[2]
                metrics_epoch[epoch][3] = metrics[3]
        # print()
        train_metrics = self._evaluate_model(train_set)
        test_metrics = self._evaluate_model(test_set)
        print(f"Final auc: {metrics_epoch[-1][3]} compared to {test_metrics['AUC']}")
        return {"train": train_metrics, "test": test_metrics}
    
    def predict(self, graph_before: DiGraph, graph_after: DiGraph, graph_final: DiGraph) -> float:
        representation = []
        graphs = [graph_before, graph_after, graph_final]
        for graph in graphs:
            graph_repr = dfs_representation(graph)
            if len(graph_repr) > self._input_len:
                raise NeuralNetError(f"Graph {graph} has more than allowed nodes ({len(graph_repr)}, \
                                       maximum allowed are {self._input_len})")
            representation.extend(graph_repr + (self._input_len - len(graph_repr)) * [0])
        return self.net(torch.tensor(representation, dtype=torch.float32, device=self.device))
