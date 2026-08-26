"""Validated records produced by the parsers, before they reach the database.

Pydantic is doing real work here: a lease whose end date precedes its start
date, or a square footage of 90,000, is a parse error we want to see rather
than a row we want to load.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChargeRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    charge_code: str
    amount: Decimal
    source_row: int


class LeaseRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    # 'current' or 'future'. Future applicants are signed but not moved in;
    # counting them as occupied would inflate occupancy by 93 units.
    section: str
    unit_number: str
    unit_type: str | None = None
    square_feet: int | None = Field(None, ge=0, le=50_000)
    resident_code: str | None = None
    resident_name: str | None = None
    is_vacant: bool = False
    market_rent: Decimal | None = None
    resident_deposit: Decimal | None = None
    other_deposit: Decimal | None = None
    balance: Decimal | None = None
    move_in_date: date | None = None
    lease_expiration: date | None = None
    move_out_date: date | None = None
    # The block's own Total row -- our primary reconciliation target,
    # available on all 25 files.
    reported_total: Decimal | None = None
    charges: list[ChargeRecord] = Field(default_factory=list)
    source_row: int

    @model_validator(mode="after")
    def _dates_ordered(self):
        if self.move_in_date and self.move_out_date:
            if self.move_out_date < self.move_in_date:
                raise ValueError(
                    f"unit {self.unit_number}: move_out precedes move_in"
                )
        return self

    @model_validator(mode="after")
    def _vacant_has_no_resident(self):
        if self.is_vacant and self.resident_code:
            raise ValueError(
                f"unit {self.unit_number}: marked vacant but has a resident code"
            )
        return self

    @property
    def lease_status(self) -> str:
        if self.is_vacant:
            return "vacant"
        if self.section == "future":
            return "future"
        if self.move_out_date:
            return "notice"
        return "current"

    def charge_total(self) -> Decimal:
        return sum((c.amount for c in self.charges), Decimal(0))


class AvailabilityRecord(BaseModel):
    """One row per property -- this report is a rollup, not unit-level."""

    model_config = ConfigDict(str_strip_whitespace=True)

    property_code: str
    property_name: str
    avg_square_feet: int | None = None
    avg_rent: Decimal | None = None
    total_units: int
    occupied_no_notice: int = 0
    vacant_rented: int = 0
    vacant_unrented: int = 0
    notice_rented: int = 0
    notice_unrented: int = 0
    available: int = 0
    model_units: int = 0
    down_units: int = 0
    admin_units: int = 0
    pct_occupied: Decimal | None = None
    pct_occupied_nonrev: Decimal | None = None
    pct_leased: Decimal | None = None
    pct_trend: Decimal | None = None
    source_row: int

    @property
    def state_total(self) -> int:
        return (self.occupied_no_notice + self.vacant_rented
                + self.vacant_unrented + self.notice_rented
                + self.notice_unrented)

    @property
    def nonrevenue_units(self) -> int:
        return self.model_units + self.down_units + self.admin_units

    @property
    def unclassified_units(self) -> int:
        """Units the report counts but never classifies.

        Three commercial properties report units with no occupancy states at
        all: the Occupied/Vacant/Notice vocabulary is a residential concept.
        Stored explicitly rather than redistributed or hidden.
        """
        return self.total_units - self.state_total - self.nonrevenue_units

    @property
    def states_reconcile(self) -> bool:
        return self.unclassified_units == 0


class FileHeader(BaseModel):
    """The title block common to both report families."""

    property_code: str
    property_name: str
    as_of_date: date