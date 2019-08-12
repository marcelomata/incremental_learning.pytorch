import datetime

import numpy as np
import torch


def to_onehot(targets, n_classes):
    onehot = torch.zeros(targets.shape[0], n_classes).to(targets.device)
    onehot.scatter_(dim=1, index=targets.long().view(-1, 1), value=1.)
    return onehot


def _check_loss(loss):
    return not bool(torch.isnan(loss).item()) and bool((loss >= 0.).item())


def compute_accuracy(ypred, ytrue, task_size=10):
    all_acc = {}

    all_acc["total"] = round((ypred == ytrue).sum() / len(ytrue), 3)

    for class_id in range(0, np.max(ytrue), task_size):
        idxes = np.where(
                np.logical_and(ytrue >= class_id, ytrue < class_id + task_size)
        )[0]

        label = "{}-{}".format(
                str(class_id).rjust(2, "0"),
                str(class_id + task_size - 1).rjust(2, "0")
        )
        all_acc[label] = round((ypred[idxes] == ytrue[idxes]).sum() / len(idxes), 3)

    return all_acc


def get_date():
    return datetime.datetime.now().strftime("%Y%m%d")


def extract_features(model, loader):
    targets, features = [], []

    for _inputs, _targets, _ in loader:
        _targets = _targets.numpy()
        _features = model.extract(_inputs.to(model.device)).detach().cpu().numpy()

        features.append(_features)
        targets.append(_targets)

    return np.concatenate(features), np.concatenate(targets)


def classify(model, loader):
    targets, predictions = [], []

    for _inputs, _targets, _ in loader:
        _targets = _targets.numpy()
        outputs = model(_inputs.to(model.device))
        if not isinstance(outputs, list):
            outputs = [outputs]

        preds = outputs[-1].argmax(dim=1).detach().cpu().numpy()

        predictions.append(preds)
        targets.append(_targets)

    return np.concatenate(predictions), np.concatenate(targets)
