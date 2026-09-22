"""Level 3 models and losses. Everything is selected by config name.

Models
    unet_small   U-Net from scratch (base width 32, 4 levels) — the plan's step 1
    unet_r18     smp.Unet with a ResNet-18 encoder — step 2 (ImageNet weights
                 optional; with 2-4 input channels smp re-initialises conv1)
Losses (all ignore IGNORE=255)
    ce           cross-entropy, optional class weights
    dice, focal, dice_ce
    cropw_ce     cross-entropy where labelled-flood pixels on cropland (and,
                 by config, vegetation) get an extra weight — the only loss
                 that targets the hypothesis directly
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from . import strata
from .data import IGNORE


# --- models -----------------------------------------------------------------

def _block(i, o):
    return nn.Sequential(nn.Conv2d(i, o, 3, padding=1, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True),
                         nn.Conv2d(o, o, 3, padding=1, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True))


class UNetSmall(nn.Module):
    def __init__(self, in_ch: int, base: int = 32, n_classes: int = 2):
        super().__init__()
        w = [base, base * 2, base * 4, base * 8]
        self.enc = nn.ModuleList([_block(in_ch, w[0]), _block(w[0], w[1]), _block(w[1], w[2])])
        self.mid = _block(w[2], w[3])
        self.up = nn.ModuleList([nn.ConvTranspose2d(w[3], w[2], 2, 2), nn.ConvTranspose2d(w[2], w[1], 2, 2), nn.ConvTranspose2d(w[1], w[0], 2, 2)])
        self.dec = nn.ModuleList([_block(w[3], w[2]), _block(w[2], w[1]), _block(w[1], w[0])])
        self.head = nn.Conv2d(w[0], n_classes, 1)

    def forward(self, x):
        skips = []
        for e in self.enc:
            x = e(x)
            skips.append(x)
            x = F.max_pool2d(x, 2)
        x = self.mid(x)
        for up, dec, s in zip(self.up, self.dec, reversed(skips)):
            x = dec(torch.cat([up(x), s], 1))
        return self.head(x)


def build_model(name: str, in_ch: int, pretrained: bool = False) -> nn.Module:
    if name == "unet_small":
        return UNetSmall(in_ch)
    if name == "unet_r18":
        import segmentation_models_pytorch as smp
        return smp.Unet("resnet18", encoder_weights="imagenet" if pretrained else None, in_channels=in_ch, classes=2)
    raise ValueError(name)


# --- losses -----------------------------------------------------------------

def _valid(y):
    return y != IGNORE


def ce_loss(logits, y, land=None, class_weight=None, crop_weight: float = 1.0, veg_weight: float = 1.0):
    """Cross-entropy with per-pixel weights. crop/veg weights apply to labelled-flood pixels on that land type."""
    w = torch.ones_like(y, dtype=torch.float32)
    if land is not None and (crop_weight != 1.0 or veg_weight != 1.0):
        flood = y == 1
        w = torch.where(flood & (land == strata.CROPLAND), torch.full_like(w, crop_weight), w)
        w = torch.where(flood & (land == strata.VEGETATION), torch.full_like(w, veg_weight), w)
    cw = torch.tensor(class_weight, dtype=torch.float32, device=logits.device) if class_weight else None
    per_px = F.cross_entropy(logits, y, weight=cw, ignore_index=IGNORE, reduction="none")
    m = _valid(y)
    return (per_px * w)[m].sum() / w[m].sum().clamp(min=1)


def dice_loss(logits, y, eps: float = 1.0):
    m = _valid(y)
    p = torch.softmax(logits, 1)[:, 1][m]
    t = (y[m] == 1).float()
    return 1 - (2 * (p * t).sum() + eps) / (p.sum() + t.sum() + eps)


def focal_loss(logits, y, gamma: float = 2.0):
    ce = F.cross_entropy(logits, y, ignore_index=IGNORE, reduction="none")
    m = _valid(y)
    pt = torch.exp(-ce[m])
    return (((1 - pt) ** gamma) * ce[m]).mean()


def build_loss(cfg: dict):
    name = cfg.get("loss", "ce")
    cw = cfg.get("class_weight")
    crop_w, veg_w = float(cfg.get("crop_weight", 1.0)), float(cfg.get("veg_weight", 1.0))
    if name == "ce":
        return lambda lg, y, land: ce_loss(lg, y, None, cw)
    if name == "cropw_ce":
        return lambda lg, y, land: ce_loss(lg, y, land, cw, crop_w, veg_w)
    if name == "dice":
        return lambda lg, y, land: dice_loss(lg, y)
    if name == "focal":
        return lambda lg, y, land: focal_loss(lg, y, float(cfg.get("gamma", 2.0)))
    if name == "dice_ce":
        return lambda lg, y, land: 0.5 * dice_loss(lg, y) + 0.5 * ce_loss(lg, y, None, cw)
    raise ValueError(name)
