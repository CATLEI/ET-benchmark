from et_dflow.infrastructure.data.preprocessing.registry import register
from et_dflow.infrastructure.data.preprocessing.steps.denoising.bilateral import denoise_bilateral
from et_dflow.infrastructure.data.preprocessing.steps.denoising.gaussian import denoise_gaussian
register("denoising", denoise_bilateral, method="bilateral", default=True)
register("denoising", denoise_gaussian, method="gaussian")
