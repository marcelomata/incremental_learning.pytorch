''' Incremental-Classifier Learning
 Authors : Khurram Javed, Muhammad Talha Paracha
 Maintainer : Khurram Javed
 Lab : TUKL-SEECS R&D Lab
 Email : 14besekjaved@seecs.edu.pk '''

import math

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn import init


class DownsampleStride(nn.Module):
    def __init__(self, n=2):
        super(DownsampleStride, self).__init__()
        self._n = n

    def forward(self, x):
        return x[..., ::2, ::2]


class ResidualBlock(nn.Module):
    expansion = 1

    def __init__(self, inplanes, increase_dim=False, last=False):
        super(ResidualBlock, self).__init__()

        self.increase_dim = increase_dim

        if increase_dim:
            first_stride = 2
            planes = inplanes * 2
        else:
            first_stride = 1
            planes = inplanes

        self.conv_a = nn.Conv2d(inplanes, planes, kernel_size=3, stride=first_stride, padding=1, bias=False)
        self.bn_a = nn.BatchNorm2d(planes)

        self.conv_b = nn.Conv2d(planes, planes, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn_b = nn.BatchNorm2d(planes)

        if increase_dim:
            self.downsample = DownsampleStride()
            self.pad = lambda x: torch.cat((x, x.mul(0)), 1)
        self.last = last

    def forward(self, x):
        y = self.conv_a(x)
        y = self.bn_a(y)
        y = F.relu(y, inplace=True)

        y = self.conv_b(y)
        y = self.bn_b(y)

        if self.increase_dim:
            x = self.downsample(x)
            x = self.pad(x)

        y = x + y

        return y


class PreActResidualBlock(nn.Module):
    expansion = 1

    def __init__(self, inplanes, increase_dim=False, last=False):
        super().__init__()

        self.increase_dim = increase_dim

        if increase_dim:
            first_stride = 2
            planes = inplanes * 2
        else:
            first_stride = 1
            planes = inplanes

        self.bn_a = nn.BatchNorm2d(inplanes)
        self.conv_a = nn.Conv2d(inplanes, planes, kernel_size=3, stride=first_stride, padding=1, bias=False)

        self.bn_b = nn.BatchNorm2d(planes)
        self.conv_b = nn.Conv2d(planes, planes, kernel_size=3, stride=1, padding=1, bias=False)

        if increase_dim:
            self.downsample = DownsampleStride()
            self.pad = lambda x: torch.cat((x, x.mul(0)), 1)
        self.last = last

    def forward(self, x):
        y = self.bn_a(x)
        y = F.relu(y, inplace=True)
        y = self.conv_a(x)

        y = self.bn_b(y)
        y = F.relu(y, inplace=True)
        y = self.conv_b(y)

        if self.increase_dim:
            x = self.downsample(x)
            x = self.pad(x)

        y = x + y

        return y


class CifarResNet(nn.Module):
    """
    ResNet optimized for the Cifar Dataset, as specified in
    https://arxiv.org/abs/1512.03385.pdf
    """

    def __init__(self, n=5, channels=3, preact=False, zero_residual=True, **kwargs):
        """ Constructor
        Args:
          depth: number of layers.
          num_classes: number of classes
          base_width: base width
        """
        if kwargs:
            raise ValueError("Unused kwargs: {}.".format(kwargs))

        Block = ResidualBlock if not preact else PreActResidualBlock

        super(CifarResNet, self).__init__()

        self.conv_1_3x3 = nn.Conv2d(channels, 16, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn_1 = nn.BatchNorm2d(16)

        self.inplanes = 16
        self.stage_1 = self._make_layer(Block, 16, increase_dim=False, n=n)
        self.stage_2 = self._make_layer(Block, 16, increase_dim=True, n=n-1)
        self.stage_3 = self._make_layer(Block, 32, increase_dim=True, n=n-2)
        self.stage_4 = Block(64, increase_dim=False, last=True)

        self.avgpool = nn.AvgPool2d(8)
        self.out_dim = 64

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

        if zero_residual:
            for m in self.modules():
                if isinstance(m, ResidualBlock):
                    nn.init.constant_(m.bn_b.weight, 0)

    def _make_layer(self, Block, planes, increase_dim=False, last=False, n=None):
        layers = []

        if increase_dim:
            layers.append(
                Block(planes, increase_dim=True)
            )
            planes = 2 * planes

        for i in range(n):
            layers.append(Block(planes))

        return nn.Sequential(*layers)

    def forward(self, x, attention_hook=False):
        x = self.conv_1_3x3(x)
        x = F.relu(self.bn_1(x), inplace=True)

        x_s1 = self.stage_1(x)
        x_s2 = self.stage_2(x_s1)
        x_s3 = self.stage_3(x_s2)
        x_s4 = self.stage_4(x_s3)

        raw_features = self.end_features(x_s4)
        features = self.end_features(F.relu(x_s4, inplace=False))

        if attention_hook:
            return raw_features, features, [x_s1, x_s2, x_s3, x_s4]
        return raw_features, features

    def end_features(self, x):
        x = self.avgpool(x)
        x = x.view(x.size(0), -1)

        return x


def resnet_rebuffi(n=5, **kwargs):
    return CifarResNet(n=n, **kwargs)
