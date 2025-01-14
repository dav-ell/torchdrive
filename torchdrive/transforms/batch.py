from abc import ABC, abstractmethod
from dataclasses import replace
from typing import Tuple

from torchdrive.data import Batch
from torchdrive.transforms.mat import random_translation, random_z_rotation


class BatchTransform(ABC):
    """
    BatchTransform is a protocol for batch transforms.
    """

    @abstractmethod
    def __call__(self, batch: Batch) -> Batch:
        ...


class Identity(BatchTransform):
    """
    Returns the original batch.
    """

    def __call__(self, batch: Batch) -> Batch:
        return batch


class Compose(BatchTransform):
    """
    Compose multiple BatchTransforms together.
    """

    def __init__(self, *transforms: BatchTransform) -> None:
        self.transforms: Tuple[BatchTransform] = transforms

    def __call__(self, batch: Batch) -> Batch:
        for transform in self.transforms:
            batch = transform(batch)
        return batch


class NormalizeCarPosition(BatchTransform):
    """
    Normalize car position makes the start_frame's car transform the identity
    matrix and all other frame positions relative to that.
    """

    def __init__(self, start_frame: int) -> None:
        self.start_frame = start_frame

    def __call__(self, batch: Batch) -> Batch:
        start_T = batch.cam_T[:, self.start_frame]
        inv_start_T = start_T.unsqueeze(1).pinverse()
        cam_T = inv_start_T.matmul(batch.cam_T)
        long_cam_T, long_cam_T_mask, long_cam_T_lengths = batch.long_cam_T
        long_cam_T = inv_start_T.matmul(long_cam_T)

        return replace(
            batch,
            cam_T=cam_T,
            long_cam_T=(long_cam_T, long_cam_T_mask, long_cam_T_lengths),
        )


class RandomRotation(BatchTransform):
    """
    RandomRotation applies a random z rotation around the origin to the car
    position transform.
    """

    def __call__(self, batch: Batch) -> Batch:
        rot = random_z_rotation(batch.batch_size(), batch.cam_T.device).unsqueeze(1)
        cam_T = batch.cam_T.matmul(rot)
        long_cam_T, long_cam_T_mask, long_cam_T_lengths = batch.long_cam_T
        long_cam_T = long_cam_T.matmul(rot)
        return replace(
            batch,
            cam_T=cam_T,
            long_cam_T=(long_cam_T, long_cam_T_mask, long_cam_T_lengths),
        )


class RandomTranslation(BatchTransform):
    """
    RandomRotation applies a translation around the origin to the car
    position transform.
    """

    def __init__(self, distances: Tuple[float, float, float]) -> None:
        self.distances = distances

    def __call__(self, batch: Batch) -> Batch:
        rot = random_translation(
            batch_size=batch.batch_size(),
            distances=self.distances,
            device=batch.cam_T.device,
        ).unsqueeze(1)
        cam_T = batch.cam_T.matmul(rot)
        long_cam_T, long_cam_T_mask, long_cam_T_lengths = batch.long_cam_T
        long_cam_T = long_cam_T.matmul(rot)
        return replace(
            batch,
            cam_T=cam_T,
            long_cam_T=(long_cam_T, long_cam_T_mask, long_cam_T_lengths),
        )
