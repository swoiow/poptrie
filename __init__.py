from . import poptrie as _native
from .ip_searcher import IpSearcher, PoptrieError  # noqa
from .poptrie import *


__doc__ = _native.__doc__

_native_all = getattr(_native, "__all__", [])
__all__ = [name for name in _native_all if name != "IpSearcher"] + ["IpSearcher", "PoptrieError"]
