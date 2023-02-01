import numpy as np
import torch
from torch import nn, Tensor


class BackprojectDepth(nn.Module):
    """Layer to transform a depth image into a point cloud

    Adapted from https://github.com/nianticlabs/monodepth2/blob/master/layers.py#L139
    Non-commercial license.
    https://github.com/nianticlabs/monodepth2/blob/master/layers.py#L139
    """

    def __init__(self, height: int, width: int) -> None:
        super().__init__()

        self.height = height
        self.width = width

        # pyre-fixme[6]: numpy types don't like range
        meshgrid = np.meshgrid(range(self.width), range(self.height), indexing="xy")
        id_coords = np.stack(meshgrid, axis=0).astype(np.float32)
        self.register_buffer(
            "id_coords",
            torch.from_numpy(id_coords),
            persistent=False,
        )

        self.register_buffer(
            "ones",
            torch.ones(1, 1, self.height * self.width),
            persistent=False,
        )

        pix_coords = torch.unsqueeze(
            torch.stack([self.id_coords[0].view(-1), self.id_coords[1].view(-1)], 0), 0
        )
        self.register_buffer(
            "pix_coords", torch.cat([pix_coords, self.ones], 1), persistent=False
        )

    def forward(self, depth: torch.Tensor, inv_K: torch.Tensor) -> torch.Tensor:
        bs = len(depth)
        cam_points = torch.matmul(
            inv_K[:, :3, :3], self.pix_coords[:bs].expand(bs, -1, -1)
        )
        cam_points = depth.view(bs, 1, -1) * cam_points
        cam_points = torch.cat([cam_points, self.ones.expand(bs, -1, -1)], 1)

        return cam_points


class Project3D(nn.Module):
    """Layer which projects 3D points into a camera with intrinsics K and at position T

    Adapted from https://github.com/nianticlabs/monodepth2/blob/master/layers.py#L139
    Non-commercial license.
    https://github.com/nianticlabs/monodepth2/blob/master/layers.py#L139
    """

    def __init__(self, height: int, width: int, eps: float = 1e-7) -> None:
        super().__init__()

        self.height = height
        self.width = width
        self.eps = eps

    def forward(self, points: Tensor, K: Tensor, T: Tensor) -> Tensor:
        bs = len(K)
        P = torch.matmul(K, T)[:, :3, :]

        cam_points = torch.matmul(P, points)

        pix_coords = cam_points[:, :2, :] / (
            cam_points[:, 2, :].unsqueeze(1) + self.eps
        )
        pix_coords = pix_coords.view(bs, 2, self.height, self.width)
        pix_coords = pix_coords.permute(0, 2, 3, 1)
        pix_coords[..., 0] /= self.width - 1
        pix_coords[..., 1] /= self.height - 1
        pix_coords = (pix_coords - 0.5) * 2
        return pix_coords