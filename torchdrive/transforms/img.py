from typing import Optional

import torch
from matplotlib import cm


@torch.no_grad()
def normalize_img_cuda(src: torch.Tensor) -> torch.Tensor:
    """
    Normalizes the provided image range to lows P0.1 and highs P99 and returns
    the tensor.

    Args:
        src: [..., ch, h, w]
    """
    src = src.detach()
    # q = 0.999
    flat = src.flatten(-2, -1)
    quantiles = torch.quantile(
        flat, torch.tensor((0.001, 0.99), device=src.device), dim=-1
    )
    max = quantiles[1].unsqueeze(-1).unsqueeze(-1)
    min = quantiles[0].unsqueeze(-1).unsqueeze(-1)
    new = (src - min).div_(max - min)
    new = new.clamp_(0, 1)
    return new


@torch.no_grad()
def normalize_img(src: torch.Tensor) -> torch.Tensor:
    """
    Normalizes the provided image and returns a CPU tensor.
    """
    return normalize_img_cuda(src).cpu()


def normalize_mask(src: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """
    Normalizes the image based on the masked region.
    """
    bs = src.size(0)
    ch = src.size(1)
    out = src.clone()
    for i in range(bs):
        masked = src[i].permute(1, 2, 0)[(mask[i].squeeze(0) > 0.5)]
        if masked.numel() == 0:
            continue
        std, mean = torch.std_mean(masked, dim=0)
        assert std.size(-1) == ch
        out[i] = (out[i] - mean.view(1, ch, 1, 1)) / std.clamp(min=1e-7).view(
            1, ch, 1, 1
        )

    return out


@torch.no_grad()
def render_color(
    img: torch.Tensor,
    max: Optional[float] = None,
    min: Optional[float] = None,
    palette: str = "magma",
) -> torch.Tensor:
    """
    Renders an array into colors with the specified palette.

    Args:
        img: input tensor [H, W], float
    Returns:
        output tensor [3, H, W], float, cpu
    """
    img = img.detach().float()
    cmap = cm.get_cmap(palette)
    N = 1000
    colors = torch.tensor([cmap(i / N)[:3] for i in range(N)], device=img.device)

    if min is None:
        min = img.min()
    if max is None:
        max = img.max()

    if max == min:
        img = torch.zeros(img.shape)
    else:
        img = (img - min) / (max - min) * (N - 1)
    mapped = colors[img.long()]
    if len(mapped.shape) != 3:
        print(mapped.shape)
    return mapped.permute(2, 0, 1).cpu()
