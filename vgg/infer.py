import oneflow.experimental as flow

import argparse
import numpy as np
import time

from models.vgg import vgg19_bn, vgg16_bn, vgg19, vgg16
from utils.imagenet1000_clsidx_to_labels import clsidx_2_labels
from utils.numpy_data_utils import load_image

model_dict = {
    "vgg16": vgg16,
    "vgg19": vgg19,
    "vgg16_bn": vgg16_bn,
    "vgg19_bn": vgg19_bn,
}


def _parse_args():
    parser = argparse.ArgumentParser("flags for test vgg")
    parser.add_argument(
        "--model_path",
        type=str,
        default="vgg_imagenet_pretrain_model/",
        help="model path",
    )
    parser.add_argument("--image_path", type=str, default="", help="input image path")
    parser.add_argument(
        "--model",
        type=str,
        default="vgg19_bn",
        help="choose from vgg16, vgg19, vgg16_bn, vgg19_bn",
    )
    return parser.parse_args()


def main(args):
    assert args.model in model_dict
    print("Predicting using", args.model, "...")
    flow.env.init()
    flow.enable_eager_execution()
    start_t = time.time()
    vgg_module = model_dict[args.model]()
    end_t = time.time()
    print("init time : {}".format(end_t - start_t))

    start_t = time.time()
    pretrain_models = flow.load(args.model_path)
    vgg_module.load_state_dict(pretrain_models)
    end_t = time.time()
    print("load params time : {}".format(end_t - start_t))

    vgg_module.eval()
    vgg_module.to("cuda")

    start_t = time.time()
    image = load_image(args.image_path)
    image = flow.Tensor(image, device=flow.device("cuda"))
    predictions = vgg_module(image).softmax()
    predictions = predictions.numpy()
    end_t = time.time()
    print("infer time : {}".format(end_t - start_t))
    clsidx = np.argmax(predictions)
    print(
        "predict prob: %f, class name: %s"
        % (np.max(predictions), clsidx_2_labels[clsidx])
    )


if __name__ == "__main__":
    args = _parse_args()
    main(args)
