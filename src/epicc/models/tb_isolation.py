import importlib.resources
from decimal import ROUND_HALF_EVEN, Decimal, getcontext
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from ruamel.yaml import YAML

from epicc.model.base import BaseSimulationModel


class TBProgressionParams(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    first_2_years: float = Field(
        alias="First 2 years (prob_latent_to_active_2yr)", ge=0.0, le=1.0
    )
    rest_of_lifetime: float = Field(
        alias="Rest of lifetime (prob_latent_to_active_lifetime)", ge=0.0, le=1.0
    )


class TBCostParams(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    cost_latent: float = Field(
        alias="Cost of latent TB infection (cost_latent)", ge=0.0
    )
    cost_active: float = Field(
        alias="Cost of active TB infection (cost_active)", ge=0.0
    )
    isolation_type: int = Field(
        alias="Isolation type (1=hospital,2=motel,3=home)", ge=1, le=3
    )
    isolation_cost: float = Field(alias="Daily isolation cost (isolation_cost)", ge=0.0)
    direct_medical_cost_day: float = Field(
        alias="Direct medical cost of a day of isolation", ge=0.0
    )
    motel_room_cost: float = Field(alias="Cost of motel room per day", ge=0.0)
    hourly_wage_worker: float = Field(alias="Hourly wage for worker", ge=0.0)
    hourly_wage_nurse: float = Field(alias="Hourly wage for nurse", ge=0.0)
    nurse_checkin_hours: float = Field(
        alias="Time for nurse to check in w/ pt in motel or home (hrs)", ge=0.0
    )


class TBIsolationParams(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    contacts_per_case: float = Field(
        alias="Number of contacts for each released TB case", ge=0.0
    )
    prob_latent_if_14_day: float = Field(
        alias="Probability that contact develops latent TB if 14-day isolation",
        ge=0.0,
        le=1.0,
    )
    infectiousness_multiplier: float = Field(
        alias="Multiplier for infectiousness with 5-day vs. 14-day isolation", ge=0.0
    )
    workday_ratio: float = Field(
        alias="Ratio of workdays to total days", ge=0.0, le=1.0
    )
    progression: TBProgressionParams = Field(
        alias="Probability of transitioning from latent to active TB"
    )
    costs: TBCostParams = Field(alias="Costs")
    discount_rate: float = Field(alias="Discount rate", ge=0.0)
    remaining_years_of_life: int = Field(alias="Remaining years of life", ge=0)


class TBIsolationModel(BaseSimulationModel[TBIsolationParams]):
    def human_name(self) -> str:
        return "TB Isolation"

    @property
    def model_title(self) -> str:
        return "TB Isolation Cost Calculator"

    @property
    def model_description(self) -> str:
        return "Estimates hospitalization, tracing, and productivity costs for TB isolation scenarios."

    @property
    def scenario_labels(self) -> dict[str, str]:
        return {
            "14_day": "14-day Isolation",
            "5_day": "5-day Isolation",
        }

    def default_params(self) -> dict[str, Any]:
        with (
            importlib.resources.files("epicc.models")
            .joinpath("tb_isolation.yaml")
            .open("rb") as f
        ):
            return dict(YAML().load(f))

    def parameter_model(self) -> type[TBIsolationParams]:
        return TBIsolationParams

    def run(
        self,
        params: TBIsolationParams,
        label_overrides: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        getcontext().prec = 28
        one = Decimal("1")
        cent = Decimal("0.01")

        if label_overrides is None:
            label_overrides = {}

        lbl_14 = label_overrides.get("14_day", self.scenario_labels["14_day"])
        lbl_5 = label_overrides.get("5_day", self.scenario_labels["5_day"])

        def q2(x: Decimal) -> Decimal:
            if abs(x) > 10:
                return x.quantize(one, rounding=ROUND_HALF_EVEN)
            return x.quantize(cent, rounding=ROUND_HALF_EVEN)

        def q2n(x: Decimal) -> Decimal:
            return x.quantize(cent, rounding=ROUND_HALF_EVEN)

        contacts_per_case = Decimal(str(params.contacts_per_case))
        prob_latent_if_14day = Decimal(str(params.prob_latent_if_14_day))
        infectiousness_multiplier = Decimal(str(params.infectiousness_multiplier))
        workday_ratio = Decimal(str(params.workday_ratio))

        prob_latent_to_active_2yr = Decimal(str(params.progression.first_2_years))
        prob_latent_to_active_lifetime = Decimal(
            str(params.progression.rest_of_lifetime)
        )

        cost_latent = Decimal(str(params.costs.cost_latent))
        cost_active = Decimal(str(params.costs.cost_active))

        isolation_type = int(params.costs.isolation_type)
        daily_hosp_cost = Decimal(str(params.costs.isolation_cost))
        direct_med_cost_day = Decimal(str(params.costs.direct_medical_cost_day))

        cost_motel_room = Decimal(str(params.costs.motel_room_cost))
        hourly_wage_nurse = Decimal(str(params.costs.hourly_wage_nurse))
        time_nurse_checkin = Decimal(str(params.costs.nurse_checkin_hours))
        hourly_wage_worker = Decimal(str(params.costs.hourly_wage_worker))

        discount_rate = Decimal(str(params.discount_rate))
        remaining_years = int(params.remaining_years_of_life)

        if isolation_type == 1:
            daily_cost = (
                direct_med_cost_day if direct_med_cost_day > 0 else daily_hosp_cost
            )
        elif isolation_type == 2:
            daily_cost = cost_motel_room + (hourly_wage_nurse * time_nurse_checkin)
        else:
            daily_cost = hourly_wage_nurse * time_nurse_checkin

        latent_14_day = q2n(contacts_per_case * prob_latent_if_14day)
        latent_5_day = q2n(latent_14_day * infectiousness_multiplier)

        active_14_day = q2n(
            latent_14_day * prob_latent_to_active_2yr
            + latent_14_day
            * (one - prob_latent_to_active_2yr)
            * prob_latent_to_active_lifetime
        )
        active_5_day = q2n(
            latent_5_day * prob_latent_to_active_2yr
            + latent_5_day
            * (one - prob_latent_to_active_2yr)
            * prob_latent_to_active_lifetime
        )

        df_infections = pd.DataFrame(
            {
                "Outcome": ["Latent TB infections", "Active TB disease"],
                lbl_14: [latent_14_day, active_14_day],
                lbl_5: [latent_5_day, active_5_day],
            }
        )

        direct_cost_14_day = q2(daily_cost * Decimal(14))
        direct_cost_5_day = q2(daily_cost * Decimal(5))

        productivity_loss_14_day = q2(
            Decimal(14) * workday_ratio * hourly_wage_worker * Decimal(8)
        )
        productivity_loss_5_day = q2(
            Decimal(5) * workday_ratio * hourly_wage_worker * Decimal(8)
        )

        base = one + discount_rate
        discounted_2yr = (prob_latent_to_active_2yr / Decimal(2)) / (base**1) + (
            (prob_latent_to_active_2yr / Decimal(2)) / (base**2)
        )
        discounted_lifetime = sum(
            (prob_latent_to_active_lifetime / Decimal(remaining_years)) / (base**y)
            for y in range(3, remaining_years + 1)
        )

        sec_cost_per_latent = q2(
            cost_latent + cost_active * (discounted_2yr + discounted_lifetime)
        )

        secondary_cost_14_day = q2(latent_14_day * sec_cost_per_latent)
        secondary_cost_5_day = q2(latent_5_day * sec_cost_per_latent)

        total_14_day = q2(
            direct_cost_14_day + productivity_loss_14_day + secondary_cost_14_day
        )
        total_5_day = q2(
            direct_cost_5_day + productivity_loss_5_day + secondary_cost_5_day
        )

        df_costs = pd.DataFrame(
            {
                "Cost Type": [
                    "Direct cost of isolation",
                    "Lost productivity for index case",
                    "Cost of secondary infections",
                    "Total cost",
                ],
                lbl_14: [
                    direct_cost_14_day,
                    productivity_loss_14_day,
                    secondary_cost_14_day,
                    total_14_day,
                ],
                lbl_5: [
                    direct_cost_5_day,
                    productivity_loss_5_day,
                    secondary_cost_5_day,
                    total_5_day,
                ],
            }
        )

        return {
            "df_infections": df_infections,
            "df_costs": df_costs,
        }

    def build_sections(self, results: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "title": "Number of Secondary Infections",
                "content": [results["df_infections"]],
            },
            {"title": "Costs", "content": [results["df_costs"]]},
        ]
