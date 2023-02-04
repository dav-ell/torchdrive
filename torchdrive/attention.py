# pyre-ignore-all-errors[21]: missing optional imports

from typing import Optional, Protocol

import torch
import torch.nn.functional as F

try:
    from flash_attn.flash_attn_interface import flash_attn_unpadded_kvpacked_func

    HAS_FLASH_ATTN = True
except ImportError:
    HAS_FLASH_ATTN = False

try:
    from xformers.ops import memory_efficient_attention

    HAS_XFORMERS = True
except ImportError as e:
    HAS_XFORMERS = False


class AttentionType(Protocol):
    def __call__(
        self,
        q: torch.Tensor,
        kv: torch.Tensor,
        dim: int,
        num_heads: int,
        dropout_p: float = 0.0,
        attn_bias: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        ...


def attention(
    q: torch.Tensor,
    kv: torch.Tensor,
    dim: int,
    num_heads: int,
    dropout_p: float = 0.0,
    attn_bias: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    """
    attention is a dispatcher for multiheaded attention and will use the most
    efficient option that's available in the current environment for the
    specific dtype/device.

    Backends (in order of preference):
    * xformers (everything)
    * flash_attn (cuda, fp16/bfloat16 only)
    * naive pytorch (everything)

    Args:
        q: [BS, num_queries, dim]
        kv: [BS, num_kvs, dim*2]
    Returns:
        [BS, num_queries, dim]
    """
    if HAS_XFORMERS and not (dropout_p != 0.0 and not q.is_cuda):
        return xformers_attention(q, kv, dim, num_heads, dropout_p, attn_bias)
    # if HAS_FLASH_ATTN and q.is_cuda and q.dtype in (torch.half, torch.bfloat16):
    #    return flash_attention(q, kv, dim, num_heads, dropout_p)
    return naive_attention(q, kv, dim, num_heads, dropout_p, attn_bias)


def flash_attention(
    q: torch.Tensor,
    kv: torch.Tensor,
    dim: int,
    num_heads: int,
    dropout_p: float = 0.0,
    attn_bias: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    assert attn_bias is None, "flash_attention doesn't support attn_bias"

    BS = q.shape[0]
    q_seqlen = q.shape[1]
    k_seqlen = kv.shape[1]

    out = flash_attn_unpadded_kvpacked_func(
        q=q.reshape(-1, num_heads, dim // num_heads).contiguous(),
        kv=kv.reshape(-1, 2, num_heads, dim // num_heads).contiguous(),
        cu_seqlens_q=torch.arange(
            0,
            (BS + 1) * q_seqlen,
            step=q_seqlen,
            device=q.device,
            dtype=torch.int32,
        ),
        cu_seqlens_k=torch.arange(
            0,
            (BS + 1) * k_seqlen,
            step=k_seqlen,
            device=q.device,
            dtype=torch.int32,
        ),
        max_seqlen_q=q_seqlen,
        max_seqlen_k=k_seqlen,
        dropout_p=dropout_p,
    )
    return out.reshape(BS, -1, dim)


def xformers_attention(
    q: torch.Tensor,
    kv: torch.Tensor,
    dim: int,
    num_heads: int,
    dropout_p: float = 0.0,
    attn_bias: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    key = kv[..., :dim]
    value = kv[..., dim:]
    return memory_efficient_attention(
        query=q.contiguous(),
        key=key.contiguous(),
        value=value.contiguous(),
        p=dropout_p,
        attn_bias=attn_bias,
    )


def naive_attention(
    q: torch.Tensor,
    kv: torch.Tensor,
    dim: int,
    num_heads: int,
    dropout_p: float = 0.0,
    attn_bias: Optional[torch.Tensor] = None,
) -> torch.Tensor:
    """
    From https://github.com/facebookresearch/xformers/blob/main/tests/test_mem_eff_attention.py#L188
    Copyright (c) Facebook, Inc. and its affiliates
    BSD 3-Clause License
    """

    q = q.contiguous()
    k = kv[..., :dim].contiguous()
    v = kv[..., dim:].contiguous()

    scale = 1 / q.shape[-1] ** 0.5
    q = q * scale

    attn = q @ k.transpose(-2, -1)
    if attn_bias is not None:
        attn += attn_bias
    attn = attn.softmax(-1)
    attn = F.dropout(attn, p=dropout_p)
    return attn @ v
