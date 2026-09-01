from decimal import Decimal
import unittest

from src.core.v2_business_rules import (
    CompanyRole,
    DeviceClass,
    Seat,
    SeatBillingStatus,
    calculate_consolidated_price,
    can_manage_company,
    can_transfer_principal,
    is_valid_cnpj,
    money,
    normalize_cnpj,
)


def seat(status=SeatBillingStatus.ACTIVE, kind=DeviceClass.ADDITIONAL):
    return Seat(kind, status)


class V2BusinessRulesTests(unittest.TestCase):
    def test_one_computer_costs_base_price(self):
        result = calculate_consolidated_price([seat(kind=DeviceClass.PRINCIPAL)])
        self.assertEqual(result.total, Decimal("300.00"))
        self.assertEqual(result.additional_seats, 0)

    def test_each_additional_computer_costs_fifty_even_same_company(self):
        result = calculate_consolidated_price([
            seat(kind=DeviceClass.PRINCIPAL), seat(), seat(), seat(),
        ])
        self.assertEqual(result.billable_seats, 4)
        self.assertEqual(result.additional_seats, 3)
        self.assertEqual(result.total, Decimal("450.00"))

    def test_pending_removal_and_blocked_remain_billable_until_effective_removal(self):
        result = calculate_consolidated_price([
            seat(kind=DeviceClass.PRINCIPAL),
            seat(SeatBillingStatus.PENDING_REMOVAL),
            seat(SeatBillingStatus.BLOCKED),
            seat(SeatBillingStatus.REMOVED),
        ])
        self.assertEqual(result.billable_seats, 3)
        self.assertEqual(result.total, Decimal("400.00"))

    def test_no_active_computer_has_zero_invoice(self):
        result = calculate_consolidated_price([seat(SeatBillingStatus.REMOVED)])
        self.assertEqual(result.total, Decimal("0.00"))

    def test_custom_legacy_price_is_preserved_by_calculation(self):
        result = calculate_consolidated_price(
            [seat(kind=DeviceClass.PRINCIPAL), seat()], "250", "50"
        )
        self.assertEqual(result.total, Decimal("300.00"))

    def test_invalid_money_is_rejected(self):
        for invalid in ["-1", "nan", "infinity", "texto", None]:
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, "INVALID_MONEY"):
                money(invalid)

    def test_cnpj_is_normalized_and_validated(self):
        self.assertEqual(normalize_cnpj("04.252.011/0001-10"), "04252011000110")
        self.assertTrue(is_valid_cnpj("04.252.011/0001-10"))
        self.assertFalse(is_valid_cnpj("11.111.111/1111-11"))
        self.assertFalse(is_valid_cnpj("04.252.011/0001-11"))

    def test_company_permissions_are_server_oriented(self):
        self.assertTrue(can_manage_company(CompanyRole.OWNER))
        self.assertTrue(can_manage_company(CompanyRole.ADMIN))
        self.assertFalse(can_manage_company(CompanyRole.OPERATOR))
        self.assertTrue(can_transfer_principal(CompanyRole.OWNER))
        self.assertFalse(can_transfer_principal(CompanyRole.ADMIN))


if __name__ == "__main__":
    unittest.main()
