from et_dflow.infrastructure.data.preprocessing.registry import register
from et_dflow.infrastructure.data.preprocessing.steps import alignment
from et_dflow.infrastructure.data.preprocessing.steps import denoising
from et_dflow.infrastructure.data.preprocessing.steps.downsample import downsample
from et_dflow.infrastructure.data.preprocessing.steps.background_subtraction import (
    background_subtraction_signal,
)
from et_dflow.infrastructure.data.preprocessing.steps.normalization import normalize
from et_dflow.infrastructure.data.preprocessing.steps.bad_pixels import remove_bad_pixels
from et_dflow.infrastructure.data.preprocessing.steps.drift import correct_drift

register("downsample", downsample)
register("background_subtraction", background_subtraction_signal)
register("normalization", normalize)
register("bad_pixels", remove_bad_pixels)
register("drift", correct_drift)
