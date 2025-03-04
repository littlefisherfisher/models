import oneflow.experimental as flow

import argparse
import numpy as np
import os
import time

from models.shufflenetv2 import shufflenetv2_x0dot5, shufflenetv2_x1
from utils.ofrecord_data_utils import OFRecordDataLoader

model_dict = {
    "shufflenetv2_x0.5": shufflenetv2_x0dot5,
    "shufflenetv2_x1.0": shufflenetv2_x1,
}


def _parse_args():
    parser = argparse.ArgumentParser("flags for train shufflenet")
    parser.add_argument(
        "--save_checkpoint_path",
        type=str,
        default="./checkpoints",
        help="save checkpoint root dir",
    )
    parser.add_argument(
        "--load_checkpoint", type=str, default="", help="load checkpoint"
    )
    parser.add_argument(
        "--ofrecord_path", type=str, default="./ofrecord", help="dataset path"
    )
    # training hyper-parameters
    parser.add_argument(
        "--learning_rate", type=float, default=0.001, help="learning rate"
    )
    parser.add_argument("--mom", type=float, default=0.9, help="momentum")
    parser.add_argument("--epochs", type=int, default=1000, help="training epochs")
    parser.add_argument(
        "--train_batch_size", type=int, default=32, help="train batch size"
    )
    parser.add_argument("--val_batch_size", type=int, default=32, help="val batch size")
    parser.add_argument(
        "--model",
        type=str,
        default="shufflenetv2_x0.5",
        help="choose a model from shufflenetv2_x0.5, shufflenetv2_x1.0",
    )

    return parser.parse_args()


def main(args):
    flow.enable_eager_execution()
    flow.InitEagerGlobalSession()

    train_data_loader = OFRecordDataLoader(
        ofrecord_root=args.ofrecord_path,
        mode="train",
        dataset_size=9469,  # NOTE(Liang Depeng): needs to explictly set the dataset size
        batch_size=args.train_batch_size,
    )

    val_data_loader = OFRecordDataLoader(
        ofrecord_root=args.ofrecord_path,
        mode="val",
        dataset_size=3925,
        batch_size=args.val_batch_size,
    )

    # oneflow init
    start_t = time.time()
    shufflenet_module = model_dict[args.model]()
    if args.load_checkpoint != "":
        shufflenet_module.load_state_dict(flow.load(args.load_checkpoint))
    end_t = time.time()
    print("init time : {}".format(end_t - start_t))

    of_cross_entropy = flow.nn.CrossEntropyLoss()

    shufflenet_module.to("cuda")
    of_cross_entropy.to("cuda")

    of_sgd = flow.optim.SGD(
        shufflenet_module.parameters(), lr=args.learning_rate, momentum=args.mom
    )

    of_losses = []
    all_samples = len(val_data_loader) * args.val_batch_size
    print_interval = 50

    for epoch in range(args.epochs):
        shufflenet_module.train()

        for b in range(len(train_data_loader)):
            image, label = train_data_loader.get_batch()

            # oneflow train
            start_t = time.time()
            image = image.to("cuda")
            label = label.to("cuda")
            logits = shufflenet_module(image)
            loss = of_cross_entropy(logits, label)
            loss.backward()
            of_sgd.step()
            of_sgd.zero_grad()
            end_t = time.time()
            if b % print_interval == 0:
                l = loss.numpy()[0]
                of_losses.append(l)
                print(
                    "epoch {} train iter {} oneflow loss {}, train time : {}".format(
                        epoch, b, l, end_t - start_t
                    )
                )

        print("epoch %d train done, start validation" % epoch)

        shufflenet_module.eval()
        correct_of = 0.0
        for b in range(len(val_data_loader)):
            image, label = val_data_loader.get_batch()

            start_t = time.time()
            image = image.to("cuda")
            with flow.no_grad():
                logits = shufflenet_module(image)
                predictions = logits.softmax()
            of_predictions = predictions.numpy()
            clsidxs = np.argmax(of_predictions, axis=1)

            label_nd = label.numpy()
            for i in range(args.val_batch_size):
                if clsidxs[i] == label_nd[i]:
                    correct_of += 1
            end_t = time.time()

        print("epoch %d, oneflow top1 val acc: %f" % (epoch, correct_of / all_samples))

        flow.save(
            shufflenet_module.state_dict(),
            os.path.join(
                args.save_checkpoint_path,
                "epoch_%d_val_acc_%f" % (epoch, correct_of / all_samples),
            ),
        )

    writer = open("of_losses.txt", "w")
    for o in of_losses:
        writer.write("%f\n" % o)
    writer.close()


if __name__ == "__main__":
    args = _parse_args()
    main(args)
