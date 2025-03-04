import unittest
from typing import Dict
from unittest.mock import MagicMock

import torch

from torchdrive.data import dummy_batch

from torchdrive.tasks.bev import Context
from torchdrive.tasks.voxel import axis_grid, VoxelTask

VOXEL_LOSSES = [
    "tvl1",
    "lossproj-voxel/right/o1",
    "lossproj-voxel/left/o1",
    "lossproj-voxel/right/o0",
    "lossproj-voxel/left/o0",
    "lossproj-voxel/right/o-1",
    "lossproj-voxel/left/o-1",
    "lossproj-cam/right/o1",
    "lossproj-cam/left/o1",
    "lossproj-cam/right/o0",
    "lossproj-cam/left/o0",
    "lossproj-cam/right/o-1",
    "lossproj-cam/left/o-1",
    "losssmooth-voxel-disp/left",
    "losssmooth-voxel-disp/right",
    "losssmooth-cam-disp/left",
    "losssmooth-cam-disp/right",
    #"losssmooth-cam-vel/left",
    #"losssmooth-cam-vel/right",
]

SEMANTIC_LOSSES = [
    "semantic-voxel/left",
    "semantic-voxel/right",
    "semantic-cam/left",
    "semantic-cam/right",
    #"losssmooth-voxel-vel/left",
    #"losssmooth-voxel-vel/right",
]

STEREOSCOPIC_LOSSES = [
    "lossstereoscopic-voxel/left/right",
    "lossstereoscopic-cam/left/right",
]


class TestVoxel(unittest.TestCase):
    def _assert_loss_shapes(self, losses: Dict[str, torch.Tensor]) -> None:
        for k, v in losses.items():
            self.assertEqual(v.shape, (), k)

    def test_voxel_task(self) -> None:
        device = torch.device("cpu")
        cameras = ["left", "right"]
        m = VoxelTask(
            cameras=cameras,
            cam_shape=(320, 240),
            cam_feats_shape=(320 // 16, 240 // 16),
            dim=4,
            hr_dim=5,
            cam_dim=6,
            height=12,
            device=device,
            render_batch_size=1,
            n_pts_per_ray=10,
            offsets=(-1, 0, 1),
        ).to(device)
        batch = dummy_batch().to(device)
        ctx = Context(
            log_img=True,
            log_text=True,
            global_step=0,
            writer=MagicMock(),
            start_frame=1,
            scaler=None,
            name="det",
            output="",
            weights=batch.weight,
            cam_feats={cam: torch.rand(2, 6, 320 // 16, 240 // 16) for cam in cameras},
        )
        bev = torch.rand(2, 5, 4, 4, device=device)
        losses = m(ctx, batch, bev)
        ctx.backward(losses)
        self.assertCountEqual(losses.keys(), VOXEL_LOSSES)
        self._assert_loss_shapes(losses)

    def test_semantic_voxel_task(self) -> None:
        device = torch.device("cpu")
        cameras = ["left", "right"]
        m = VoxelTask(
            cameras=cameras,
            cam_shape=(320, 240),
            cam_feats_shape=(320 // 16, 240 // 16),
            dim=4,
            cam_dim=4,
            hr_dim=5,
            height=12,
            device=device,
            semantic=["left"],
            offsets=(-1, 0, 1),
        )
        batch = dummy_batch()
        ctx = Context(
            log_img=True,
            log_text=True,
            global_step=0,
            writer=MagicMock(),
            start_frame=1,
            scaler=None,
            name="det",
            output="",
            weights=batch.weight,
            cam_feats={cam: torch.rand(2, 4, 320 // 16, 240 // 16) for cam in cameras},
        )
        bev = torch.rand(2, 5, 4, 4)
        losses = m(ctx, batch, bev)
        ctx.backward(losses)
        self.assertCountEqual(
            losses.keys(),
            SEMANTIC_LOSSES + VOXEL_LOSSES,
        )
        self._assert_loss_shapes(losses)

    def test_stereoscopic_voxel_task(self) -> None:
        device = torch.device("cpu")
        cameras = ["left", "right"]
        m = VoxelTask(
            cameras=cameras,
            cam_shape=(320, 240),
            cam_feats_shape=(320 // 16, 240 // 16),
            dim=4,
            cam_dim=4,
            hr_dim=5,
            height=12,
            device=device,
            semantic=["left"],
            camera_overlap={
                "left": ["right"],
                "right": [],
            },
            offsets=(-1, 0, 1),
        )
        batch = dummy_batch()
        ctx = Context(
            log_img=True,
            log_text=True,
            global_step=0,
            writer=MagicMock(),
            start_frame=1,
            scaler=None,
            name="det",
            output="",
            weights=batch.weight,
            cam_feats={cam: torch.rand(2, 4, 320 // 16, 240 // 16) for cam in cameras},
        )
        bev = torch.rand(2, 5, 4, 4)
        losses = m(ctx, batch, bev)
        ctx.backward(losses)
        self.assertCountEqual(
            losses.keys(),
            STEREOSCOPIC_LOSSES + SEMANTIC_LOSSES + VOXEL_LOSSES,
        )
        self._assert_loss_shapes(losses)

    def test_axis_grid(self) -> None:
        grid, color = axis_grid(torch.rand(2, 1, 3, 4, 5))
        self.assertEqual(grid.shape, (2, 1, 3, 4, 5))
        self.assertEqual(color.shape, (2, 3, 3, 4, 5))
