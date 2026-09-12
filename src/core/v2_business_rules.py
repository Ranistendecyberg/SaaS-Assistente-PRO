"""Regras comerciais puras da versão 2.0.

Este módulo não acessa Supabase, Mercado Pago nem a interface. Manter os
cálculos aqui permite validar preços e vínculos antes de conectá-los ao banco
de produção.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import StrEnum
from typing import Iterable


CENTAVOS = Decimal("0.01")
PRECO_PRINCIPAL_PADRAO = Decimal("300.00")
PRECO_ADICIONAL_PADRAO = Decimal("50.00")


class CompanyRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    OPERATOR = "operator"


class DeviceClass(StrEnum):
    PRINCIPAL = "principal"
    ADDITIONAL = "additional"


class SeatBillingStatus(StrEnum):
    ACTIVE = "active"
    PENDING_REMOVAL = "pending_removal"
    BLOCKED = "blocked"
    REMOVED = "removed"


@dataclass(frozen=True)
class Seat:
    device_class: DeviceClass
    billing_status: SeatBillingStatus

    @property
    def is_billable(self) -> bool:
        # Bloqueio operacional não cancela uma vaga já contratada. A vaga só
        # deixa a próxima fatura após a remoção efetiva.
        return self.billing_status in {
            SeatBillingStatus.ACTIVE,
            SeatBillingStatus.PENDING_REMOVAL,
            SeatBillingStatus.BLOCKED,
        }


@dataclass(frozen=True)
class ConsolidatedPrice:
    billable_seats: int
    additional_seats: int
    base_price: Decimal
    additional_unit_price: Decimal
    total: Decimal


def money(value: object) -> Decimal:
    """Normaliza um valor monetário e impede números negativos/inválidos."""
    try:
        normalized = Decimal(str(value).strip().replace("R$", "").replace(" ", ""))
    except (InvalidOperation, AttributeError, ValueError) as error:
        raise ValueError("INVALID_MONEY") from error
    if not normalized.is_finite() or normalized < 0:
        raise ValueError("INVALID_MONEY")
    return normalized.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def calculate_consolidated_price(
    seats: Iterable[Seat],
    base_price: object = PRECO_PRINCIPAL_PADRAO,
    additional_unit_price: object = PRECO_ADICIONAL_PADRAO,
) -> ConsolidatedPrice:
    """Calcula uma cobrança por empresa, não por CNPJ.

    A primeira vaga faturável usa o preço principal. Cada computador ativo
    adicional acrescenta o preço unitário, mesmo que use o mesmo CNPJ.
    """
    base = money(base_price)
    additional_price = money(additional_unit_price)
    billable = [seat for seat in seats if seat.is_billable]
    count = len(billable)
    additional_count = max(0, count - 1)
    total = Decimal("0.00") if count == 0 else base + additional_price * additional_count
    return ConsolidatedPrice(
        billable_seats=count,
        additional_seats=additional_count,
        base_price=base,
        additional_unit_price=additional_price,
        total=total.quantize(CENTAVOS),
    )


def normalize_cnpj(value: object) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())


def is_valid_cnpj(value: object) -> bool:
    digits = normalize_cnpj(value)
    if len(digits) != 14 or not digits.isascii() or digits == digits[0] * 14:
        return False

    def verifier(base: str, weights: tuple[int, ...]) -> str:
        remainder = sum(int(number) * weight for number, weight in zip(base, weights)) % 11
        result = 0 if remainder < 2 else 11 - remainder
        return str(result)

    first = verifier(digits[:12], (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    second = verifier(digits[:12] + first, (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    return digits[-2:] == first + second


def is_valid_cpf(value: object) -> bool:
    digits = normalize_cnpj(value)
    if len(digits) != 11 or not digits.isascii() or len(set(digits)) == 1:
        return False
    base = digits[:9]
    for size in (10, 11):
        remainder = sum(int(digit) * weight for digit, weight in zip(base, range(size, 1, -1))) % 11
        base += str(0 if remainder < 2 else 11 - remainder)
    return base == digits


def is_valid_document(value: object) -> bool:
    return is_valid_cpf(value) or is_valid_cnpj(value)


def can_manage_company(role: CompanyRole | str) -> bool:
    try:
        normalized = CompanyRole(role)
    except ValueError:
        return False
    return normalized in {CompanyRole.OWNER, CompanyRole.ADMIN}


def can_transfer_principal(role: CompanyRole | str) -> bool:
    try:
        return CompanyRole(role) is CompanyRole.OWNER
    except ValueError:
        return False
