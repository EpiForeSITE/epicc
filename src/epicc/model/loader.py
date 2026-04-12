from epicc.model.base import BaseSimulationModel
from epicc.models.measles_outbreak import MeaslesOutbreakModel
from epicc.models.tb_isolation import TBIsolationModel


def get_built_in_models() -> list[BaseSimulationModel]:
    return [TBIsolationModel(), MeaslesOutbreakModel()]
