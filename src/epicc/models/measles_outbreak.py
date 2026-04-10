import importlib.resources
from decimal import ROUND_HALF_EVEN, Decimal, getcontext
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from ruamel.yaml import YAML

from epicc.model.base import BaseSimulationModel


class MeaslesOutbreakParams(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    cost_measles_hospitalization: float = Field(
        alias="Cost of measles hospitalization", ge=0.0
    )
    proportion_hospitalized: float = Field(
        alias="Proportion of cases hospitalized", ge=0.0, le=1.0
    )
    proportion_missed_workdays: float = Field(
        alias="Proportion of quarantine days that would be a missed day of work",
        ge=0.0,
        le=1.0,
    )
    hourly_wage_worker: float = Field(alias="Hourly wage for worker", ge=0.0)
    hourly_wage_contract_tracer: float = Field(
        alias="Hourly wage for contract tracer", ge=0.0
    )
    hours_contact_tracing_per_contact: float = Field(
        alias="Hours of contact tracing per contact", ge=0.0
    )
    contacts_per_case: float = Field(alias="Number of contacts per case", ge=0.0)
    vaccination_rate: float = Field(
        alias="Vaccination rate in community", ge=0.0, le=1.0
    )
    quarantine_days: int = Field(alias="Length of quarantine (days)", ge=0)


class MeaslesOutbreakModel(BaseSimulationModel[MeaslesOutbreakParams]):
    def human_name(self) -> str:
        return "Measles Outbreak"

    @property
    def model_title(self) -> str:
        return "Measles Outbreak Cost Estimation"

    @property
    def model_description(self) -> str:
        return "Estimates hospitalization, tracing, and productivity costs for measles outbreaks."

    @property
    def scenario_labels(self) -> dict[str, str]:
        return {
            "22_cases": "22 Cases",
            "100_cases": "100 Cases",
            "803_cases": "803 Cases",
        }

    def default_params(self) -> dict[str, Any]:
        with (
            importlib.resources.files("epicc.models")
            .joinpath("measles_outbreak.yaml")
            .open("rb") as f
        ):
            return dict(YAML().load(f))

    def parameter_model(self) -> type[MeaslesOutbreakParams]:
        return MeaslesOutbreakParams

    def run(
        self,
        params: MeaslesOutbreakParams,
        label_overrides: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        getcontext().prec = 28
        one = Decimal("1")
        cent = Decimal("0.01")

        if label_overrides is None:
            label_overrides = {}

        lbl_22 = label_overrides.get("22_cases", self.scenario_labels["22_cases"])
        lbl_100 = label_overrides.get("100_cases", self.scenario_labels["100_cases"])
        lbl_803 = label_overrides.get("803_cases", self.scenario_labels["803_cases"])

        def q2(x: Decimal) -> Decimal:
            if abs(x) > 10:
                return x.quantize(one, rounding=ROUND_HALF_EVEN)
            return x.quantize(cent, rounding=ROUND_HALF_EVEN)

        cost_hosp = Decimal(str(params.cost_measles_hospitalization))
        prop_hosp = Decimal(str(params.proportion_hospitalized))
        missed_ratio = Decimal(str(params.proportion_missed_workdays))
        wage_worker = Decimal(str(params.hourly_wage_worker))
        wage_tracer = Decimal(str(params.hourly_wage_contract_tracer))
        hrs_tracing = Decimal(str(params.hours_contact_tracing_per_contact))
        contacts = Decimal(str(params.contacts_per_case))
        vacc_rate = Decimal(str(params.vaccination_rate))
        quarantine = int(params.quarantine_days)

        hosp_22 = q2(22 * prop_hosp * cost_hosp)
        hosp_100 = q2(100 * prop_hosp * cost_hosp)
        hosp_803 = q2(803 * prop_hosp * cost_hosp)

        lost_22 = q2(
            22 * contacts * (1 - vacc_rate) * quarantine * missed_ratio * wage_worker
        )
        lost_100 = q2(
            100 * contacts * (1 - vacc_rate) * quarantine * missed_ratio * wage_worker
        )
        lost_803 = q2(
            803 * contacts * (1 - vacc_rate) * quarantine * missed_ratio * wage_worker
        )

        trace_22 = q2(22 * contacts * hrs_tracing * wage_tracer)
        trace_100 = q2(100 * contacts * hrs_tracing * wage_tracer)
        trace_803 = q2(803 * contacts * hrs_tracing * wage_tracer)

        total_22 = q2(hosp_22 + lost_22 + trace_22)
        total_100 = q2(hosp_100 + lost_100 + trace_100)
        total_803 = q2(hosp_803 + lost_803 + trace_803)

        df_costs = pd.DataFrame(
            {
                "Cost Type": [
                    "Hospitalization",
                    "Lost productivity",
                    "Contact tracing",
                    "TOTAL",
                ],
                lbl_22: [hosp_22, lost_22, trace_22, total_22],
                lbl_100: [hosp_100, lost_100, trace_100, total_100],
                lbl_803: [hosp_803, lost_803, trace_803, total_803],
            }
        )

        return {"df_costs": df_costs}

    def build_sections(self, results: dict[str, Any]) -> list[dict[str, Any]]:
        return [{"title": "Measles Outbreak Costs", "content": [results["df_costs"]]}]
