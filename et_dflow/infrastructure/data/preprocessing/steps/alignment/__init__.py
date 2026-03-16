"""
Alignment step: cross_correlation, center_of_mass, axis_shift, tilts_rotation.
"""

from et_dflow.infrastructure.data.preprocessing.registry import register
from et_dflow.infrastructure.data.preprocessing.steps.alignment.adapters import (
    align_cross_correlation,
    align_center_of_mass,
    align_axis_shift,
    align_tilts_rotation,
)

register("alignment", align_cross_correlation, method="cross_correlation", default=True)
register("alignment", align_center_of_mass, method="center_of_mass")
register("alignment", align_axis_shift, method="axis_shift")
register("alignment", align_tilts_rotation, method="tilts_rotation")
register("alignment", align_tilts_rotation, method="tilt_axis")  # alias
